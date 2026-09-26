"""
TEST-FIXTURE CLEANUP -- removes leaked test zones from the shared demo DB.

Run:
    python -m backend.data.cleanup_test_zones          # report + clean
    python -m backend.data.cleanup_test_zones --dry    # report only

Why this exists: team test runs (all four of us hit the same shared
Supabase instance) have repeatedly left fixture zones behind:

  - ZONE-TEST          from alltests.py when the run was killed mid-test
  - ZONE-AGENT-TEST*   from agent router tests (create-if-missing fixture,
  - ZONE-NO-MEM        no teardown on the shared DB)
  - ZONE-NO-CENTROID   from satellite endpoint tests

Leftover fixtures show up on the Dashboard as unlabelled fake zones and
had once wiped/corrupted demo state. The canary
`backend/test/test_demo_db_integrity.py` fails when this happens; this
script is the sanctioned fix. It NEVER touches the 12 demo zones or
ZONE-DEMO-01 (Person 3's deliberate agent demo seed).
"""

import argparse
import os
import sys

# repo root, so both `python -m backend.data.cleanup_test_zones` and
# `python backend/data/cleanup_test_zones.py` resolve backend.* imports
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from sqlalchemy import func

from backend.app.db import SessionLocal
from backend.data.db_schema import (
    Zone, RawReading, BillingRecord, NRWSnapshot,
    InvestigationMemory, LeakAlert, ActionLog, RevenueLog,
)

# Fixture zones that must never appear in the demo dataset.
FORBIDDEN_ZONES = {
    "ZONE-TEST",
    "ZONE-AGENT-TEST",
    "ZONE-AGENT-TEST-2",
    "ZONE-NO-MEM",
    "ZONE-NO-CENTROID",
}

# Children first (FK-safe), then the zones themselves.
CHILD_MODELS = [
    ActionLog, RevenueLog, LeakAlert, InvestigationMemory,
    NRWSnapshot, BillingRecord, RawReading,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry", action="store_true", help="report only, delete nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        present = sorted(z.id for z in db.query(Zone) if z.id in FORBIDDEN_ZONES)
        if not present:
            print("No leaked test zones found. Demo DB is clean.")
            return 0

        print(f"Leaked test zones: {present}")
        for model in CHILD_MODELS:
            counts = dict(
                db.query(model.zone_id, func.count())
                .filter(model.zone_id.in_(FORBIDDEN_ZONES))
                .group_by(model.zone_id)
            )
            if counts:
                print(f"  {model.__tablename__}: {counts}")

        if args.dry:
            print("\n(dry run -- nothing deleted)")
            return 0

        removed = {}
        for model in CHILD_MODELS:
            n = db.query(model).filter(
                model.zone_id.in_(FORBIDDEN_ZONES)
            ).delete(synchronize_session=False)
            if n:
                removed[model.__tablename__] = n
        n = db.query(Zone).filter(Zone.id.in_(FORBIDDEN_ZONES)).delete(
            synchronize_session=False
        )
        if n:
            removed["zones"] = n
        db.commit()

        print(f"Removed: {removed}")
        print(f"Demo zones remaining: {db.query(Zone).count()} (expect 12)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
