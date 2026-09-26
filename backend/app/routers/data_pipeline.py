"""
DATA PIPELINE ROUTER -- Person 1 (Data + ML)

Endpoints:
  POST /data/upload-csv     -- bulk ingest of readings or billing data via CSV
  GET  /data/town-profile   -- returns the real Lucknow anchor figures with source citation

CSV upload supports two file types (detected by column headers):
  1. readings  -- columns: zone_id, inflow_litres, timestamp
                  optional: night_flow_litres, pressure_bar
  2. billing   -- columns: zone_id, consumer_id, billed_litres, benchmark_litres, billing_period
                  optional: household_size, property_type

Rows with unknown zone_ids, invalid values, or unparseable timestamps
are skipped with a warning -- the rest are inserted. Never crashes on
a single bad row.
"""

import io
from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db import get_db
from backend.data.db_schema import Zone, RawReading, BillingRecord
from backend.app.engines.ml_billing_anomaly import FALLBACK_RATIO
from backend.app.engines.trend_forecast import (
    forecast,
    load_town_snapshots,
    load_zone_snapshots,
)

router = APIRouter(prefix="/data", tags=["Data Pipeline"])


# ---------------------------------------------------------------------------
# Response models (local to this router, not in shared models.py)
# ---------------------------------------------------------------------------
class CSVUploadResult(BaseModel):
    readings_inserted: int
    billing_records_inserted: int
    warnings: List[str] = []


class TownProfile(BaseModel):
    town_name: str
    total_nrw_percent: float
    estimated_annual_loss_inr: float
    total_zones: int
    population_covered: int
    data_source: str
    anchor_source_citation: str


class NRWForecast(BaseModel):
    """
    30-day NRW projection (trend-forecasting model, Tier 1 optional).

    Numeric fields are null when is_sufficient=False — the endpoint then
    carries an explicit message instead of a fabricated number.
    """
    zone_id: Optional[str] = None
    is_sufficient: bool
    observations: int
    required_observations: Optional[int] = None
    message: Optional[str] = None
    method: Optional[str] = None
    window_days: Optional[float] = None
    horizon_days: Optional[int] = None
    tariff_rate: Optional[float] = None
    current_loss_litres_per_day: Optional[float] = None
    projected_loss_litres_per_day: Optional[float] = None
    loss_slope_litres_per_day_per_day: Optional[float] = None
    loss_change_pct: Optional[float] = None
    loss_r2: Optional[float] = None
    trend_confidence: Optional[str] = None
    direction: Optional[str] = None
    projected_loss_litres: Optional[float] = None
    projected_loss_rupees: Optional[float] = None
    current_nrw_pct: Optional[float] = None
    projected_nrw_pct: Optional[float] = None
    nrw_slope_pp_per_day: Optional[float] = None
    nrw_r2: Optional[float] = None
    interpretation: Optional[str] = None


# ---------------------------------------------------------------------------
# Real Lucknow anchor figures -- used by GET /data/town-profile
# Cited: AMRUT 2.0 MIS, Jal Shakti Ministry Annual Report 2024
# ---------------------------------------------------------------------------
LUCKNOW_PROFILE = TownProfile(
    town_name="Lucknow",
    total_nrw_percent=55.0,
    estimated_annual_loss_inr=650_737_500.0,   # Rs 650.7 million/yr (Rs 65 crore)
    total_zones=12,
    population_covered=3_495_000,
    data_source="AMRUT 2.0 MIS; Jal Shakti Ministry Annual Report 2024; LMC Water Audit 2023-24",
    anchor_source_citation=(
        "Ministry of Jal Shakti, Annual Report 2023-24, Table 4.3 (NRW by city); "
        "AMRUT 2.0 MIS Portal, Lucknow entry, accessed Sep 2026; "
        "LMC internal water audit, presented at AMRUT review, Mar 2024."
    ),
)


# ---------------------------------------------------------------------------
# CSV type detection
# ---------------------------------------------------------------------------
def _detect_csv_type(df: pd.DataFrame) -> str:
    cols = set(df.columns.str.strip().str.lower())
    if {"zone_id", "inflow_litres", "timestamp"}.issubset(cols):
        return "readings"
    if {"zone_id", "consumer_id", "billed_litres", "benchmark_litres", "billing_period"}.issubset(cols):
        return "billing"
    raise HTTPException(
        status_code=422,
        detail=(
            "CSV columns not recognised. "
            "For readings: zone_id, inflow_litres, timestamp (+ optional night_flow_litres, pressure_bar). "
            "For billing: zone_id, consumer_id, billed_litres, benchmark_litres, billing_period."
        ),
    )


