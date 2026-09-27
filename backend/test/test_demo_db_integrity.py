"""
Demo-DB integrity canary (roadmap Hours 19-22: "verify every zone's synthetic
numbers still sum correctly to the real Lucknow aggregate after all the new
writes").

The demo DB is a SHARED Supabase Postgres. Sep 26-27 incidents this file is
meant to catch:
  - team test runs left fixture zones behind (ZONE-TEST + 4 snapshots that
    corrupted the town forecast; ZONE-AGENT-TEST/ZONE-NO-MEM + 20 memory rows)
  - something repeatedly ran `DELETE FROM zones` (children intact), wiping all
    12 demo zones three times in one evening

These tests are read-only. Via conftest.py they run FIRST in every
session -- before any test can write -- so they describe the state a
judge would see; conftest.py also sweeps leaked fixture zones after
every run (reported in the terminal summary).

If one fails, the demo dataset needs reseeding:
    python -m backend.data.lucknow_seed
For leaked fixture zones specifically:
    python -m backend.data.cleanup_test_zones
"""

import pytest
from sqlalchemy import func

from backend.app.db import SessionLocal
from backend.data.cleanup_test_zones import FORBIDDEN_ZONES
from backend.data.db_schema import (
    Zone, RawReading, BillingRecord, NRWSnapshot,
    InvestigationMemory, LeakAlert,
)

DEMO_ZONES = {f"zone_{i}" for i in range(1, 13)}

# Non-demo zones that are ALLOWED to exist deliberately:
#   ZONE-DEMO-01 -- Person 3's agent demo seed (backend/data/seed_agent_demo.py)
ALLOWED_EXTRA_ZONES = {"ZONE-DEMO-01"}


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _zone_ids(db):
    return {z.id for z in db.query(Zone)}


def test_all_12_demo_zones_present(db):
    """The wipe detector: every seeded Lucknow zone must exist."""
    ids = _zone_ids(db)
    missing = DEMO_ZONES - ids
    assert not missing, (
        f"Demo zones missing from the DB: {sorted(missing)}. "
        f"Run: python -m backend.data.lucknow_seed"
    )
    extras = ids - DEMO_ZONES
    assert extras <= ALLOWED_EXTRA_ZONES, (
        f"Unknown zones on the shared demo DB: {sorted(extras - ALLOWED_EXTRA_ZONES)}. "
        f"Test fixtures must not leak here (tear them down, or run: "
        f"python -m backend.data.cleanup_test_zones)"
    )


def test_no_forbidden_test_zones(db):
    ids = _zone_ids(db)
    leaked = ids & FORBIDDEN_ZONES
    assert not leaked, (
        f"Test fixture zones leaked into the demo DB: {sorted(leaked)}. "
        f"Run: python -m backend.data.cleanup_test_zones"
    )


def test_readings_present_for_every_demo_zone(db):
    counts = dict(
        db.query(RawReading.zone_id, func.count())
        .group_by(RawReading.zone_id)
    )
    for zid in DEMO_ZONES:
        assert counts.get(zid, 0) >= 80, (
            f"{zid} has only {counts.get(zid, 0)} readings (expected ~90)."
        )


def test_snapshots_complete_and_scoped_to_known_zones(db):
    """13 weeks per demo zone; zero rows on any test/unknown zone."""
    counts = dict(
        db.query(NRWSnapshot.zone_id, func.count())
        .group_by(NRWSnapshot.zone_id)
    )
    unknown = set(counts) - DEMO_ZONES - ALLOWED_EXTRA_ZONES
    assert not unknown, f"Snapshots exist for unknown zones: {sorted(unknown)}"

    for zid in DEMO_ZONES:
        assert counts.get(zid, 0) >= 13, (
            f"{zid} has {counts.get(zid, 0)} snapshots (expected >= 13)."
        )


def test_billing_scoped_to_known_zones(db):
    zones_with_billing = {
        zid for (zid,) in db.query(BillingRecord.zone_id).distinct()
    }
    unknown = zones_with_billing - DEMO_ZONES - ALLOWED_EXTRA_ZONES
    assert not unknown, f"Billing rows exist for unknown zones: {sorted(unknown)}"

    total = db.query(BillingRecord).count()
    assert total >= 300, f"Only {total} billing records (expected ~399)."


def test_investigation_memory_scoped_to_known_zones(db):
    zones_with_memory = {
        zid for (zid,) in db.query(InvestigationMemory.zone_id).distinct()
    }
    unknown = zones_with_memory - DEMO_ZONES - ALLOWED_EXTRA_ZONES
    assert not unknown, (
        f"Investigation memory on unknown zones: {sorted(unknown)} "
        f"(test-fixture memories leaked)."
    )


def test_leak_alerts_scoped_to_known_zones(db):
    zones_with_alerts = {
        zid for (zid,) in db.query(LeakAlert.zone_id).distinct()
    }
    unknown = zones_with_alerts - DEMO_ZONES - ALLOWED_EXTRA_ZONES
    assert not unknown, f"Leak alerts on unknown zones: {sorted(unknown)}"


def test_agent_balance_citations_match_seeded_zone_data(db):
    """The Copilot's water-balance citations must agree with the numbers
    every other screen shows (roadmap final sweep: no page may contradict
    the demo dataset). Guards the snapshot-first fix in agent/tools.py --
    if anyone reverts to inflow-vs-billing-sample math, this fails."""
    from backend.app.agent.tools import run_water_balance, TOWN_ANCHOR_NRW

    assert TOWN_ANCHOR_NRW == 55.0   # same anchor as GET /data/town-profile

    worst = run_water_balance("zone_6", db=db)
    assert worst["status"] == "SUCCESS"
    assert worst["data_source"] == "WEEKLY_SNAPSHOT"
    assert worst["nrw_percentage"] == pytest.approx(70.6, abs=0.1)
    assert worst["severity"] == "CRITICAL"
    assert worst["is_leak_detected"] is True

    clean = run_water_balance("zone_8", db=db)
    assert clean["status"] == "SUCCESS"
    assert clean["nrw_percentage"] == pytest.approx(43.5, abs=0.1)
    assert clean["severity"] == "LOW"
    assert clean["is_leak_detected"] is False


def test_town_weighted_nrw_still_in_lucknow_range(db):
    """
    Latest snapshot per demo zone, inflow-weighted NRW must sit near the
    Lucknow anchor (~55%, seed computes 52.6%). Catches corrupted, missing,
    or truncated snapshot history after teammates' writes.
    """
    latest = (
        db.query(
            NRWSnapshot.zone_id,
            func.max(NRWSnapshot.timestamp).label("ts"),
        )
        .filter(NRWSnapshot.zone_id.in_(DEMO_ZONES))
        .group_by(NRWSnapshot.zone_id)
        .subquery()
    )
    rows = (
        db.query(NRWSnapshot)
        .join(
            latest,
            (NRWSnapshot.zone_id == latest.c.zone_id)
            & (NRWSnapshot.timestamp == latest.c.ts),
        )
        .all()
    )
    assert len(rows) >= 12, f"Only {len(rows)} zones have snapshots"

    total_inflow = sum(r.inflow_litres for r in rows)
    total_loss = sum(r.inflow_litres * r.nrw_percentage / 100 for r in rows)
    weighted_nrw = total_loss / total_inflow * 100

    assert 47.0 <= weighted_nrw <= 58.0, (
        f"Town weighted NRW is {weighted_nrw:.1f}% -- outside the Lucknow "
        f"anchor band (47-58%, seed target 52.6% vs city anchor 55%). "
        f"Snapshot history looks corrupted."
    )
