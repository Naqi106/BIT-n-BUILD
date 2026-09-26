"""
ML Confidence Score — Person 1 (Data + ML)

Replaces every hardcoded ``confidence_score = 0.7`` in the codebase.

The hardcoded constant is **deleted**, not just left unused.  Every call
site that previously wrote 0.7 should import and call ``compute_confidence``
instead.

Score components (equal weight, averaged to [0, 1]):
    1. data_completeness  — fraction of data types present (inflow, billing, MNF)
    2. count_weight       — logarithmic scale on number of inflow readings
    3. variance_weight    — lower reading variance → higher confidence
    4. method_weight      — more detection methods agreeing → higher confidence
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def compute_confidence(
    has_inflow: bool,
    has_billing: bool,
    has_mnf: bool,
    reading_count: int,
    reading_variance: float,
    methods_agreed: int = 1,
) -> float:
    """
    Compute a dynamic confidence score for a leak alert.

    Parameters
    ----------
    has_inflow       : True if the zone has inflow meter readings.
    has_billing      : True if the zone has household billing data.
    has_mnf          : True if minimum night-flow data is available.
    reading_count    : Number of inflow observations for the zone.
    reading_variance : Normalised variance of inflow readings (0 = no variance).
    methods_agreed   : How many detection methods flagged the same zone (1–3).

    Returns
    -------
    confidence_score : float in [0, 1]
    """
    # Component 1 — data completeness
    present = sum([has_inflow, has_billing, has_mnf])
    completeness = present / 3.0

    # Component 2 — reading count (log-like steps)
    if reading_count >= 50:
        count_weight = 1.00
    elif reading_count >= 20:
        count_weight = 0.80
    elif reading_count >= 10:
        count_weight = 0.60
    elif reading_count >= 3:
        count_weight = 0.40
    else:
        count_weight = 0.20

    # Component 3 — variance (lower variance = higher confidence)
    variance_weight = max(0.0, 1.0 - float(reading_variance))

    # Component 4 — method agreement
    method_weight = {1: 0.33, 2: 0.67, 3: 1.00}.get(methods_agreed, 0.33)

    score = (completeness + count_weight + variance_weight + method_weight) / 4.0
    return round(max(0.0, min(1.0, score)), 3)


def get_confidence_breakdown(
    zone_id: str,
    has_inflow: bool,
    has_billing: bool,
    has_mnf: bool,
    reading_count: int,
    reading_variance: float,
    methods_agreed: int = 1,
) -> Dict[str, Any]:
    """
    Return the confidence score AND a full component breakdown for auditability.

    Useful for API responses and the AI Copilot's evidence citations.
    """
    score = compute_confidence(
        has_inflow, has_billing, has_mnf,
        reading_count, reading_variance, methods_agreed,
    )

    present = sum([has_inflow, has_billing, has_mnf])

    method_table = {1: 0.33, 2: 0.67, 3: 1.00}

    return {
        "zone_id": zone_id,
        "confidence_score": score,
        "interpretation": interpret(score),
        "components": {
            "data_completeness": round(present / 3.0, 3),
            "count_weight": round(
                1.00 if reading_count >= 50 else
                0.80 if reading_count >= 20 else
                0.60 if reading_count >= 10 else
                0.40 if reading_count >= 3 else 0.20,
                3,
            ),
            "variance_weight": round(max(0.0, 1.0 - float(reading_variance)), 3),
            "method_weight": round(method_table.get(methods_agreed, 0.33), 3),
        },
        "calculated_at": datetime.utcnow().isoformat(),
    }


def interpret(score: float) -> str:
    """Human-readable band for the confidence score."""
    if score >= 0.80:
        return "High — reliable detection, suitable for automated actions"
    if score >= 0.50:
        return "Moderate — manual verification recommended before acting"
    return "Low — detection unreliable, field investigation required"
