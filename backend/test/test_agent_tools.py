"""
Unit & Integration Tests for AltoMare Agent Tools (Block 2)
Tests run_water_balance, run_mnf, run_uarl, run_billing_anomaly, run_ppa,
and get_correlation_status using an isolated SQLite database.
"""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.data.db_schema import Zone, RawReading, BillingRecord
from backend.app.agent.tools import (
    run_water_balance,
    run_mnf,
    run_uarl,
    run_ppa,
    run_billing_anomaly,
    get_correlation_status,
)


@pytest.fixture(scope="session")
def test_db():
    """Sets up an isolated in-memory SQLite database seeded with test scenarios."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    # 1. Standard zone with complete telemetry & billing
    zone_complete = Zone(
        id="ZONE-COMPLETE",
        name="Complete Telemetry Ward",
        pipe_length_km=15.0,
        connection_count=800,
        avg_pressure_bar=3.0,
        tariff_rate=0.005,
    )
    session.add(zone_complete)

    reading_complete = RawReading(
        zone_id="ZONE-COMPLETE",
        inflow_litres=120000.0,
        night_flow_litres=3500.0,
        pressure_bar=2.9,
    )
    session.add(reading_complete)

    # Billing records: 1 anomaly, 1 normal
    session.add(BillingRecord(
        zone_id="ZONE-COMPLETE",
        consumer_id="CONS-SUSPECT-01",
        household_size=4,
        property_type="residential",
        billed_litres=12000.0,
        benchmark_litres=25000.0,
        anomaly_score=0.92,
        is_anomaly=True,
    ))
    session.add(BillingRecord(
        zone_id="ZONE-COMPLETE",
        consumer_id="CONS-NORMAL-02",
        household_size=4,
        property_type="residential",
        billed_litres=26000.0,
        benchmark_litres=25000.0,
        anomaly_score=0.05,
        is_anomaly=False,
    ))

    # 2. Zone with missing night-flow telemetry (night_flow is None)
    zone_no_mnf = Zone(
        id="ZONE-NO-MNF",
        name="No MNF Ward",
        pipe_length_km=10.0,
        connection_count=400,
        avg_pressure_bar=2.0,
    )
    session.add(zone_no_mnf)

    reading_no_mnf = RawReading(
        zone_id="ZONE-NO-MNF",
        inflow_litres=80000.0,
        night_flow_litres=None,
        pressure_bar=2.0,
    )
    session.add(reading_no_mnf)

    # 3. Zone with empty billing records
    zone_empty_bill = Zone(
        id="ZONE-EMPTY-BILL",
        name="Empty Billing Ward",
        pipe_length_km=8.0,
        connection_count=300,
        avg_pressure_bar=2.5,
    )
    session.add(zone_empty_bill)

    session.commit()
    yield session
    session.close()


def test_water_balance_valid(test_db):
    """Test run_water_balance with valid inflow and billing records."""
    res = run_water_balance("ZONE-COMPLETE", db=test_db)
    assert res["status"] == "SUCCESS"
    assert res["data_source"] == "TELEMETRY"
    assert res["inflow_litres"] == 120000.0
    assert res["billed_litres"] == 38000.0  # 12000 + 26000
    assert res["loss_litres"] == 82000.0   # 120000 - 38000
    assert res["nrw_percentage"] == 68.33
    assert res["severity"] == "CRITICAL"
    assert res["is_leak_detected"] is True
    assert res["zone_id"] == "ZONE-COMPLETE"


def test_water_balance_no_telemetry(test_db):
    """Test run_water_balance for a non-existent zone gracefully returns NO_DATA."""
    res = run_water_balance("NON-EXISTENT-ZONE", db=test_db)
    assert res["status"] == "NO_DATA"
    assert res["data_source"] == "NO_DATA"
    assert res["inflow_litres"] == 0.0
    assert res["loss_litres"] == 0.0


def test_mnf_valid(test_db):
    """Test run_mnf when valid night flow telemetry exists."""
    res = run_mnf("ZONE-COMPLETE", db=test_db)
    assert res["status"] == "SUCCESS"
    assert res["has_night_flow_data"] is True
    assert res["night_flow_litres"] == 3500.0
    assert res["estimated_daily_leakage_litres"] > 0.0
    # Expected formula check: (3500 * (1 - 0.15)) / 2 * 24 = 35700.0
    assert res["estimated_daily_leakage_litres"] == 35700.0


def test_mnf_missing_telemetry(test_db):
    """Test run_mnf when night flow telemetry is absent returns NO_TELEMETRY without faking 0."""
    res = run_mnf("ZONE-NO-MNF", db=test_db)
    assert res["status"] == "NO_TELEMETRY"
    assert res["has_night_flow_data"] is False
    assert res["estimated_daily_leakage_litres"] == 0.0


def test_uarl_valid_zone(test_db):
    """Test run_uarl with valid zone infrastructure metrics and ILI calculation."""
    res = run_uarl("ZONE-COMPLETE", current_real_loss_litres=45000.0, db=test_db)
    assert res["status"] == "SUCCESS"
    assert res["pipe_length_km"] == 15.0
    assert res["connection_count"] == 800
    assert res["avg_pressure_bar"] == 3.0
    assert res["uarl_litres_per_day"] > 0.0
    assert res["infrastructure_leakage_index"] is not None
    assert res["infrastructure_leakage_index"] > 0.0


def test_uarl_non_existent_zone(test_db):
    """Test run_uarl returns NO_DATA for unknown zone."""
    res = run_uarl("UNKNOWN-ZONE", db=test_db)
    assert res["status"] == "NO_DATA"
    assert res["uarl_litres_per_day"] == 0.0
    assert res["infrastructure_leakage_index"] is None


def test_ppa_is_simulated(test_db):
    """Test run_ppa extracts suspect node and explicitly declares is_simulated=True."""
    res = run_ppa("ZONE-COMPLETE", db=test_db)
    assert res["status"] == "SUCCESS"
    assert res["is_simulated"] is True
    assert res["highest_probability_node"].startswith("NODE-ZONE-COMPLETE")
    assert res["leak_probability"] > 0.5
    assert res["total_nodes_evaluated"] == 5
    assert res["pressure_drop_bar"] > 0.0


def test_billing_anomaly_empty(test_db):
    """Test run_billing_anomaly when zone has zero billing records returns NO_DATA."""
    res = run_billing_anomaly("ZONE-EMPTY-BILL", db=test_db)
    assert res["status"] == "NO_DATA"
    assert res["total_accounts_audited"] == 0
    assert res["anomaly_count"] == 0
    assert res["anomaly_rate_pct"] == 0.0
    assert res["estimated_unbilled_litres"] == 0.0
    assert res["top_suspicious_consumer_ids"] == []


def test_billing_anomaly_with_anomalies(test_db):
    """Test run_billing_anomaly aggregates accounts, flags anomalies, and identifies top suspects."""
    res = run_billing_anomaly("ZONE-COMPLETE", db=test_db)
    assert res["status"] == "SUCCESS"
    assert res["total_accounts_audited"] == 2
    assert res["anomaly_count"] == 1
    assert res["anomaly_rate_pct"] == 50.0
    assert res["estimated_unbilled_litres"] == 13000.0  # 25000 benchmark - 12000 billed
    assert res["top_suspicious_consumer_ids"] == ["CONS-SUSPECT-01"]


def test_correlation_returns_not_available(test_db):
    """Test get_correlation_status safely returns NOT_AVAILABLE without fabricating fake data."""
    res = get_correlation_status("ZONE-COMPLETE", db=test_db)
    assert res["status"] == "NOT_AVAILABLE"
    assert res["correlation_detected"] is False
    assert res["risk_level"] == "NONE"
    assert res["water_quality_events"] == 0
    assert res["is_simulated"] is False
    assert "No water-quality data source" in res["details"]


def test_all_tools_json_safe(test_db):
    """Test that all tool return values serialize to JSON cleanly with only primitive types."""
    tools_outputs = [
        run_water_balance("ZONE-COMPLETE", db=test_db),
        run_water_balance("NON-EXISTENT", db=test_db),
        run_mnf("ZONE-COMPLETE", db=test_db),
        run_mnf("ZONE-NO-MNF", db=test_db),
        run_uarl("ZONE-COMPLETE", current_real_loss_litres=20000.0, db=test_db),
        run_ppa("ZONE-COMPLETE", db=test_db),
        run_billing_anomaly("ZONE-COMPLETE", db=test_db),
        run_billing_anomaly("ZONE-EMPTY-BILL", db=test_db),
        get_correlation_status("ZONE-COMPLETE", db=test_db),
    ]

    for output in tools_outputs:
        assert isinstance(output, dict)
        # Verify JSON serializability
        serialized = json.dumps(output)
        assert isinstance(serialized, str)
        # Ensure no ORM or complex objects
        for key, val in output.items():
            assert type(val) in (int, float, str, bool, list, type(None)), f"Non-primitive type in key '{key}': {type(val)}"
