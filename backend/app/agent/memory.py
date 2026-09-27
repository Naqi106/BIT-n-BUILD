"""
Investigation Memory Service (Block 4)

Provides read/write helpers for the InvestigationMemory table defined in
backend/data/db_schema.py.  All public functions accept a SQLAlchemy Session
and return clean Python / Pydantic data — no raw ORM objects are exposed.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.data.db_schema import InvestigationMemory

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
    record = InvestigationMemory(
        zone_id=zone_id,
        summary=summary,
        action_taken=action_taken,
        outcome=outcome,
        timestamp=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("Saved investigation memory id=%d for zone %s", record.id, zone_id)
    return record.id


def get_zone_memory(
    db: Session,
    zone_id: str,
    limit: int = 5,
) -> List[dict]:
    """
    Returns the most recent `limit` investigation memory entries for a zone,
    ordered newest-first.

    Returns an empty list when no history exists — never raises on empty.
    """
    rows = (
        db.query(InvestigationMemory)
        .filter(InvestigationMemory.zone_id == zone_id)
        .order_by(InvestigationMemory.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "zone_id": r.zone_id,
            "summary": r.summary,
            "action_taken": r.action_taken,
            "outcome": r.outcome,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


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
