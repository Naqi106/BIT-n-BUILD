"""
ML Billing Anomaly Detector — Person 1 (Data + ML)

Isolation Forest replacing the hardcoded 40%-threshold rule.

Primary path : Isolation Forest trained on billed vs benchmark litres.
Fallback path: rule-based (billed < 60% of benchmark) — kept only as a
               documented no-ML safety net when the model is not yet trained.

Usage
-----
    from backend.app.engines.ml_billing_anomaly import train_detector, is_anomaly

    # Once at startup, after loading billing records:
    df = pd.DataFrame(records)          # needs: billed_litres, benchmark_litres, household_size
    train_detector(df)

    # Per-household check:
    flagged, explanation = is_anomaly(billed=420, benchmark=1080, household_size=4)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple

from sklearn.ensemble import IsolationForest


class BillingAnomalyDetector:
    """
    Isolation Forest model for billing-theft detection.

    Features used: billed_litres, benchmark_litres, household_size.
    """

    FEATURES = ["billed_litres", "benchmark_litres", "household_size"]

    def __init__(self, contamination: float = 0.10, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model: Optional[IsolationForest] = None
        self.is_trained = False
        # Rough decision_function range observed on Lucknow seed data
        self._score_min: float = -0.5
        self._score_max: float = 0.5

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> "BillingAnomalyDetector":
        """Train on a billing-records DataFrame."""
        X = df[self.FEATURES].fillna(df[self.FEATURES].median())
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=100,
            random_state=self.random_state,
        )
        self.model.fit(X.values)

        # Calibrate normalisation range from training data
        scores = self.model.decision_function(X.values)
        self._score_min = float(scores.min())
        self._score_max = float(scores.max())

        self.is_trained = True
        return self

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _decision_to_anomaly(self, raw_score: float) -> float:
        """
        Map Isolation Forest decision_function score → anomaly likelihood [0, 1].

        decision_function: lower = more anomalous.
        We invert so that 1 = definitely anomalous, 0 = completely normal.
        """
        span = self._score_max - self._score_min or 1e-8
        normalised = (raw_score - self._score_min) / span  # 0 = most anomalous, 1 = most normal
        return float(np.clip(1.0 - normalised, 0.0, 1.0))

    def score_household(
        self, billed: float, benchmark: float, household_size: int = 4
    ) -> float:
        """
        Return anomaly likelihood in [0, 1] for a single household.
        Falls back to rule-based score when not yet trained.
        """
        if not self.is_trained:
            # Rule-based fallback: 40% below benchmark threshold
            ratio = billed / benchmark if benchmark > 0 else 1.0
            return float(np.clip(1.0 - ratio, 0.0, 1.0))

        x = np.array([[billed, benchmark, household_size]])
        raw = float(self.model.decision_function(x)[0])
        return self._decision_to_anomaly(raw)

    def predict_anomaly(self, df: pd.DataFrame) -> np.ndarray:
        """Batch-score a DataFrame; returns anomaly likelihood array."""
        if not self.is_trained:
            raise RuntimeError("Detector must be fitted before calling predict_anomaly.")
        X = df[self.FEATURES].fillna(df[self.FEATURES].median())
        scores = self.model.decision_function(X.values)
        return np.array([self._decision_to_anomaly(s) for s in scores])

    def explanation(
        self, billed: float, benchmark: float, household_size: int = 4
    ) -> Dict[str, str]:
        """Human-readable explanation for a single-household score."""
        ratio = billed / benchmark if benchmark > 0 else 0.0
        ml_score = self.score_household(billed, benchmark, household_size)

        if ml_score >= 0.7:
            rec = "Strong anomaly flag — refer for field investigation"
        elif ml_score >= 0.4:
            rec = "Moderate anomaly — monitor and cross-check billing"
        else:
            rec = "No anomaly detected"

        method = "isolation_forest" if self.is_trained else "rule_fallback"
        return {
            "method": method,
            "ml_score": f"{ml_score:.3f}",
            "billed_vs_benchmark": f"{ratio * 100:.0f}%",
            "recommendation": rec,
        }


# ---------------------------------------------------------------------------
# Module-level singleton — trained once at app startup
# ---------------------------------------------------------------------------

_detector: Optional[BillingAnomalyDetector] = None


def train_detector(df: pd.DataFrame) -> BillingAnomalyDetector:
    """
    Train and register the global detector.
    Call once during app startup after loading billing_records from the DB.
    """
    global _detector
    _detector = BillingAnomalyDetector(contamination=0.10, random_state=42)
    _detector.fit(df)
    return _detector


def get_detector() -> Optional[BillingAnomalyDetector]:
    """Return the trained global detector (None if not yet trained)."""
    return _detector


def is_anomaly(
    billed: float, benchmark: float, household_size: int = 4
) -> Tuple[bool, Dict[str, str]]:
    """
    Check whether a household is anomalous.

    Primary path  : Isolation Forest (when _detector is trained).
    Fallback path : rule-based, billed < 60% of benchmark.

    Returns
    -------
    (is_anomalous: bool, explanation: dict)
    """
    det = _detector

    if det is None:
        # Documented rule-based fallback
        ratio = billed / benchmark if benchmark > 0 else 1.0
        flagged = ratio < 0.60
        return flagged, {
            "method": "rule_fallback",
            "ml_score": "N/A",
            "billed_vs_benchmark": f"{ratio * 100:.0f}%",
            "recommendation": "Flag for review (billed < 60% of benchmark)",
        }

    score = det.score_household(billed, benchmark, household_size)
    return (score >= 0.5), det.explanation(billed, benchmark, household_size)