# ---------------------------------------------------------------------------
# POST /data/upload-csv
# ---------------------------------------------------------------------------
@router.post("/upload-csv", response_model=CSVUploadResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV to bulk-insert zone readings or billing records.

    **readings CSV:** zone_id, inflow_litres, timestamp,
    night_flow_litres (optional), pressure_bar (optional)

    **billing CSV:** zone_id, consumer_id, billed_litres,
    benchmark_litres, billing_period, household_size (optional),
    property_type (optional)

    Bad rows are skipped with a warning -- valid rows always insert.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=422, detail="CSV file is empty.")

    df.columns = df.columns.str.strip().str.lower()
    csv_type = _detect_csv_type(df)

    # Get valid zone ids from DB
    valid_zone_ids = {z.id for z in db.query(Zone.id).all()}

    readings_inserted = 0
    billing_inserted = 0
    warnings = []

    if csv_type == "readings":
        for i, row in df.iterrows():
            row_num = i + 2
            try:
                zone_id = str(row["zone_id"]).strip()
                inflow = float(row["inflow_litres"])
                ts = pd.to_datetime(str(row["timestamp"]).strip()).to_pydatetime()

                if zone_id not in valid_zone_ids:
                    warnings.append(f"Row {row_num}: unknown zone_id '{zone_id}' -- skipped.")
                    continue
                if inflow < 0:
                    warnings.append(f"Row {row_num}: negative inflow_litres -- skipped.")
                    continue

                night_flow = float(row["night_flow_litres"]) if "night_flow_litres" in df.columns and pd.notna(row.get("night_flow_litres")) else None
                pressure = float(row["pressure_bar"]) if "pressure_bar" in df.columns and pd.notna(row.get("pressure_bar")) else None

                db.add(RawReading(
                    zone_id=zone_id,
                    timestamp=ts,
                    inflow_litres=inflow,
                    night_flow_litres=night_flow,
                    pressure_bar=pressure,
                ))
                readings_inserted += 1

            except Exception as e:
                warnings.append(f"Row {row_num}: {e} -- skipped.")

        db.commit()

    elif csv_type == "billing":
        for i, row in df.iterrows():
            row_num = i + 2
            try:
                zone_id = str(row["zone_id"]).strip()
                consumer_id = str(row["consumer_id"]).strip()
                billed = float(row["billed_litres"])
                benchmark = float(row["benchmark_litres"])
                period = str(row["billing_period"]).strip()

                if zone_id not in valid_zone_ids:
                    warnings.append(f"Row {row_num}: unknown zone_id '{zone_id}' -- skipped.")
                    continue
                if billed < 0 or benchmark <= 0:
                    warnings.append(f"Row {row_num}: invalid litres values -- skipped.")
                    continue

                hh_size = int(row["household_size"]) if "household_size" in df.columns and pd.notna(row.get("household_size")) else 4
                prop_type = str(row["property_type"]).strip() if "property_type" in df.columns and pd.notna(row.get("property_type")) else "residential"

                # Basic anomaly score: how far below benchmark (0 = normal, 1 = max suspicious)
                ratio = billed / benchmark if benchmark > 0 else 1.0
                anomaly_score = round(max(0.0, 1.0 - ratio), 4)
                is_anomaly = ratio < FALLBACK_RATIO  # documented no-ML threshold

                db.add(BillingRecord(
                    zone_id=zone_id,
                    consumer_id=consumer_id,
                    billed_litres=billed,
                    benchmark_litres=benchmark,
                    billing_period=period,
                    household_size=hh_size,
                    property_type=prop_type,
                    anomaly_score=anomaly_score,
                    is_anomaly=is_anomaly,
                ))
                billing_inserted += 1

            except Exception as e:
                warnings.append(f"Row {row_num}: {e} -- skipped.")

        db.commit()

    return CSVUploadResult(
        readings_inserted=readings_inserted,
        billing_records_inserted=billing_inserted,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# GET /data/town-profile
# ---------------------------------------------------------------------------
@router.get("/town-profile", response_model=TownProfile)
def get_town_profile():
    """
    Returns the real Lucknow city-level NRW figures used to anchor all
    synthetic zone data. Includes source citation for demo transparency.

    Judges can ask 'where did this data come from?' -- this endpoint answers that.
    """
    return LUCKNOW_PROFILE


# ---------------------------------------------------------------------------
# GET /data/nrw-forecast            -- town-wide 30-day projection
# GET /data/nrw-forecast/{zone_id}  -- single-zone 30-day projection
#
# Tier 1 optional model (Person 1, Hours 10-15): turns 13 weeks of
# nrw_snapshots into the pitch line "if unfixed, projected loss over the next
# 30 days is X litres / Rs Y", which feeds the payback/ROI story.
# ---------------------------------------------------------------------------

def _town_tariff_rate(db: Session) -> float:
    """
    Tariff is configurable per zone (roadmap deprecation of the hardcoded
    TARIFF_RATE constant); the town-wide forecast uses the mean of the zones.
    """
    from sqlalchemy import func

    average = db.query(func.avg(Zone.tariff_rate)).scalar()
    return float(average) if average else 0.005


@router.get("/nrw-forecast", response_model=NRWForecast)
def get_town_nrw_forecast(
    horizon_days: int = Query(30, ge=1, le=365, description="Projection window in days"),
    db: Session = Depends(get_db),
):
    """
    Town-wide projection: every zone's daily loss summed per snapshot date,
    NRW percentage averaged across zones, then fitted for the horizon.
    """
    return forecast(
        load_town_snapshots(db),
        tariff_rate=_town_tariff_rate(db),
        horizon_days=horizon_days,
    )


@router.get("/nrw-forecast/{zone_id}", response_model=NRWForecast)
def get_zone_nrw_forecast(
    zone_id: str,
    horizon_days: int = Query(30, ge=1, le=365, description="Projection window in days"),
    db: Session = Depends(get_db),
):
    """Single-zone projection using that zone's configured tariff rate."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    return forecast(
        load_zone_snapshots(db, zone_id),
        tariff_rate=zone.tariff_rate or 0.005,
        horizon_days=horizon_days,
        zone_id=zone_id,
    )
