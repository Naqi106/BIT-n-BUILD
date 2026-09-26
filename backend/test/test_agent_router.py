"""
Tests for AltoMare AI Agent Router (Block 4)

Covers:
  1.  POST /agent/investigate — success
  2.  Investigation persisted to InvestigationMemory
  3.  GET  /agent/memory/{zone_id} — returns history
  4.  Empty memory returns cleanly
  5.  POST /agent/create-action — recommendation mapping
  6.  create-action uses Person 2's ActionLog flow (state machine)
  7.  Invalid zone handled correctly
  8.  Missing/invalid Groq key uses existing fallback behaviour
  9.  Memory retrieval failure does not crash the agent
  10. Previous memory treated as historical context, not fresh evidence

All Groq API calls are mocked — no real Groq calls in CI.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import Base, engine, SessionLocal, get_db
from backend.data.db_schema import Zone, InvestigationMemory, ActionLog


# ---------------------------------------------------------------------------
# Shared test DB setup
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def setup_db():
    """Ensure tables exist and a test zone is present for every test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(Zone).filter(Zone.id == "ZONE-AGENT-TEST").first():
        db.add(Zone(
            id="ZONE-AGENT-TEST",
            name="Agent Router Test Zone",
            pipe_length_km=10.0,
            connection_count=500,
            avg_pressure_bar=2.5,
            tariff_rate=0.005,
        ))
        db.commit()
    db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers: Mock Groq responses mirroring Block 3 helpers
# ---------------------------------------------------------------------------
def _make_text_response(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=None)
            )
        ]
    )


def _make_tool_call_response(tool_name: str, arguments: dict, call_id: str = "call_1"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id=call_id,
                            type="function",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments=json.dumps(arguments),
                            ),
                        )
                    ],
                )
            )
        ]
    )


_VALID_INVESTIGATION_PAYLOAD = {
    "zone_id": "ZONE-AGENT-TEST",
    "risk_level": "HIGH",
    "likely_cause": "physical_leakage",
    "confidence": 0.87,
    "summary": "Water balance confirms high NRW. Physical leakage suspected.",
    "evidence": [],
    "recommendations": [
        {
            "action": "Acoustic leak survey",
            "priority": "HIGH",
            "reason": "Confirm physical pipe leak at high-NRW segment.",
        }
    ],
    "missing_data": [],
    "ai_available": True,
}


