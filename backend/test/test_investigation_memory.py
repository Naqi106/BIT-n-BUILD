"""
Investigation Memory tests (roadmap Hours 15-19).

Covers:
- engine round-trip + JSON safety (the Copilot consumes these dicts)
- the "previously flagged" banner: present for flagged demo zones,
  absent for the clean reference zone (zone_8)
- endpoints GET/POST /data/investigations/{zone_id}: 404s, validation,
  limit parameter, count-vs-limit semantics
- banner record counts must match what the BillingAudit screen shows

Endpoint tests use an isolated in-memory DB via dependency override, so
no test row ever touches the shared demo DB. Live-DB checks are read-only.

Known shared-DB hazard (Sep 26-27): team test runs left fixture zones
(ZONE-TEST, ZONE-AGENT-TEST, ZONE-NO-MEM) on Supabase, and something
repeatedly ran `DELETE FROM zones` (children intact). test_demo_db_integrity.py
is the canary for that class of damage.
"""

import json
import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db import Base, SessionLocal, get_db
from backend.data.db_schema import Zone, BillingRecord, InvestigationMemory
from backend.app.engines import investigation_memory as imem
from backend.app.engines import ml_billing_anomaly as mba
from backend.app.main import app


# ---------------------------------------------------------------------------
# Isolated in-memory DB fixtures (endpoint tests never touch live data)
# ---------------------------------------------------------------------------
@pytest.fixture()
def mem_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # TestClient runs the app on another thread, and a plain :memory: URL
        # gives every new connection its own EMPTY database -- StaticPool
        # shares one connection so fixtures and requests see the same tables.
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def mem_db(mem_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=mem_engine)
    session = Session()
    for zid, name in (("zone_t1", "Memory Test Ward"), ("zone_t2", "Clean Test Ward")):
        session.add(Zone(
            id=zid, name=name, pipe_length_km=1.0,
            connection_count=50, avg_pressure_bar=2.0, tariff_rate=0.005,
        ))
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client(mem_db):
    """TestClient with get_db overridden to the isolated in-memory DB."""
    app.dependency_overrides[get_db] = lambda: mem_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_detector_state():
    """Some tests retrain the live detector; restore global state after."""
    saved = mba._detector
    yield
    mba._detector = saved


# ---------------------------------------------------------------------------
# Engine: round-trip, ordering, JSON safety
# ---------------------------------------------------------------------------
def test_record_and_read_roundtrip_is_json_safe(mem_db):
    entry = imem.record_investigation(
        mem_db, "zone_t1",
        summary="Billing audit: 2 households flagged.",
        action_taken="Meter inspection assigned.",
        outcome="Pending verification.",
    )
    assert entry["zone_id"] == "zone_t1"
    assert entry["timestamp"] is not None
    json.dumps(entry)  # must not raise: ISO string, no datetime objects

    rows = imem.get_zone_investigations(mem_db, "zone_t1")
    assert len(rows) == 1
    assert rows[0]["summary"].startswith("Billing audit")
    assert rows[0]["action_taken"] == "Meter inspection assigned."


def test_history_returns_newest_first(mem_db):
    imem.record_investigation(mem_db, "zone_t1", "older note")
    imem.record_investigation(mem_db, "zone_t1", "newer note")
    rows = imem.get_zone_investigations(mem_db, "zone_t1")
    assert [r["summary"] for r in rows] == ["newer note", "older note"]


def test_note_none_when_never_flagged(mem_db):
    assert imem.previously_flagged_note(mem_db, "zone_t1") is None
    assert imem.count_zone_investigations(mem_db, "zone_t1") == 0


def test_note_structure_and_banner_text(mem_db):
    for i in range(3):
        imem.record_investigation(mem_db, "zone_t1", f"finding {i}")

    note = imem.previously_flagged_note(mem_db, "zone_t1")
    assert note["previously_flagged"] is True
    assert note["investigation_count"] == 3
    assert note["days_since_last"] == 0
    assert "Previously flagged 3 times" in note["note"]
    assert "finding 2" in note["note"]          # cites the latest summary
    assert "(today)" in note["note"]
    json.dumps(note)


def test_single_investigation_banner_grammar(mem_db):
    imem.record_investigation(mem_db, "zone_t1", "one-off check")
    note = imem.previously_flagged_note(mem_db, "zone_t1")
    assert "Previously flagged 1 time " in note["note"]
    assert note["investigation_count"] == 1


