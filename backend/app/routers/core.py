from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional

from backend.app.db import get_db
from backend.data.db_schema import Zone, RawReading, LeakAlert, BillingRecord, RevenueLog, NRWSnapshot
from backend.app.models import (
    ZoneResponse, ZoneCreate, ReadingCreate, ReadingResponse,
    LeakAlertResponse, PaybackResponse, RevenueLogResponse, NRWSnapshotResponse
)
from backend.app.engines.latias import process_zone
from backend.app.engines.revenue import calculate_payback_period

router = APIRouter(tags=["Core Operations"])

@router.get("/zones", response_model=List[ZoneResponse])
def get_zones(db: Session = Depends(get_db)):
    """Returns list of all municipal zones."""
    return db.query(Zone).all()

@router.post("/zones", response_model=ZoneResponse)
def create_zone(zone: ZoneCreate, db: Session = Depends(get_db)):
    """Creates a new municipal zone."""
    existing = db.query(Zone).filter(Zone.id == zone.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Zone ID already exists.")
    db_zone = Zone(**zone.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone

@router.post("/readings", response_model=ReadingResponse)
def post_reading(reading: ReadingCreate, db: Session = Depends(get_db)):
    """Ingests flow/pressure reading for a zone."""
    zone = db.query(Zone).filter(Zone.id == reading.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found.")
    
    db_reading = RawReading(
        zone_id=reading.zone_id,
        inflow_litres=reading.inflow_litres,
        night_flow_litres=reading.night_flow_litres,
        pressure_bar=reading.pressure_bar
    )
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading

@router.post("/detect/{zone_id}", response_model=Dict[str, Any])
def trigger_detection(zone_id: str, db: Session = Depends(get_db)):
    """Triggers Latias multi-method detection engine."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found.")

    latest_reading = db.query(RawReading).filter(RawReading.zone_id == zone_id).order_by(RawReading.timestamp.desc()).first()
    has_real_reading = latest_reading is not None
    inflow = latest_reading.inflow_litres if has_real_reading else 100000.0
    night_flow = latest_reading.night_flow_litres if has_real_reading else None
    readings_count = db.query(RawReading).filter(RawReading.zone_id == zone_id).count()

    # Prefer the zone's latest weekly balance snapshot -- the same rows the
    # Dashboard, the trend chart and the Copilot agent read. The legacy path
    # below compares daily inflow against the household billing SAMPLE,
    # which overstated loss severalfold and tripped is_leak_detected on
    # every zone (a stray /detect call would have written bogus alerts).
    snapshot = (
        db.query(NRWSnapshot)
        .filter(NRWSnapshot.zone_id == zone_id)
        .order_by(NRWSnapshot.timestamp.desc())
        .first()
    )
    if snapshot is not None and float(snapshot.inflow_litres or 0.0) > 0:
        inflow = float(snapshot.inflow_litres)
        billed_litres = float(snapshot.billed_litres)
        is_fallback = False
        data_source = "WEEKLY_SNAPSHOT"
    else:
        billed_sum = db.query(func.sum(BillingRecord.billed_litres)).filter(BillingRecord.zone_id == zone_id).scalar()
        has_real_billing = billed_sum is not None
        billed_litres = billed_sum if has_real_billing else (inflow * 0.45)
        is_fallback = not (has_real_reading and has_real_billing)
        data_source = "DEFAULT_FALLBACK" if is_fallback else "TELEMETRY"

    result = process_zone(
        zone_id=zone_id,
        inflow_litres=inflow,
        billed_litres=billed_litres,
        night_flow_litres=night_flow,
        pipe_length_km=zone.pipe_length_km,
        connection_count=zone.connection_count,
        avg_pressure_bar=zone.avg_pressure_bar,
        readings_count=max(readings_count, 1)
    )

    result["is_simulated"] = is_fallback
    result["data_source"] = data_source

    if is_fallback:
        result["details"] = f"[DEFAULT FALLBACK DATA - NOT REAL TELEMETRY] {result['details']}"

    if result["is_leak_detected"]:
        alert = LeakAlert(
            zone_id=zone_id,
            severity=result["severity"],
            estimated_loss_litres=result["estimated_loss_litres"],
            confidence_score=result["confidence_score"],
            detection_methods=result["detection_methods"],
            status="ACTIVE",
            details=result["details"]
        )
        db.add(alert)
        db.commit()
        result["alert_id"] = alert.id

    return result

@router.get("/alerts", response_model=List[LeakAlertResponse])
def get_alerts(zone_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieves leak alerts."""
    query = db.query(LeakAlert)
    if zone_id:
        query = query.filter(LeakAlert.zone_id == zone_id)
    return query.order_by(LeakAlert.timestamp.desc()).all()

@router.get("/revenue/payback/{zone_id}", response_model=PaybackResponse)
def get_payback(zone_id: str, db: Session = Depends(get_db)):
    """Exposes payback period calculation via API (Roadmap Hour 2-4)."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found.")

    latest_alert = db.query(LeakAlert).filter(LeakAlert.zone_id == zone_id, LeakAlert.status == "ACTIVE").first()
    is_fallback = latest_alert is None
    daily_loss = latest_alert.estimated_loss_litres if latest_alert else 25000.0

    res = calculate_payback_period(
        daily_loss_litres=daily_loss,
        tariff_rate=zone.tariff_rate
    )
    return PaybackResponse(
        zone_id=zone_id,
        is_simulated=is_fallback,
        data_source="DEFAULT_FALLBACK" if is_fallback else "ACTIVE_ALERT",
        **res
    )

@router.get("/revenue/summary", response_model=List[RevenueLogResponse])
def get_revenue_summary(db: Session = Depends(get_db)):
    """Returns list of recovered revenue transactions."""
    return db.query(RevenueLog).order_by(RevenueLog.recovered_at.desc()).all()

@router.get("/nrw/summary", response_model=List[NRWSnapshotResponse])
def get_nrw_summary(db: Session = Depends(get_db)):
    """Returns NRW historical snapshots for frontend trend charts."""
    return db.query(NRWSnapshot).order_by(NRWSnapshot.timestamp.asc()).all()

if __name__ == "__main__":
    print("Core router created successfully!")