# ===========================================================================
# Test 1: POST /agent/investigate — success with mocked Groq (no tools called)
# ===========================================================================
def test_investigate_success(client):
    """Mocked Groq returns valid investigation JSON directly (no tool rounds)."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_text_response(
        json.dumps(_VALID_INVESTIGATION_PAYLOAD)
    )

    with patch("backend.app.agent.agent.AsyncGroq", return_value=mock_client), \
         patch("backend.app.agent.agent.os.getenv", side_effect=lambda k, d=None: "fake-key" if k == "GROQ_API_KEY" else d):
        res = client.post("/agent/investigate", json={
            "zone_id": "ZONE-AGENT-TEST",
            "question": "Why is this zone at risk?",
        })

    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == "ZONE-AGENT-TEST"
    assert data["risk_level"] == "HIGH"
    assert data["ai_available"] is True
    assert data["confidence"] == 0.87


# ===========================================================================
# Test 2: Investigation is persisted to InvestigationMemory after success
# ===========================================================================
def test_investigate_persists_memory(client):
    """After a successful investigation, a memory row must exist in the DB."""
    payload = _VALID_INVESTIGATION_PAYLOAD.copy()
    payload["zone_id"] = "ZONE-AGENT-TEST"

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_text_response(
        json.dumps(payload)
    )

    with patch("backend.app.agent.agent.AsyncGroq", return_value=mock_client), \
         patch("backend.app.agent.agent.os.getenv", side_effect=lambda k, d=None: "fake-key" if k == "GROQ_API_KEY" else d):
        res = client.post("/agent/investigate", json={
            "zone_id": "ZONE-AGENT-TEST",
            "question": "Test memory persistence",
        })

    assert res.status_code == 200
    assert res.json()["ai_available"] is True

    # Verify DB row
    db = SessionLocal()
    try:
        row = (
            db.query(InvestigationMemory)
            .filter(InvestigationMemory.zone_id == "ZONE-AGENT-TEST")
            .order_by(InvestigationMemory.timestamp.desc())
            .first()
        )
        assert row is not None
        assert "NRW" in row.summary or "leakage" in row.summary.lower()
        assert row.action_taken is not None
    finally:
        db.close()


# ===========================================================================
# Test 3: GET /agent/memory/{zone_id} returns history
# ===========================================================================
def test_get_memory_returns_history(client):
    """GET /agent/memory/{zone_id} returns existing memory rows."""
    # Pre-insert a memory row directly
    db = SessionLocal()
    try:
        db.add(InvestigationMemory(
            zone_id="ZONE-AGENT-TEST",
            summary="Historical: High NRW detected previously.",
            action_taken="Acoustic survey deployed",
            outcome="Pipe replaced, NRW dropped to 22%",
        ))
        db.commit()
    finally:
        db.close()

    res = client.get("/agent/memory/ZONE-AGENT-TEST")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(m["zone_id"] == "ZONE-AGENT-TEST" for m in data)


# ===========================================================================
# Test 4: Empty memory returns cleanly (empty list, 200 OK)
# ===========================================================================
def test_get_memory_empty_zone(client):
    """GET /agent/memory on a zone with no history returns [], not an error."""
    # Create a zone guaranteed to have no memory
    db = SessionLocal()
    try:
        if not db.query(Zone).filter(Zone.id == "ZONE-NO-MEM").first():
            db.add(Zone(id="ZONE-NO-MEM", name="No Memory Zone",
                        pipe_length_km=5.0, connection_count=100,
                        avg_pressure_bar=2.0, tariff_rate=0.005))
            db.commit()
    finally:
        db.close()

    res = client.get("/agent/memory/ZONE-NO-MEM")
    assert res.status_code == 200
    assert res.json() == []


# ===========================================================================
# Test 5: POST /agent/create-action maps recommendation correctly
# ===========================================================================
def test_create_action_from_recommendation(client):
    """create-action correctly maps recommendation fields to ActionLog columns."""
    res = client.post("/agent/create-action", json={
        "zone_id": "ZONE-AGENT-TEST",
        "action": "Acoustic leak survey",
        "priority": "HIGH",
        "reason": "High NRW detected by water balance tool.",
        "daily_loss_litres": 30000.0,
        "tariff_rate": 0.005,
        "pipe_age_years": 15,
    })

    assert res.status_code == 200
    data = res.json()
    assert data["action_type"] == "Acoustic leak survey"
    assert data["urgency"] == "HIGH"
    assert data["officer_notes"] == "High NRW detected by water balance tool."
    assert data["status"] == "PENDING"
    assert data["estimated_cost"] > 0
    assert data["estimated_payback_days"] > 0
    assert data["message"] == "Action created and pending officer approval."


# ===========================================================================
# Test 6: create-action creates a real ActionLog row (Person 2's state machine)
# ===========================================================================
def test_create_action_writes_action_log(client):
    """Verify that the ActionLog row actually exists in DB after create-action."""
    res = client.post("/agent/create-action", json={
        "zone_id": "ZONE-AGENT-TEST",
        "action": "Valve isolation test",
        "priority": "URGENT",
        "reason": "Night flow anomaly confirmed.",
        "daily_loss_litres": 50000.0,
    })
    assert res.status_code == 200
    action_id = res.json()["action_id"]

    db = SessionLocal()
    try:
        row = db.query(ActionLog).filter(ActionLog.id == action_id).first()
        assert row is not None
        assert row.status == "PENDING"
        assert row.zone_id == "ZONE-AGENT-TEST"
        assert row.action_type == "Valve isolation test"
        assert row.urgency == "URGENT"
    finally:
        db.close()


# ===========================================================================
# Test 7: Invalid zone returns 404
# ===========================================================================
def test_investigate_invalid_zone(client):
    """POST /agent/investigate with an unknown zone_id returns 404."""
    res = client.post("/agent/investigate", json={
        "zone_id": "ZONE-DOES-NOT-EXIST",
        "question": "anything",
    })
    assert res.status_code == 404


def test_create_action_invalid_zone(client):
    """POST /agent/create-action with unknown zone_id returns 404."""
    res = client.post("/agent/create-action", json={
        "zone_id": "ZONE-DOES-NOT-EXIST",
        "action": "Test",
        "priority": "LOW",
        "reason": "Test",
        "daily_loss_litres": 1000.0,
    })
    assert res.status_code == 404


def test_memory_invalid_zone(client):
    """GET /agent/memory/{zone_id} with unknown zone_id returns 404."""
    res = client.get("/agent/memory/ZONE-DOES-NOT-EXIST")
    assert res.status_code == 404


# ===========================================================================
# Test 8: Missing GROQ_API_KEY uses existing fallback behaviour
# ===========================================================================
def test_investigate_missing_api_key_uses_fallback(client):
    """When GROQ_API_KEY is absent, investigate() returns a graceful fallback."""
    import os
    with patch.dict(os.environ, {}, clear=True):
        res = client.post("/agent/investigate", json={
            "zone_id": "ZONE-AGENT-TEST",
            "question": "Test fallback",
        })

    # Fallback still returns 200 — it is a structured degraded result
    assert res.status_code == 200
    data = res.json()
    assert data["ai_available"] is False
    assert data["risk_level"] == "UNKNOWN"
    assert "GROQ_API_KEY" in data["summary"]


# ===========================================================================
# Test 9: Memory retrieval failure does not crash the agent
# ===========================================================================
def test_memory_retrieval_failure_does_not_crash(client):
    """If get_zone_memory raises, investigate() continues and returns a result."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_text_response(
        json.dumps(_VALID_INVESTIGATION_PAYLOAD)
    )

    with patch("backend.app.agent.agent.AsyncGroq", return_value=mock_client), \
         patch("backend.app.agent.agent.os.getenv", side_effect=lambda k, d=None: "fake-key" if k == "GROQ_API_KEY" else d), \
         patch("backend.app.agent.agent.get_zone_memory", side_effect=RuntimeError("DB connection lost")):
        res = client.post("/agent/investigate", json={
            "zone_id": "ZONE-AGENT-TEST",
            "question": "Test memory failure resilience",
        })

    # Agent must still return a result despite memory failure
    assert res.status_code == 200
    assert res.json()["ai_available"] is True


