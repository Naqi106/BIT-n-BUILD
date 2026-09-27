"""
POST /detect/{zone} de-duplication.

Regression for the Run Detection UX bug reported Sep 27: every click on a
leak-positive zone filed another identical alert row (zone_1 got ALT-16 and
ALT-17 one minute apart). The route now reuses the zone's existing ACTIVE
alert and only files a fresh row once that alert has been resolved.

Shared-DB hygiene: fixtures use the sanctioned ZONE-TEST id (already in
cleanup_test_zones.FORBIDDEN_ZONES, swept by conftest as a backstop) and are
torn down at the source here, children first, so nothing lingers for the
demo-DB canary between tests in this session.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import Base, engine, SessionLocal
from backend.data.db_schema import Zone, NRWSnapshot, RawReading, LeakAlert

FIXTURE_ZONE = "ZONE-TEST"


def _wipe_fixture(db) -> None:
    """Delete fixture rows, children first (FK-safe)."""
    db.query(LeakAlert).filter(LeakAlert.zone_id == FIXTURE_ZONE).delete(
        synchronize_session=False
    )
    db.query(NRWSnapshot).filter(NRWSnapshot.zone_id == FIXTURE_ZONE).delete(
        synchronize_session=False
    )
    db.query(RawReading).filter(RawReading.zone_id == FIXTURE_ZONE).delete(
        synchronize_session=False
    )
    db.query(Zone).filter(Zone.id == FIXTURE_ZONE).delete(synchronize_session=False)
    db.commit()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def fixture_zone():
    """A leak-positive fixture zone with one weekly snapshot (60% NRW)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _wipe_fixture(db)  # a killed earlier run may have left rows behind
        db.add(Zone(
            id=FIXTURE_ZONE,
            name="Detect Dedup Fixture",
            pipe_length_km=10.0,
            connection_count=500,
            avg_pressure_bar=2.5,
            tariff_rate=0.005,
        ))
        # Flush the parent first: Zone and NRWSnapshot have no ORM
        # relationship, so a combined flush can schedule the child insert
        # ahead of zones.id and trip the FK.
        db.flush()
        # 60,000 L loss dwarfs the UARL floor (~19,600 L/day), so the engine
        # trips: loss > unavoidable baseline -> is_leak_detected.
        db.add(NRWSnapshot(
            zone_id=FIXTURE_ZONE,
            nrw_percentage=60.0,
            inflow_litres=100000.0,
            billed_litres=40000.0,
            loss_litres=60000.0,
        ))
        db.commit()
    finally:
        db.close()
    yield FIXTURE_ZONE
    db = SessionLocal()
    try:
        _wipe_fixture(db)
    finally:
        db.close()


def _alert_count() -> int:
    db = SessionLocal()
    try:
        return (
            db.query(LeakAlert)
            .filter(LeakAlert.zone_id == FIXTURE_ZONE)
            .count()
        )
    finally:
        db.close()


def test_first_run_files_alert_and_second_run_reuses_it(client, fixture_zone):
    j1 = client.post(f"/detect/{fixture_zone}").json()
    assert j1["is_leak_detected"] is True
    assert j1.get("alert_id"), "first positive run must file an alert"
    assert j1["reused_existing"] is False

    j2 = client.post(f"/detect/{fixture_zone}").json()
    assert j2["is_leak_detected"] is True
    assert j2["reused_existing"] is True
    assert j2["alert_id"] == j1["alert_id"], "second run must return the same alert"

    # The bug itself: clicking twice used to leave two identical rows.
    assert _alert_count() == 1


def test_resolving_the_alert_rearms_detection(client, fixture_zone):
    j1 = client.post(f"/detect/{fixture_zone}").json()
    assert j1["reused_existing"] is False

    db = SessionLocal()
    try:
        alert = (
            db.query(LeakAlert)
            .filter(LeakAlert.id == j1["alert_id"])
            .first()
        )
        assert alert is not None
        # What POST /actions/resolve/{id} does to the alert row.
        alert.status = "RESOLVED"
        db.commit()
    finally:
        db.close()

    j2 = client.post(f"/detect/{fixture_zone}").json()
    assert j2["is_leak_detected"] is True
    assert j2["reused_existing"] is False, "resolved zone must be re-armed"
    assert j2["alert_id"] != j1["alert_id"], "a fresh alert must be filed"
    assert _alert_count() == 2  # old RESOLVED + new ACTIVE


def test_zone_below_the_uarl_floor_files_nothing(client, fixture_zone):
    """No actionable loss -> no alert, and no reuse bookkeeping either."""
    db = SessionLocal()
    try:
        db.query(NRWSnapshot).filter(NRWSnapshot.zone_id == FIXTURE_ZONE).delete(
            synchronize_session=False
        )
        # 100 L loss << UARL floor (~19,600 L/day) -> engine must not trip.
        db.add(NRWSnapshot(
            zone_id=FIXTURE_ZONE,
            nrw_percentage=0.1,
            inflow_litres=100000.0,
            billed_litres=99900.0,
            loss_litres=100.0,
        ))
        db.commit()
    finally:
        db.close()

    j = client.post(f"/detect/{fixture_zone}").json()
    assert j["is_leak_detected"] is False
    assert "alert_id" not in j
    assert "reused_existing" not in j
    assert _alert_count() == 0
