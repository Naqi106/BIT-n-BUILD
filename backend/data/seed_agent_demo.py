"""
Synthetic Demo Data Seeder for AltoMare AI Agent E2E Validation.

Creates and populates an isolated local SQLite database at:
backend/data/agent_demo.db

Zone: ZONE-DEMO-01 (SYNTHETIC DEMO DATASET)
Contains:
- 1 synthetic municipal zone
- Inflow & Minimum Night Flow telemetry readings
- 25 synthetic consumer billing records (21 normal, 4 anomalous)

DOES NOT modify production or remote databases.
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.data.db_schema import Zone, RawReading, BillingRecord

DEMO_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent_demo.db"))
DEMO_DB_URL = f"sqlite:///{DEMO_DB_PATH}"


def get_demo_engine():
    return create_engine(DEMO_DB_URL, connect_args={"check_same_thread": False})


def seed_demo_data():
    """Seeds a dedicated, repeatable synthetic dataset into agent_demo.db."""
    engine = get_demo_engine()
    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    try:
        # Clear existing demo zone records for repeatability
        db.query(BillingRecord).filter(BillingRecord.zone_id == "ZONE-DEMO-01").delete()
        db.query(RawReading).filter(RawReading.zone_id == "ZONE-DEMO-01").delete()
        db.query(Zone).filter(Zone.id == "ZONE-DEMO-01").delete()
        db.commit()

        # 1. Synthetic Zone
        zone = Zone(
            id="ZONE-DEMO-01",
            name="Demo Ward 01 (Synthetic)",
            pipe_length_km=12.0,
            connection_count=800,
            avg_pressure_bar=2.7,
            tariff_rate=0.005,  # ₹ 5 per kL
            data_level=1,
        )
        db.add(zone)

        # 2. Synthetic Telemetry
        reading = RawReading(
            zone_id="ZONE-DEMO-01",
            timestamp=datetime.utcnow(),
            inflow_litres=100000.0,
            night_flow_litres=3500.0,  # 2-4 AM night flow
            pressure_bar=2.4,
        )
        db.add(reading)

        # 3. Synthetic Billing Records (25 total: 21 normal, 4 anomalous)
        billing_data = [
            # 21 Normal Consumer Accounts
            ("DEMO-C001", 4, "residential", 2050.0, 2000.0, 0.03, False),
            ("DEMO-C002", 3, "residential", 1520.0, 1500.0, 0.02, False),
            ("DEMO-C003", 5, "residential", 2480.0, 2500.0, 0.04, False),
            ("DEMO-C004", 4, "residential", 1990.0, 2000.0, 0.01, False),
            ("DEMO-C005", 6, "residential", 3100.0, 3000.0, 0.05, False),
            ("DEMO-C006", 4, "residential", 2020.0, 2000.0, 0.02, False),
            # Suspect Anomaly 1: Severely under-billed residential
            ("DEMO-C007-SUSPECT", 5, "residential", 120.0, 2500.0, 0.95, True),
            ("DEMO-C008", 4, "residential", 1950.0, 2000.0, 0.03, False),
            ("DEMO-C009", 3, "residential", 1480.0, 1500.0, 0.02, False),
            ("DEMO-C010", 4, "residential", 2100.0, 2000.0, 0.06, False),
            ("DEMO-C011", 5, "residential", 2550.0, 2500.0, 0.03, False),
            ("DEMO-C012", 4, "residential", 1980.0, 2000.0, 0.02, False),
            # Suspect Anomaly 2: Low-consumption meter tampering indicator
            ("DEMO-C013-SUSPECT", 6, "residential", 190.0, 3000.0, 0.92, True),
            ("DEMO-C014", 3, "residential", 1530.0, 1500.0, 0.03, False),
            ("DEMO-C015", 4, "residential", 2010.0, 2000.0, 0.01, False),
            ("DEMO-C016", 5, "residential", 2490.0, 2500.0, 0.02, False),
            ("DEMO-C017", 4, "residential", 2040.0, 2000.0, 0.03, False),
            ("DEMO-C018", 3, "residential", 1470.0, 1500.0, 0.04, False),
            # Suspect Anomaly 3: Near-zero bypass candidate
            ("DEMO-C019-SUSPECT", 4, "residential", 65.0, 2000.0, 0.97, True),
            ("DEMO-C020", 5, "residential", 2520.0, 2500.0, 0.02, False),
            ("DEMO-C021", 4, "residential", 1970.0, 2000.0, 0.02, False),
            ("DEMO-C022", 6, "residential", 2980.0, 3000.0, 0.03, False),
            ("DEMO-C023", 4, "residential", 2030.0, 2000.0, 0.02, False),
            # Suspect Anomaly 4: High benchmark commercial account heavily under-reporting
            ("DEMO-C024-COMMERCIAL-SUSPECT", 8, "commercial", 450.0, 5000.0, 0.91, True),
            ("DEMO-C025", 4, "residential", 2000.0, 2000.0, 0.01, False),
        ]

        for cid, size, ptype, billed, bench, score, anomaly in billing_data:
            rec = BillingRecord(
                zone_id="ZONE-DEMO-01",
                consumer_id=cid,
                household_size=size,
                property_type=ptype,
                billed_litres=billed,
                benchmark_litres=bench,
                anomaly_score=score,
                is_anomaly=anomaly,
                billing_period="2026-DEMO-Q1",
            )
            db.add(rec)

        db.commit()
        print(f"[DEMO SEED] Successfully populated isolated database: {DEMO_DB_PATH}")
        print(f"[DEMO SEED] Zone: ZONE-DEMO-01 (1 zone, 1 telemetry reading, {len(billing_data)} billing records)")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
