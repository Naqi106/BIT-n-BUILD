"""
Agent Tools Module: AltoMare AI Agent (Block 2)
Provides deterministic analytical data retrieval helpers wrapping existing
AltoMare calculation engines and database records.

Rules:
- Directly calls existing Python functions; NEVER makes localhost HTTP calls.
- Returns only JSON-safe primitives (dict, list, str, float, int, bool, None).
- Never returns SQLAlchemy ORM instances.
- Never fabricates missing real data; flags NO_DATA, NO_TELEMETRY, or DEFAULT_FALLBACK.
- PPA simulation is explicitly marked is_simulated=True.
- Water-quality correlation returns NOT_AVAILABLE safely.
"""

from typing import Optional, Dict, Any, List
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db import SessionLocal
from backend.data.db_schema import Zone, RawReading, BillingRecord
from backend.app.engines.latias import (
    water_balance_loss,
    mnf_loss_estimate,
    unavoidable_annual_real_losses,
)
from backend.app.engines.ml_billing_anomaly import FLAG_THRESHOLD, get_detector
from backend.app.routers.audit import get_ppa_leak_location


def run_water_balance(
    zone_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Computes component-based water balance for a zone using latest telemetry and billing data.
    Wraps water_balance_loss() from backend.app.engines.latias.
    """
    managed_session = False
    if db is None:
        try:
            db = SessionLocal()
            managed_session = True
        except Exception:
            db = None

    try:
        if db is None:
            return {
                "zone_id": zone_id,
                "inflow_litres": 0.0,
                "billed_litres": 0.0,
                "loss_litres": 0.0,
                "nrw_percentage": 0.0,
                "severity": "LOW",
                "is_leak_detected": False,
                "data_source": "NO_DATA",
                "status": "NO_DATA",
            }

        latest_reading = (
            db.query(RawReading)
            .filter(RawReading.zone_id == zone_id)
            .order_by(RawReading.timestamp.desc())
            .first()
        )

        if not latest_reading or latest_reading.inflow_litres is None:
            return {
                "zone_id": zone_id,
                "inflow_litres": 0.0,
                "billed_litres": 0.0,
                "loss_litres": 0.0,
                "nrw_percentage": 0.0,
                "severity": "LOW",
                "is_leak_detected": False,
                "data_source": "NO_DATA",
                "status": "NO_DATA",
            }

        inflow = float(latest_reading.inflow_litres)
        billed_sum = (
            db.query(func.sum(BillingRecord.billed_litres))
            .filter(BillingRecord.zone_id == zone_id)
            .scalar()
        )
        billed_litres = float(billed_sum) if billed_sum is not None else 0.0

        loss = water_balance_loss(inflow, billed_litres)
        nrw_pct = round((loss / inflow * 100.0), 2) if inflow > 0 else 0.0

        if nrw_pct >= 50.0:
            severity = "CRITICAL"
        elif nrw_pct >= 35.0:
            severity = "HIGH"
        elif nrw_pct >= 20.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        is_leak = loss > 0.0

        return {
            "zone_id": zone_id,
            "inflow_litres": round(inflow, 2),
            "billed_litres": round(billed_litres, 2),
            "loss_litres": round(loss, 2),
            "nrw_percentage": nrw_pct,
            "severity": severity,
            "is_leak_detected": is_leak,
            "data_source": "TELEMETRY",
            "status": "SUCCESS",
        }
    except Exception as e:
        return {
            "zone_id": zone_id,
            "inflow_litres": 0.0,
            "billed_litres": 0.0,
            "loss_litres": 0.0,
            "nrw_percentage": 0.0,
            "severity": "LOW",
            "is_leak_detected": False,
            "data_source": "NO_DATA",
            "status": "ERROR",
            "error": str(e),
        }
    finally:
        if managed_session and db is not None:
            db.close()


def run_mnf(
    zone_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Estimates 24-hr physical leakage from Minimum Night Flow (2:00 AM - 4:00 AM).
    Wraps mnf_loss_estimate() from backend.app.engines.latias.
    """
    managed_session = False
    if db is None:
        try:
            db = SessionLocal()
            managed_session = True
        except Exception:
            db = None

    try:
        if db is None:
            return {
                "zone_id": zone_id,
                "has_night_flow_data": False,
                "night_flow_litres": 0.0,
                "estimated_daily_leakage_litres": 0.0,
                "status": "NO_TELEMETRY",
            }

        latest_reading = (
            db.query(RawReading)
            .filter(RawReading.zone_id == zone_id, RawReading.night_flow_litres.isnot(None))
            .order_by(RawReading.timestamp.desc())
            .first()
        )

        if not latest_reading or latest_reading.night_flow_litres is None or latest_reading.night_flow_litres <= 0:
            return {
                "zone_id": zone_id,
                "has_night_flow_data": False,
                "night_flow_litres": 0.0,
                "estimated_daily_leakage_litres": 0.0,
                "status": "NO_TELEMETRY",
            }

        night_flow = float(latest_reading.night_flow_litres)
        daily_loss = mnf_loss_estimate(night_flow)

        return {
            "zone_id": zone_id,
            "has_night_flow_data": True,
            "night_flow_litres": round(night_flow, 2),
            "estimated_daily_leakage_litres": round(daily_loss, 2),
            "status": "SUCCESS",
        }
    except Exception as e:
        return {
            "zone_id": zone_id,
            "has_night_flow_data": False,
            "night_flow_litres": 0.0,
            "estimated_daily_leakage_litres": 0.0,
            "status": "ERROR",
            "error": str(e),
        }
    finally:
        if managed_session and db is not None:
            db.close()


def run_uarl(
    zone_id: str,
    current_real_loss_litres: Optional[float] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Calculates Unavoidable Annual Real Losses (UARL) baseline and ILI for a zone.
    Wraps unavoidable_annual_real_losses() from backend.app.engines.latias.
    """
    managed_session = False
    if db is None:
        try:
            db = SessionLocal()
            managed_session = True
        except Exception:
            db = None

    try:
        if db is None:
            return {
                "zone_id": zone_id,
                "uarl_litres_per_day": 0.0,
                "infrastructure_leakage_index": None,
                "pipe_length_km": 0.0,
                "connection_count": 0,
                "avg_pressure_bar": 0.0,
                "status": "NO_DATA",
            }

        zone = db.query(Zone).filter(Zone.id == zone_id).first()
        if not zone:
            return {
                "zone_id": zone_id,
                "uarl_litres_per_day": 0.0,
                "infrastructure_leakage_index": None,
                "pipe_length_km": 0.0,
                "connection_count": 0,
                "avg_pressure_bar": 0.0,
                "status": "NO_DATA",
            }

        pipe_len = float(zone.pipe_length_km or 0.0)
        conn_count = int(zone.connection_count or 0)
        pressure = float(zone.avg_pressure_bar or 0.0)

        uarl = unavoidable_annual_real_losses(pipe_len, conn_count, pressure)

        ili = None
        if current_real_loss_litres is not None and uarl > 0:
            ili = round(current_real_loss_litres / uarl, 2)

        return {
            "zone_id": zone_id,
            "uarl_litres_per_day": round(uarl, 2),
            "infrastructure_leakage_index": ili,
            "pipe_length_km": pipe_len,
            "connection_count": conn_count,
            "avg_pressure_bar": pressure,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {
            "zone_id": zone_id,
            "uarl_litres_per_day": 0.0,
            "infrastructure_leakage_index": None,
            "pipe_length_km": 0.0,
            "connection_count": 0,
            "avg_pressure_bar": 0.0,
            "status": "ERROR",
            "error": str(e),
        }
    finally:
        if managed_session and db is not None:
            db.close()


def run_ppa(
    zone_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Executes Pressure Profile Analysis (PPA) simulation to locate candidate leak nodes.
    Wraps get_ppa_leak_location() from backend.app.routers.audit.
    Always declares is_simulated = True.
    """
    managed_session = False
    if db is None:
        try:
            db = SessionLocal()
            managed_session = True
        except Exception:
            db = None

    try:
        nodes = get_ppa_leak_location(zone_id=zone_id, db=db)
        if not nodes:
            return {
                "zone_id": zone_id,
                "highest_probability_node": "",
                "suspect_distance_km": 0.0,
                "pressure_drop_bar": 0.0,
                "leak_probability": 0.0,
                "is_simulated": True,
                "total_nodes_evaluated": 0,
                "status": "ERROR",
            }

        highest = max(nodes, key=lambda n: n.leak_probability)
        return {
            "zone_id": zone_id,
            "highest_probability_node": str(highest.node_id),
            "suspect_distance_km": float(highest.distance_from_source_km),
            "pressure_drop_bar": float(highest.pressure_drop_bar),
            "leak_probability": float(highest.leak_probability),
            "is_simulated": True,
            "total_nodes_evaluated": len(nodes),
            "status": "SUCCESS",
        }
    except Exception as e:
        return {
            "zone_id": zone_id,
            "highest_probability_node": "",
            "suspect_distance_km": 0.0,
            "pressure_drop_bar": 0.0,
            "leak_probability": 0.0,
            "is_simulated": True,
            "total_nodes_evaluated": 0,
            "status": "ERROR",
            "error": str(e),
        }
    finally:
        if managed_session and db is not None:
            db.close()


def run_billing_anomaly(
    zone_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Audits consumer billing records for suspicious consumption anomalies.

    Primary path : live Isolation Forest scoring, identical to
                   GET /audit/billing/{zone_id}, so the Copilot's citation
                   and the BillingAudit screen never disagree.
    Fallback path: the stored rule column written at ingest time
                   (billed < 60% of benchmark) when the model is not trained.
    The path actually used is reported as `detection_method`.
    """
    managed_session = False
    if db is None:
        try:
            db = SessionLocal()
            managed_session = True
        except Exception:
            db = None

    try:
        if db is None:
            return {
                "zone_id": zone_id,
                "total_accounts_audited": 0,
                "anomaly_count": 0,
                "anomaly_rate_pct": 0.0,
                "estimated_unbilled_litres": 0.0,
                "top_suspicious_consumer_ids": [],
                "detection_method": None,
                "status": "NO_DATA",
            }

        query = db.query(BillingRecord).filter(BillingRecord.zone_id == zone_id)
        total_records = query.count()

        if total_records == 0:
            return {
                "zone_id": zone_id,
                "total_accounts_audited": 0,
                "anomaly_count": 0,
                "anomaly_rate_pct": 0.0,
                "estimated_unbilled_litres": 0.0,
                "top_suspicious_consumer_ids": [],
                "detection_method": None,
                "status": "NO_DATA",
            }

        records = query.order_by(BillingRecord.id).all()
        detector = get_detector()

        if detector is not None and detector.is_trained:
            # Live ML path — re-scored on every call, same model and same
            # FLAG_THRESHOLD the audit endpoint uses.
            frame = pd.DataFrame([{
                "billed_litres": r.billed_litres,
                "benchmark_litres": r.benchmark_litres,
                "household_size": r.household_size or 4,
            } for r in records])
            scores = detector.predict_anomaly(frame)
            detection_method = "isolation_forest"
            flagged = sorted(
                ((r, float(s)) for r, s in zip(records, scores)
                 if s >= FLAG_THRESHOLD),
                key=lambda item: -item[1],
            )
        else:
            # Documented no-ML fallback (stored rule column from ingest)
            detection_method = "rule_fallback"
            flagged = sorted(
                ((r, float(r.anomaly_score or 0.0)) for r in records
                 if r.is_anomaly),
                key=lambda item: -item[1],
            )

        anomaly_count = len(flagged)
        anomaly_rate_pct = round((anomaly_count / total_records) * 100.0, 2)

        estimated_unbilled = sum(
            max(0.0, float(r.benchmark_litres or 0.0) - float(r.billed_litres or 0.0))
            for r, _ in flagged
        )

        top_consumers = [str(r.consumer_id) for r, _ in flagged[:5]]

        return {
            "zone_id": zone_id,
            "total_accounts_audited": total_records,
            "anomaly_count": anomaly_count,
            "anomaly_rate_pct": anomaly_rate_pct,
            "estimated_unbilled_litres": round(estimated_unbilled, 2),
            "top_suspicious_consumer_ids": top_consumers,
            "detection_method": detection_method,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {
            "zone_id": zone_id,
            "total_accounts_audited": 0,
            "anomaly_count": 0,
            "anomaly_rate_pct": 0.0,
            "estimated_unbilled_litres": 0.0,
            "top_suspicious_consumer_ids": [],
            "detection_method": None,
            "status": "ERROR",
            "error": str(e),
        }
    finally:
        if managed_session and db is not None:
            db.close()


def get_correlation_status(
    zone_id: str,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Returns water-quality and contamination correlation status for a zone.
    Currently no water-quality subsystem or DB table is configured.
    Returns safe NOT_AVAILABLE convention without fabricating data.
    """
    return {
        "zone_id": zone_id,
        "correlation_detected": False,
        "risk_level": "NONE",
        "water_quality_events": 0,
        "details": "No water-quality data source is currently configured.",
        "is_simulated": False,
        "status": "NOT_AVAILABLE",
    }
