from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from backend.app.db import Base, engine

class Zone(Base):
    __tablename__ = "zones"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    pipe_length_km = Column(Float, default=10.0)
    connection_count = Column(Integer, default=500)
    avg_pressure_bar = Column(Float, default=2.5)
    tariff_rate = Column(Float, default=0.005)  # ₹ per litre, customizable per zone
    data_level = Column(Integer, default=0)     # 0: Manual, 1: Partial IoT, 2: SCADA

    readings = relationship("RawReading", back_populates="zone", cascade="all, delete-orphan")
    alerts = relationship("LeakAlert", back_populates="zone", cascade="all, delete-orphan")

class RawReading(Base):
    __tablename__ = "raw_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    inflow_litres = Column(Float, nullable=False)
    night_flow_litres = Column(Float, nullable=True) # 2-4 AM Minimum Night Flow
    pressure_bar = Column(Float, nullable=True)

    zone = relationship("Zone", back_populates="readings")

class LeakAlert(Base):
    __tablename__ = "leak_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(String(20), default="MEDIUM") # LOW, MEDIUM, HIGH, CRITICAL
    estimated_loss_litres = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False) # Dynamic calculation (0.0 to 1.0)
    detection_methods = Column(String(100), nullable=False) # e.g. "water_balance,mnf,uarl"
    status = Column(String(20), default="ACTIVE") # ACTIVE, INVESTIGATING, RESOLVED
    details = Column(Text, nullable=True)

    zone = relationship("Zone", back_populates="alerts")

class BillingRecord(Base):
    __tablename__ = "billing_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    consumer_id = Column(String(50), nullable=False, index=True)
    household_size = Column(Integer, default=4)
    property_type = Column(String(50), default="residential")
    billed_litres = Column(Float, nullable=False)
    benchmark_litres = Column(Float, nullable=False)
    anomaly_score = Column(Float, default=0.0)
    is_anomaly = Column(Boolean, default=False)
    billing_period = Column(String(20), default="2026-Q1")

class RevenueLog(Base):
    __tablename__ = "revenue_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    alert_id = Column(Integer, ForeignKey("leak_alerts.id"), nullable=True)
    litres_recovered = Column(Float, nullable=False)
    tariff_rate = Column(Float, nullable=False)
    revenue_recovered = Column(Float, nullable=False) # litres * tariff_rate
    recovered_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

#3 new tables
class NRWSnapshot(Base):
    """Stores historical snapshots of NRW % so frontend charts show real history."""
    __tablename__ = "nrw_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    nrw_percentage = Column(Float, nullable=False)
    inflow_litres = Column(Float, nullable=False)
    billed_litres = Column(Float, nullable=False)
    loss_litres = Column(Float, nullable=False)

class ActionLog(Base):
    """Tracks officer approvals and resolutions for AI recommendations."""
    __tablename__ = "action_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    alert_id = Column(Integer, ForeignKey("leak_alerts.id"), nullable=True)
    action_type = Column(String(100), nullable=False) 
    status = Column(String(20), default="PENDING")   # PENDING, APPROVED, REJECTED, RESOLVED
    urgency = Column(String(20), default="MEDIUM")   # LOW, MEDIUM, HIGH, URGENT
    estimated_cost = Column(Float, default=0.0)      # ₹
    estimated_payback_days = Column(Float, default=0.0)
    officer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class InvestigationMemory(Base):
    """Provides memory of past incidents, repairs, and outcomes per zone."""
    __tablename__ = "investigation_memory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone_id = Column(String(50), ForeignKey("zones.id"), nullable=False)
    summary = Column(Text, nullable=False)
    action_taken = Column(String(255), nullable=True)
    outcome = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")