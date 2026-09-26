"""
Unit and Integration Tests for AltoMare AI Agent (Block 3)
Tests Groq tool-calling flow, multi-step loops, Pydantic validation,
and deterministic fallback behavior using mocked Groq clients.
"""

import os
import json
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.data.db_schema import Zone, RawReading, BillingRecord
from backend.app.agent.agent import (
    investigate,
    execute_tool,
    parse_agent_response,
    MAX_TOOL_ROUNDS,
)
from backend.app.agent.schemas import InvestigationRequest, AgentInvestigation


@pytest.fixture(scope="session")
def test_db():
    """Sets up an isolated in-memory SQLite database for agent testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    zone = Zone(
        id="ZONE-TEST-AI",
        name="AI Investigation Test Ward",
        pipe_length_km=12.0,
        connection_count=600,
        avg_pressure_bar=2.5,
        tariff_rate=0.005,
    )
    session.add(zone)

    reading = RawReading(
        zone_id="ZONE-TEST-AI",
        inflow_litres=100000.0,
        night_flow_litres=2800.0,
        pressure_bar=2.4,
    )
    session.add(reading)

    session.add(BillingRecord(
        zone_id="ZONE-TEST-AI",
        consumer_id="CONS-001",
        household_size=4,
        property_type="residential",
        billed_litres=20000.0,
        benchmark_litres=30000.0,
        anomaly_score=0.88,
        is_anomaly=True,
    ))

    session.commit()
    yield session
    session.close()


def make_text_response(content: str):
    """Creates a mock Groq response returning final text content."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )


def make_tool_call_response(tool_name: str, arguments: dict, call_id: str = "call_1"):
    """Creates a mock Groq response requesting a single tool call."""
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


def make_multi_tool_call_response(tool_calls_list):
    """Creates a mock Groq response requesting multiple tool calls."""
    tcs = [
        SimpleNamespace(
            id=cid,
            type="function",
            function=SimpleNamespace(
                name=tname,
                arguments=json.dumps(targs),
            ),
        )
        for tname, targs, cid in tool_calls_list
    ]
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=tcs,
                )
            )
        ]
    )


def test_agent_imports_and_types():
    """Verifies that all agent entry points import cleanly and expose expected callables."""
    assert callable(investigate)
    assert callable(execute_tool)
    assert callable(parse_agent_response)


def test_mocked_groq_direct_structured_response():
    """Tests that a valid JSON response from Groq parses directly into AgentInvestigation."""
    valid_payload = {
        "zone_id": "ZONE-TEST-AI",
        "risk_level": "HIGH",
        "likely_cause": "physical_leakage",
        "confidence": 0.85,
        "summary": "Zone exhibits significant physical losses based on night flow telemetry.",
        "evidence": [],
        "recommendations": [
            {
                "action": "Acoustic leak pinpointing",
                "priority": "HIGH",
                "reason": "Locate burst pipe in high-friction segment."
            }
        ],
        "missing_data": [],
        "ai_available": True
    }

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = make_text_response(json.dumps(valid_payload))

    req = InvestigationRequest(zone_id="ZONE-TEST-AI", question="Why is this zone at risk?")
    result = asyncio.run(investigate(req, client=mock_client))

    assert isinstance(result, AgentInvestigation)
    assert result.zone_id == "ZONE-TEST-AI"
    assert result.risk_level == "HIGH"
    assert result.confidence == 0.85
    assert result.ai_available is True
    assert len(result.evidence) == 0
    assert len(result.recommendations) == 1


def test_single_tool_execution_flow(test_db):
    """Tests multi-step flow: model requests run_water_balance -> tool executes -> model summarizes."""
    final_payload = {
        "zone_id": "ZONE-TEST-AI",
        "risk_level": "CRITICAL",
        "likely_cause": "physical_leakage",
        "confidence": 0.90,
        "summary": "Water balance shows NRW over 50%. Immediate leak isolation needed.",
        "evidence": [
            {
                "source": "run_water_balance",
                "metric": "nrw_percentage",
                "value": 80.0,
                "unit": "%",
                "explanation": "Water loss exceeds acceptable threshold."
            }
        ],
        "recommendations": [
            {
                "action": "Deploy field maintenance crew",
                "priority": "URGENT",
                "reason": "Address active high-volume leak."
            }
        ],
        "missing_data": [],
        "ai_available": True
    }

    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = [
        make_tool_call_response("run_water_balance", {"zone_id": "ZONE-TEST-AI"}),
        make_text_response(json.dumps(final_payload)),
    ]

    req = InvestigationRequest(zone_id="ZONE-TEST-AI", question="Inspect zone losses")
    result = asyncio.run(investigate(req, db=test_db, client=mock_client))

    assert result.ai_available is True
    assert result.risk_level == "CRITICAL"
    assert mock_client.chat.completions.create.call_count == 2


