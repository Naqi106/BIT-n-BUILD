import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import Base, engine, SessionLocal
from backend.data.db_schema import Zone

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Create sample demo zone if not present
    if not db.query(Zone).filter(Zone.id == "ZONE-TEST").first():
        db.add(Zone(id="ZONE-TEST", name="Test Zone", pipe_length_km=12.0, connection_count=600, tariff_rate=0.005))
        db.commit()
    db.close()

def test_get_zones():
    res = client.get("/zones")
    assert res.status_code == 200
    assert len(res.json()) >= 1

def test_trigger_detection():
    res = client.post("/detect/ZONE-TEST")
    assert res.status_code == 200
    data = res.json()
    assert "confidence_score" in data
    assert data["confidence_score"] != 0.7  # Must be dynamic!
    assert "uarl_baseline_litres" in data

def test_payback_endpoint():
    res = client.get("/revenue/payback/ZONE-TEST")
    assert res.status_code == 200
    data = res.json()
    assert "payback_period_days" in data

def test_audit_endpoints():
    res_billing = client.get("/audit/billing/ZONE-TEST")
    assert res_billing.status_code == 200

    res_ppa = client.get("/audit/ppa/ZONE-TEST")
    assert res_ppa.status_code == 200
    assert res_ppa.json()[0]["is_simulated"] is True

def test_action_lifecycle_and_auto_revenue():
    # 1. Create action
    create_res = client.post("/actions/create", json={
        "zone_id": "ZONE-TEST",
        "action_type": "Pipe repair",
        "urgency": "HIGH",
        "estimated_cost": 30000.0,
        "estimated_payback_days": 15.0
    })
    assert create_res.status_code == 200
    action_id = create_res.json()["id"]

    # 2. Approve action
    app_res = client.post(f"/actions/approve/{action_id}")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # 3. Resolve action -> auto-generates revenue log
    res_res = client.post(f"/actions/resolve/{action_id}")
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"

    # 4. Verify revenue log populated
    rev_res = client.get("/revenue/summary")
    assert rev_res.status_code == 200
    assert len(rev_res.json()) >= 1