# ---------------------------------------------------------------------------
# Endpoints (isolated DB)
# ---------------------------------------------------------------------------
def test_get_unknown_zone_returns_404(client):
    assert client.get("/data/investigations/zone_nope").status_code == 404


def test_post_unknown_zone_returns_404(client):
    res = client.post("/data/investigations/zone_nope", json={"summary": "x"})
    assert res.status_code == 404


def test_clean_zone_returns_no_banner(client):
    data = client.get("/data/investigations/zone_t2").json()
    assert data["zone_id"] == "zone_t2"
    assert data["previously_flagged"] is False
    assert data["note"] is None
    assert data["investigation_count"] == 0
    assert data["entries"] == []


def test_post_then_get_shows_banner(client):
    res = client.post("/data/investigations/zone_t1", json={
        "summary": "Leak survey completed; repair scheduled.",
        "action_taken": "Work order raised",
        "outcome": "Pending repair",
    })
    assert res.status_code == 201
    assert res.json()["zone_id"] == "zone_t1"

    data = client.get("/data/investigations/zone_t1").json()
    assert data["previously_flagged"] is True
    assert "Leak survey completed" in data["note"]
    assert data["investigation_count"] == 1
    assert len(data["entries"]) == 1
    assert data["entries"][0]["outcome"] == "Pending repair"


def test_post_requires_summary(client):
    assert client.post("/data/investigations/zone_t1", json={}).status_code == 422


def test_limit_trims_entries_but_not_total_count(client):
    for i in range(7):
        client.post("/data/investigations/zone_t1", json={"summary": f"note {i}"})

    data = client.get("/data/investigations/zone_t1?limit=3").json()
    assert len(data["entries"]) == 3
    assert data["investigation_count"] == 7      # total ignores limit


# ---------------------------------------------------------------------------
# Live DB (read-only): seeded banner content + agreement with BillingAudit
# ---------------------------------------------------------------------------
def test_seeded_flags_visible_and_clean_zone_has_no_banner():
    db = SessionLocal()
    try:
        for zid in ("zone_2", "zone_4", "zone_6"):
            note = imem.previously_flagged_note(db, zid)
            assert note is not None, f"{zid} should carry a seeded history note"
            assert note["previously_flagged"] is True
            assert "billing audit" in note["last_summary"] or "NRW trend" in note["last_summary"]

        # zone_8 is the clean reference zone: no history, no banner
        assert imem.previously_flagged_note(db, "zone_8") is None
        assert imem.count_zone_investigations(db, "zone_8") == 0
    finally:
        db.close()


def test_banner_record_count_matches_billing_audit_screen():
    """
    The banner cites "(N records ...)"; BillingAudit (and the Copilot) must
    show the same N for the same zone. Trains the same detector the seed
    used, so a divergence in model, threshold, or seed derivation fails here
    instead of contradicting itself in the demo.
    """
    db = SessionLocal()
    try:
        rows = db.query(BillingRecord).all()
        frame = pd.DataFrame([{
            "billed_litres": r.billed_litres,
            "benchmark_litres": r.benchmark_litres,
            "household_size": r.household_size or 4,
        } for r in rows])
        mba.train_detector(frame)
        detector = mba.get_detector()

        for zid in ("zone_2", "zone_4"):
            note = imem.previously_flagged_note(db, zid)
            assert note is not None
            match = re.search(r"\((\d+) records?", note["last_summary"])
            assert match, f"banner summary lacks a record count: {note['last_summary']}"
            banner_count = int(match.group(1))

            zone_rows = [r for r in rows if r.zone_id == zid]
            zone_frame = frame[[r.zone_id == zid for r in rows]]
            scores = detector.predict_anomaly(zone_frame)
            audit_count = int((scores >= mba.FLAG_THRESHOLD).sum())

            assert banner_count == audit_count, (
                f"{zid}: banner says {banner_count} records, "
                f"BillingAudit would show {audit_count}"
            )
        assert detector.is_trained
    finally:
        db.close()


def test_live_endpoint_matches_engine_output():
    """GET /data/investigations/{zone} on the live DB == engine banner."""
    client = TestClient(app)          # no override: get_db hits live DB
    res = client.get("/data/investigations/zone_2")
    assert res.status_code == 200
    data = res.json()

    db = SessionLocal()
    try:
        note = imem.previously_flagged_note(db, "zone_2")
    finally:
        db.close()

    assert data["previously_flagged"] is True
    assert data["note"] == note["note"]
    assert data["investigation_count"] == note["investigation_count"]
    assert len(data["entries"]) == min(5, data["investigation_count"])
