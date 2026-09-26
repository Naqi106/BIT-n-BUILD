"""
INVESTIGATION MEMORY ENGINE -- Person 1 (Data + ML)

Persistent memory of past flags and investigations per zone
(roadmap Hours 15-19: "Persistent Investigation Memory table + a
'previously flagged' note wired into the zone detail view").

The table itself is defined in backend/data/db_schema.py
(InvestigationMemory: zone_id, summary, action_taken, outcome, timestamp).
This module is the single place that writes and reads it:

  record_investigation()     -- append a note (officer, Copilot, or seeder)
  get_zone_investigations()  -- newest-first history for the zone detail view
  previously_flagged_note()  -- the "previously flagged" banner, or None

Conventions (same as app/agent/tools.py):
- Every return value is JSON-safe primitives only (dict/list/str/int/
  float/None) -- timestamps are ISO-8601 strings, never datetime objects.
- Never fabricates: a zone with no history gets note=None and
  previously_flagged=False, not a generic warning.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.data.db_schema import InvestigationMemory


def _as_utc(ts: datetime) -> datetime:
    """SQLite stores naive UTC; Postgres may store aware -- normalise both."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _entry_to_dict(row: InvestigationMemory) -> Dict[str, Any]:
    ts = _as_utc(row.timestamp) if row.timestamp else None
    return {
        "id": int(row.id),
        "zone_id": str(row.zone_id),
        "summary": str(row.summary),
        "action_taken": row.action_taken,
        "outcome": row.outcome,
        "timestamp": ts.isoformat() if ts else None,
    }


def record_investigation(
    db: Session,
    zone_id: str,
    summary: str,
    action_taken: Optional[str] = None,
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one investigation note for a zone and return it (JSON-safe)."""
    row = InvestigationMemory(
        zone_id=zone_id,
        summary=summary,
        action_taken=action_taken,
        outcome=outcome,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _entry_to_dict(row)


def get_zone_investigations(
    db: Session, zone_id: str, limit: int = 5
) -> List[Dict[str, Any]]:
    """Newest-first investigation history for a zone."""
    rows = (
        db.query(InvestigationMemory)
        .filter(InvestigationMemory.zone_id == zone_id)
        .order_by(InvestigationMemory.timestamp.desc(), InvestigationMemory.id.desc())
        .limit(limit)
        .all()
    )
    return [_entry_to_dict(r) for r in rows]


def count_zone_investigations(db: Session, zone_id: str) -> int:
    """Total investigations ever recorded for the zone (ignores limit)."""
    return (
        db.query(InvestigationMemory)
        .filter(InvestigationMemory.zone_id == zone_id)
        .count()
    )


def previously_flagged_note(
    db: Session, zone_id: str
) -> Optional[Dict[str, Any]]:
    """
    The "previously flagged" banner shown on the zone detail view.

    Returns None when the zone has never been investigated -- the view then
    shows no banner instead of a fabricated warning.
    """
    total = count_zone_investigations(db, zone_id)
    if total == 0:
        return None

    latest = get_zone_investigations(db, zone_id, limit=1)[0]

    days_since = None
    if latest["timestamp"]:
        last = datetime.fromisoformat(latest["timestamp"])
        days_since = max(0, (datetime.now(timezone.utc) - last).days)

    when = ""
    if latest["timestamp"]:
        last = datetime.fromisoformat(latest["timestamp"])
        when = f" on {last.strftime('%d %b %Y')}"
        if days_since == 0:
            when += " (today)"
        elif days_since == 1:
            when += " (1 day ago)"
        else:
            when += f" ({days_since} days ago)"

    return {
        "previously_flagged": True,
        "investigation_count": int(total),
        "last_flagged_at": latest["timestamp"],
        "days_since_last": days_since,
        "last_summary": latest["summary"],
        "note": (
            f"Previously flagged {total} time{'s' if total != 1 else ''}"
            f"{when}: {latest['summary']}"
        ),
    }
