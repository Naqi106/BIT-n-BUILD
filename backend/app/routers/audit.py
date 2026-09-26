from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.app.db import get_db
from backend.data.db_schema import BillingRecord, Zone
from backend.app.models import PaginatedBillingAudit, BillingAuditItem, PPAAuditItem

router = APIRouter(prefix="/audit", tags=["Audits"])

@router.get("/billing/{zone_id}", response_model=PaginatedBillingAudit)
def get_billing_audit(
    zone_id: str,
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Returns ranked theft/tampering candidates for a zone with pagination.
    Flagged where billed consumption is significantly below property benchmark.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    query = db.query(BillingRecord).filter(BillingRecord.zone_id == zone_id)
    total_records = query.count()
    total_anomalies = query.filter(BillingRecord.is_anomaly == True).count()

    records = query.order_by(BillingRecord.anomaly_score.desc()).offset(offset).limit(limit).all()

    items = [
        BillingAuditItem(
            consumer_id=r.consumer_id,
            household_size=r.household_size,
            property_type=r.property_type,
            billed_litres=r.billed_litres,
            benchmark_litres=r.benchmark_litres,
            suspicion_score=round(r.anomaly_score, 2),
            is_anomaly=r.is_anomaly
        ) for r in records
    ]

    return PaginatedBillingAudit(
        total_records=total_records,
        total_anomalies=total_anomalies,
        limit=limit,
        offset=offset,
        items=items
    )

@router.get("/ppa/{zone_id}", response_model=List[PPAAuditItem])
def get_ppa_leak_location(zone_id: str, db: Session = Depends(get_db)):
    """
    Simulated Pressure Profile Analysis (PPA) leak location narrowing.
    Per solution doc, Level-1 hardware is simulated for 24-hr build,
    so 'is_simulated = True' is explicitly declared per roadmap.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        # Default baseline if zone hasn't been seeded yet
        base_pressure = 2.5
        pipe_len = 8.0
    else:
        base_pressure = zone.avg_pressure_bar or 2.5
        pipe_len = zone.pipe_length_km or 8.0

    nodes = []
    for i in range(1, 6):
        dist = round((pipe_len / 5.0) * i, 2)
        drop = 0.75 if i == 3 else round(0.05 * i, 2)
        observed = max(0.5, round(base_pressure - drop, 2))
        prob = 0.88 if i == 3 else round(0.10 + (i * 0.05), 2)

        nodes.append(PPAAuditItem(
            node_id=f"NODE-{zone_id}-{i:02d}",
            distance_from_source_km=dist,
            baseline_pressure_bar=base_pressure,
            observed_pressure_bar=observed,
            pressure_drop_bar=drop,
            leak_probability=prob,
            is_simulated=True
        ))
    return nodes

if __name__ == "__main__":
    print("Audit router created successfully!")