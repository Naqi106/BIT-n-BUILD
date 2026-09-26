from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
import pandas as pd

from backend.app.db import get_db
from backend.data.db_schema import BillingRecord, Zone
from backend.app.models import PaginatedBillingAudit, BillingAuditItem, PPAAuditItem
from backend.app.engines.ml_billing_anomaly import (
    FLAG_THRESHOLD,
    get_detector,
    is_anomaly as ml_is_anomaly,
)

router = APIRouter(prefix="/audit", tags=["Audits"])


@router.get("/billing/{zone_id}", response_model=PaginatedBillingAudit)
def get_billing_audit(
    zone_id: str,
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Returns ranked theft/tampering candidates for a zone.

    Detection method: Isolation Forest (primary) or rule-based fallback
    (billed < 60% of benchmark) when the model is not yet trained.
    Results are re-scored live by the ML model so scores are always fresh.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    all_records = db.query(BillingRecord).filter(BillingRecord.zone_id == zone_id).all()
    total_records = len(all_records)

    detector = get_detector()

    # Re-score every record with the current ML model
    if detector and detector.is_trained and all_records:
        df = pd.DataFrame([{
            "billed_litres": r.billed_litres,
            "benchmark_litres": r.benchmark_litres,
            "household_size": r.household_size or 4,
        } for r in all_records])
        ml_scores = detector.predict_anomaly(df)
    else:
        # Fallback: use stored rule-based anomaly_score column
        ml_scores = [r.anomaly_score for r in all_records]

    # Attach scores and sort descending (highest anomaly first)
    scored = sorted(
        zip(all_records, ml_scores),
        key=lambda x: x[1],
        reverse=True
    )

    total_anomalies = sum(1 for _, s in scored if s >= FLAG_THRESHOLD)

    # Paginate
    page = scored[offset: offset + limit]

    items = []
    for rec, score in page:
        _, expl = ml_is_anomaly(
            billed=rec.billed_litres,
            benchmark=rec.benchmark_litres,
            household_size=rec.household_size or 4,
        )
        items.append(BillingAuditItem(
            consumer_id=rec.consumer_id,
            household_size=rec.household_size,
            property_type=rec.property_type,
            billed_litres=rec.billed_litres,
            benchmark_litres=rec.benchmark_litres,
            suspicion_score=round(float(score), 3),
            is_anomaly=(float(score) >= FLAG_THRESHOLD),
        ))

    return PaginatedBillingAudit(
        total_records=total_records,
        total_anomalies=total_anomalies,
        limit=limit,
        offset=offset,
        items=items,
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