# ===========================================================================
# Test 10: Previous memory is historical context, not fresh evidence
# ===========================================================================
def test_memory_context_not_treated_as_evidence(client):
    """
    If an old memory entry exists for the zone, but no tool is called for the
    matching source in the current round, that source must not appear in evidence.

    Simulate: Groq returns evidence citing 'run_ppa' (not called) while
    old memory mentions a past PPA investigation.  The grounding check must
    still reject the hallucinated PPA evidence.
    """
    # Pre-insert old memory mentioning PPA
    db = SessionLocal()
    try:
        db.add(InvestigationMemory(
            zone_id="ZONE-AGENT-TEST",
            summary="Previous investigation: PPA found pressure drop at Node 4.",
            action_taken="PPA survey ordered",
            outcome=None,
        ))
        db.commit()
    finally:
        db.close()

    # Groq returns a payload that hallucinates PPA evidence (tool was not called)
    hallucinated_payload = {
        "zone_id": "ZONE-AGENT-TEST",
        "risk_level": "HIGH",
        "likely_cause": "physical_leakage",
        "confidence": 0.80,
        "summary": "Based on historical PPA records...",
        "evidence": [
            {
                "source": "run_ppa",
                "metric": "pressure_drop_bar",
                "value": 1.2,
                "unit": "bar",
                "explanation": "Hallucinated from old memory",
            }
        ],
        "recommendations": [],
        "missing_data": [],
        "ai_available": True,
    }

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_text_response(
        json.dumps(hallucinated_payload)
    )

    with patch("backend.app.agent.agent.AsyncGroq", return_value=mock_client), \
         patch("backend.app.agent.agent.os.getenv", side_effect=lambda k, d=None: "fake-key" if k == "GROQ_API_KEY" else d):
        res = client.post("/agent/investigate", json={
            "zone_id": "ZONE-AGENT-TEST",
            "question": "Test memory grounding",
        })

    # Hallucinated evidence must trigger fallback — grounding must hold
    assert res.status_code == 200
    data = res.json()
    assert data["ai_available"] is False
    assert "unvalidated structure" in data["summary"]
