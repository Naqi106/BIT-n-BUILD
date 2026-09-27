"""
Investigation Memory Service (Block 4)

Read/write helpers for the InvestigationMemory table defined in
backend/data/db_schema.py.

backend/app/engines/investigation_memory.py owns the canonical SQL for this
table (it also powers the zone-detail "previously flagged" banner). This
module keeps the agent-facing function names as thin wrappers over that
engine so the Copilot router, the prompt-context builder and the block-4
smoke script stay import-compatible, and adds the one agent-specific
concern: building the clearly-labelled historical-context block that is
injected into the system prompt.

All public functions accept a SQLAlchemy Session and return clean Python
data -- no raw ORM objects are exposed.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.engines.investigation_memory import (
    get_zone_investigations,
    record_investigation,
)

logger = logging.getLogger("altomare.agent.memory")


def save_investigation_memory(
    db: Session,
    zone_id: str,
    summary: str,
    action_taken: Optional[str] = None,
    outcome: Optional[str] = None,
) -> int:
    """
    Persists one investigation result to investigation_memory.

    Returns the new record's primary-key id so callers can log it.
    Propagates DB exceptions — callers should catch and handle them.
    """
    mem_id = record_investigation(
        db=db,
        zone_id=zone_id,
        summary=summary,
        action_taken=action_taken,
        outcome=outcome,
    )["id"]
    logger.info("Saved investigation memory id=%d for zone %s", mem_id, zone_id)
    return mem_id


def get_zone_memory(
    db: Session,
    zone_id: str,
    limit: int = 5,
) -> List[dict]:
    """
    Returns the most recent `limit` investigation memory entries for a zone,
    ordered newest-first (deterministic id tiebreak included).

    Returns an empty list when no history exists — never raises on empty.
    """
    return get_zone_investigations(db, zone_id, limit)


def get_latest_zone_memory(
    db: Session,
    zone_id: str,
) -> Optional[dict]:
    """
    Returns only the single most-recent memory entry for a zone, or None.
    Useful for quick context injection into the agent prompt.
    """
    rows = get_zone_memory(db, zone_id, limit=1)
    return rows[0] if rows else None


def build_memory_context_block(memories: List[dict]) -> str:
    """
    Converts a list of memory dicts into a clearly labelled text block
    that can be injected into the system prompt.

    The block is explicitly marked so the LLM treats it as historical context
    and NOT as fresh tool-call evidence.
    """
    if not memories:
        return ""

    lines = [
        "=== PREVIOUS INVESTIGATIONS (HISTORICAL CONTEXT ONLY) ===",
        "The following records are PAST investigation summaries for this zone.",
        "They are context, NOT current evidence. Do NOT cite them as tool results.",
        "Only current tool calls executed in this investigation count as evidence.",
        "",
    ]
    for mem in memories:
        ts = mem.get("timestamp", "unknown date")
        lines.append(f"[{ts}]")
        lines.append(f"  Summary    : {mem.get('summary', 'N/A')}")
        if mem.get("action_taken"):
            lines.append(f"  Action taken: {mem['action_taken']}")
        if mem.get("outcome"):
            lines.append(f"  Outcome    : {mem['outcome']}")
        lines.append("")

    lines.append("=== END PREVIOUS INVESTIGATIONS ===")
    return "\n".join(lines)