def test_multiple_tool_calls_in_single_turn(test_db):
    """Tests model requesting multiple tools simultaneously (water balance + MNF + PPA)."""
    final_payload = {
        "zone_id": "ZONE-TEST-AI",
        "risk_level": "HIGH",
        "likely_cause": "physical_and_apparent_loss",
        "confidence": 0.88,
        "summary": "Combined physical leakage and candidate pipe drop identified.",
        "evidence": [
            {
                "source": "run_water_balance",
                "metric": "loss_litres",
                "value": 80000.0,
                "unit": "L",
                "explanation": "Gross balance loss"
            },
            {
                "source": "run_ppa (SIMULATED)",
                "metric": "pressure_drop_bar",
                "value": 0.75,
                "unit": "bar",
                "explanation": "Simulated PPA candidate leak at Node 3"
            }
        ],
        "recommendations": [
            {
                "action": "Acoustic confirmation at Node 3",
                "priority": "HIGH",
                "reason": "Confirm simulated pressure anomaly"
            }
        ],
        "missing_data": [],
        "ai_available": True
    }

    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = [
        make_multi_tool_call_response([
            ("run_water_balance", {"zone_id": "ZONE-TEST-AI"}, "call_wb"),
            ("run_mnf", {"zone_id": "ZONE-TEST-AI"}, "call_mnf"),
            ("run_ppa", {"zone_id": "ZONE-TEST-AI"}, "call_ppa"),
        ]),
        make_text_response(json.dumps(final_payload)),
    ]

    req = InvestigationRequest(zone_id="ZONE-TEST-AI")
    result = asyncio.run(investigate(req, db=test_db, client=mock_client))

    assert result.ai_available is True
    assert result.confidence == 0.88
    assert mock_client.chat.completions.create.call_count == 2


def test_invalid_llm_json_triggers_fallback():
    """Tests that unparseable or malformed output from Groq safely falls back without crashing."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = make_text_response("Sorry, I could not generate JSON.")

    req = InvestigationRequest(zone_id="ZONE-TEST-AI")
    result = asyncio.run(investigate(req, client=mock_client))

    assert result.ai_available is False
    assert result.risk_level == "UNKNOWN"
    assert result.confidence == 0.0
    assert "unvalidated structure" in result.summary or "unparseable" in result.summary


def test_groq_api_exception_triggers_fallback():
    """Tests that network or Groq API exceptions safely return fallback investigation."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Groq rate limit exceeded (429)")

    req = InvestigationRequest(zone_id="ZONE-TEST-AI")
    result = asyncio.run(investigate(req, client=mock_client))

    assert result.ai_available is False
    assert result.risk_level == "UNKNOWN"
    assert "temporarily unavailable" in result.summary


def test_missing_groq_api_key_triggers_fallback():
    """Tests that missing GROQ_API_KEY environment variable triggers clean fallback without error."""
    with patch.dict(os.environ, {}, clear=True):
        req = InvestigationRequest(zone_id="ZONE-NO-KEY")
        result = asyncio.run(investigate(req, client=None))

        assert result.ai_available is False
        assert result.zone_id == "ZONE-NO-KEY"
        assert "GROQ_API_KEY is not configured" in result.summary


def test_max_tool_rounds_exceeded_triggers_fallback(test_db):
    """Tests that runaway tool calling loops terminate at MAX_TOOL_ROUNDS with clean fallback."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = make_tool_call_response(
        "run_water_balance", {"zone_id": "ZONE-TEST-AI"}
    )

    req = InvestigationRequest(zone_id="ZONE-TEST-AI")
    result = asyncio.run(investigate(req, db=test_db, client=mock_client))

    assert result.ai_available is False
    assert mock_client.chat.completions.create.call_count == MAX_TOOL_ROUNDS
    assert f"maximum tool iterations ({MAX_TOOL_ROUNDS})" in result.summary


def test_ppa_tool_direct_simulated_attribute(test_db):
    """Verifies that run_ppa tool execution always returns is_simulated=True."""
    ppa_res = execute_tool("run_ppa", {"zone_id": "ZONE-TEST-AI"}, db=test_db)
    assert ppa_res["status"] == "SUCCESS"
    assert ppa_res["is_simulated"] is True


def test_no_localhost_http_calls_in_agent_code():
    """Static analysis verifying no localhost HTTP requests exist in agent code."""
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    app_agent_dir = os.path.join(agent_dir, "..", "app", "agent")

    # Check for actual network call expressions to localhost
    disallowed_patterns = [
        "http://localhost",
        "http://127.0.0.1",
        "https://localhost",
        "https://127.0.0.1",
        "requests.get",
        "requests.post",
        "httpx.get",
        "httpx.post",
        "urllib.request",
    ]

    for filename in os.listdir(app_agent_dir):
        if filename.endswith(".py"):
            filepath = os.path.join(app_agent_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                for pattern in disallowed_patterns:
                    assert pattern not in content, f"Disallowed HTTP/network pattern '{pattern}' found in {filename}"


def test_hallucinated_evidence_triggers_fallback():
    """Tests that if the LLM returns evidence for a tool it didn't execute, it triggers a fallback."""
    final_payload = {
        "zone_id": "ZONE-TEST-AI",
        "risk_level": "HIGH",
        "likely_cause": "physical_leakage",
        "confidence": 0.85,
        "summary": "Zone exhibits significant physical losses.",
        "evidence": [
            {
                "source": "run_ppa (SIMULATED)",
                "metric": "pressure_drop",
                "value": 1.2,
                "unit": "bar",
                "explanation": "Hallucinated PPA result"
            }
        ],
        "recommendations": [],
        "missing_data": [],
        "ai_available": True
    }
    
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = make_text_response(json.dumps(final_payload))

    req = InvestigationRequest(zone_id="ZONE-TEST-AI")
    result = asyncio.run(investigate(req, client=mock_client))
    
    assert result.ai_available is False
    assert "unvalidated structure" in result.summary
