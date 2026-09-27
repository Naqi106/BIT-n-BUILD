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
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import Base, engine, SessionLocal, get_db
from backend.data.db_schema import Zone, InvestigationMemory, ActionLog
from backend.app.agent.schemas import AgentInvestigation


# ---------------------------------------------------------------------------
# Shared test DB setup
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def setup_db():
    """Ensure tables exist and test zones are present for every test."""
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
    if not db.query(Zone).filter(Zone.id == "ZONE-AGENT-TEST-2").first():
        db.add(Zone(
            id="ZONE-AGENT-TEST-2",
            name="Agent Router Test Zone 2",
            pipe_length_km=8.0,
            connection_count=300,
            avg_pressure_bar=2.0,
            tariff_rate=0.006,
        ))
        db.commit()
    db.close()
    yield
    # Teardown: this file runs against the SHARED demo DB, so remove every
    # row its tests create. The conftest session-end sweep stays as a
    # backstop, but the leaks should die at the source -- every test in this
    # file creates its own rows and must not rely on leftovers from a
    # previous test.
    db = SessionLocal()
    try:
        test_zone_ids = ["ZONE-AGENT-TEST", "ZONE-AGENT-TEST-2", "ZONE-NO-MEM"]
        db.query(InvestigationMemory).filter(
            InvestigationMemory.zone_id.in_(test_zone_ids)
        ).delete(synchronize_session=False)
        db.query(ActionLog).filter(
            ActionLog.zone_id.in_(test_zone_ids)
        ).delete(synchronize_session=False)
        db.query(Zone).filter(
            Zone.id.in_(test_zone_ids)
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


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


# ===========================================================================
# Test 11: Concurrent investigations via asyncio.gather
# ===========================================================================
def test_concurrent_investigations():
    """
    Issues 3 concurrent investigation requests via asyncio.gather:
      - Req 1: ZONE-AGENT-TEST (triggers run_water_balance)
      - Req 2: ZONE-AGENT-TEST (triggers run_mnf)
      - Req 3: ZONE-AGENT-TEST-2 (triggers run_billing_anomaly)

    Verifies:
      1. Requests do not crash.
      2. Responses remain associated with the correct zone.
      3. Evidence from one request does NOT leak into another.
      4. Memory entries are correctly persisted for each zone without corruption.
      5. No shared mutable agent state is corrupted across concurrent executions.
      6. All responses validate as AgentInvestigation models.
    """
    async def _run():
        async def mock_groq_create(model=None, messages=None, **kwargs):
            last_msg = messages[-1] if messages else {}

            # Round 2: Tool execution result provided, return grounded structured JSON
            if last_msg.get("role") == "tool":
                tool_name = last_msg.get("name")
                if tool_name == "run_water_balance":
                    return _make_text_response(json.dumps({
                        "zone_id": "ZONE-AGENT-TEST",
                        "risk_level": "HIGH",
                        "likely_cause": "physical_leakage",
                        "confidence": 0.88,
                        "summary": "Zone 1 high water balance loss detected.",
                        "evidence": [{
                            "source": "run_water_balance",
                            "metric": "loss_litres",
                            "value": 25000.0,
                            "unit": "litres",
                            "explanation": "Significant gross loss calculated.",
                        }],
                        "recommendations": [{
                            "action": "Repair main pipe",
                            "priority": "HIGH",
                            "reason": "Water balance loss exceeds threshold.",
                        }],
                        "missing_data": [],
                        "ai_available": True,
                    }))
                elif tool_name == "run_mnf":
                    return _make_text_response(json.dumps({
                        "zone_id": "ZONE-AGENT-TEST",
                        "risk_level": "CRITICAL",
                        "likely_cause": "physical_leakage",
                        "confidence": 0.91,
                        "summary": "Zone 1 night flow anomaly detected.",
                        "evidence": [{
                            "source": "run_mnf",
                            "metric": "night_flow_litres",
                            "value": 3200.0,
                            "unit": "litres",
                            "explanation": "High baseline night consumption.",
                        }],
                        "recommendations": [{
                            "action": "Acoustic survey",
                            "priority": "URGENT",
                            "reason": "Suspected hidden night leak.",
                        }],
                        "missing_data": [],
                        "ai_available": True,
                    }))
                elif tool_name == "run_billing_anomaly":
                    return _make_text_response(json.dumps({
                        "zone_id": "ZONE-AGENT-TEST-2",
                        "risk_level": "MEDIUM",
                        "likely_cause": "apparent_loss_theft",
                        "confidence": 0.75,
                        "summary": "Zone 2 unmetered billing discrepancies.",
                        "evidence": [{
                            "source": "run_billing_anomaly",
                            "metric": "anomaly_count",
                            "value": 3,
                            "unit": None,
                            "explanation": "Suspect consumer meters identified.",
                        }],
                        "recommendations": [{
                            "action": "Audit consumer meters",
                            "priority": "MEDIUM",
                            "reason": "Zero consumption flags detected.",
                        }],
                        "missing_data": [],
                        "ai_available": True,
                    }))

            # Round 1: Model requests a tool call based on user question
            user_content = last_msg.get("content", "")
            if "Req1" in user_content or "water balance" in user_content:
                return _make_tool_call_response(
                    "run_water_balance",
                    {"zone_id": "ZONE-AGENT-TEST"},
                    call_id="call_wb_conc_1",
                )
            elif "Req2" in user_content or "night flow" in user_content:
                return _make_tool_call_response(
                    "run_mnf",
                    {"zone_id": "ZONE-AGENT-TEST"},
                    call_id="call_mnf_conc_2",
                )
            else:
                return _make_tool_call_response(
                    "run_billing_anomaly",
                    {"zone_id": "ZONE-AGENT-TEST-2"},
                    call_id="call_bill_conc_3",
                )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_groq_create)

        with patch("backend.app.agent.agent.AsyncGroq", return_value=mock_client), \
             patch("backend.app.agent.agent.os.getenv", side_effect=lambda k, d=None: "fake-key" if k == "GROQ_API_KEY" else d):

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                t1 = ac.post("/agent/investigate", json={
                    "zone_id": "ZONE-AGENT-TEST",
                    "question": "Req1: Investigate water balance",
                })
                t2 = ac.post("/agent/investigate", json={
                    "zone_id": "ZONE-AGENT-TEST",
                    "question": "Req2: Investigate night flow",
                })
                t3 = ac.post("/agent/investigate", json={
                    "zone_id": "ZONE-AGENT-TEST-2",
                    "question": "Req3: Investigate billing anomaly",
                })

                res1, res2, res3 = await asyncio.gather(t1, t2, t3)

        # 1. Verify all requests completed successfully without crashing
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res3.status_code == 200

        d1 = res1.json()
        d2 = res2.json()
        d3 = res3.json()

        # 2. Verify all responses validate as AgentInvestigation Pydantic schemas
        inv1 = AgentInvestigation.model_validate(d1)
        inv2 = AgentInvestigation.model_validate(d2)
        inv3 = AgentInvestigation.model_validate(d3)

        # 3. Verify responses remain associated with the correct zone
        assert inv1.zone_id == "ZONE-AGENT-TEST"
        assert inv2.zone_id == "ZONE-AGENT-TEST"
        assert inv3.zone_id == "ZONE-AGENT-TEST-2"

        assert inv1.summary == "Zone 1 high water balance loss detected."
        assert inv2.summary == "Zone 1 night flow anomaly detected."
        assert inv3.summary == "Zone 2 unmetered billing discrepancies."

        # 4. Verify evidence from one request does NOT leak into another
        d1_sources = [e["source"] for e in d1["evidence"]]
        d2_sources = [e["source"] for e in d2["evidence"]]
        d3_sources = [e["source"] for e in d3["evidence"]]

        assert d1_sources == ["run_water_balance"]
        assert d2_sources == ["run_mnf"]
        assert d3_sources == ["run_billing_anomaly"]

        assert "run_mnf" not in d1_sources
        assert "run_billing_anomaly" not in d1_sources
        assert "run_water_balance" not in d2_sources
        assert "run_billing_anomaly" not in d2_sources
        assert "run_water_balance" not in d3_sources
        assert "run_mnf" not in d3_sources

        # 5. Verify memory persistence in DB: rows exist for each zone without corruption
        db = SessionLocal()
        try:
            mem1 = (
                db.query(InvestigationMemory)
                .filter(InvestigationMemory.zone_id == "ZONE-AGENT-TEST")
                .order_by(InvestigationMemory.timestamp.desc())
                .all()
            )
            mem2 = (
                db.query(InvestigationMemory)
                .filter(InvestigationMemory.zone_id == "ZONE-AGENT-TEST-2")
                .order_by(InvestigationMemory.timestamp.desc())
                .all()
            )

            assert len(mem1) >= 2
            zone1_summaries = [m.summary for m in mem1]
            assert any("water balance" in s for s in zone1_summaries)
            assert any("night flow" in s for s in zone1_summaries)

            assert len(mem2) >= 1
            zone2_summaries = [m.summary for m in mem2]
            assert any("billing discrepancies" in s for s in zone2_summaries)
        finally:
            db.close()

    asyncio.run(_run())

