"""
Unit tests — Model 1: Isolation Forest billing anomaly detector
Person 1 (Data + ML), Hours 7-10 roadmap deliverable.

    python -m pytest backend/test/test_ml_billing.py -v

Two layers:
  1. Pure unit tests over a fixture that mirrors lucknow_seed.py's theft rule
     (theft households billed 35-65% of benchmark, normal households 92-108%).
     No database, no network, runs in milliseconds.
  2. One integration check against the live seeded Lucknow data — asserts the
     known theft zones (zone_2 Aliganj, zone_4 Gomti Nagar, zone_6 Chowk) score
     higher than a clean zone. Skips automatically if the DB is unreachable.
"""

import random

import pandas as pd
import pytest

from backend.app.engines import ml_billing_anomaly as mba


# Mirrors lucknow_seed.py: household_size=4 x 135 L/person/day x 30 days
BENCHMARK = 4 * 135 * 30  # 16200 L/month

THEFT_ZONES = {"zone_2", "zone_4", "zone_6"}
CLEAN_ZONE = "zone_8"  # Chinhat — no theft seeded there


@pytest.fixture(autouse=True)
def isolate_detector_state():
    """Never let a test leak a trained model into the running app."""
    saved = mba._detector
    yield
    mba._detector = saved


@pytest.fixture()
def seeded_df() -> pd.DataFrame:
    """Reproduces the seeded billing distribution from lucknow_seed.py."""
    rng = random.Random(42)
    rows = []

    # 12 theft households — 3 per theft zone, as the seed writes them
    for _ in range(12):
        rows.append({
            "billed_litres": round(BENCHMARK * rng.uniform(0.35, 0.65)),
            "benchmark_litres": BENCHMARK,
            "household_size": 4,
            "_label": "theft",
        })

    # 60 normal households
    for _ in range(60):
        rows.append({
            "billed_litres": round(BENCHMARK * rng.uniform(0.92, 1.08)),
            "benchmark_litres": BENCHMARK,
            "household_size": 4,
            "_label": "normal",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Training + scoring behaviour
# ---------------------------------------------------------------------------

def test_detector_trains(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)
    assert det.is_trained
    assert det.model is not None


def test_seeded_theft_households_are_flagged(seeded_df):
    """Core requirement: the 12 known theft households must be caught."""
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    theft_mask = seeded_df["_label"].eq("theft").values
    theft_flagged = int((scores[theft_mask] >= 0.5).sum())

    # Allow one miss — Isolation Forest is unsupervised, not a guarantee
    assert theft_flagged >= 11, (
        f"Only {theft_flagged}/12 known theft households flagged"
    )


def test_theft_scores_rank_above_normal(seeded_df):
    """Average score for theft households must exceed average for normal ones."""
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    theft_mask = seeded_df["_label"].eq("theft").values
    mean_theft = scores[theft_mask].mean()
    mean_normal = scores[~theft_mask].mean()

    assert mean_theft > mean_normal, (
        f"Theft mean {mean_theft:.3f} not above normal mean {mean_normal:.3f}"
    )


def test_false_positive_rate_is_reasonable(seeded_df):
    """Rule-based predecessor used a hard 40% cut; ML must not flag everything."""
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    normal_mask = seeded_df["_label"].eq("normal").values
    fp_rate = float((scores[normal_mask] >= 0.5).mean())

    assert fp_rate <= 0.15, f"False-positive rate {fp_rate:.0%} too high"


def test_extreme_cases_score_in_expected_direction(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)

    severe_theft = det.score_household(billed=BENCHMARK * 0.35, benchmark=BENCHMARK)
    honest = det.score_household(billed=BENCHMARK, benchmark=BENCHMARK)

    assert severe_theft > honest, (
        f"severe theft {severe_theft:.3f} must outrank honest {honest:.3f}"
    )
    assert 0.0 <= severe_theft <= 1.0
    assert 0.0 <= honest <= 1.0


def test_scores_are_normalised_to_unit_interval(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=0.15, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)
    assert scores.min() >= 0.0
    assert scores.max() <= 1.0


# ---------------------------------------------------------------------------
# 2. Documented rule-based fallback (roadmap Section 4: keep as fallback)
# ---------------------------------------------------------------------------

def test_rule_fallback_when_model_missing():
    """If sklearn/model fails to load, the old 40%-rule must still work."""
    assert mba._detector is None  # ensure untrained state

    flagged, expl = mba.is_anomaly(billed=BENCHMARK * 0.50, benchmark=BENCHMARK)

    assert flagged is True
    assert expl["method"] == "rule_fallback"
    assert expl["ml_score"] == "N/A"


def test_rule_fallback_passes_honest_households():
    assert mba._detector is None

    flagged, expl = mba.is_anomaly(billed=BENCHMARK, benchmark=BENCHMARK)
    assert flagged is False
    assert expl["method"] == "rule_fallback"


def test_rule_fallback_respects_the_40_percent_threshold():
    """billed < 60% of benchmark => flagged; billed >= 60% => not flagged."""
    assert mba._detector is None

    just_below, _ = mba.is_anomaly(billed=BENCHMARK * 0.59, benchmark=BENCHMARK)
    just_above, _ = mba.is_anomaly(billed=BENCHMARK * 0.61, benchmark=BENCHMARK)

    assert just_below is True
    assert just_above is False


# ---------------------------------------------------------------------------
# 3. Primary ML path through the public entry point
# ---------------------------------------------------------------------------

def test_primary_path_uses_isolation_forest(seeded_df):
    mba.train_detector(seeded_df)

    flagged, expl = mba.is_anomaly(billed=BENCHMARK * 0.40, benchmark=BENCHMARK)

    assert flagged is True
    assert expl["method"] == "isolation_forest"
    assert 0.0 <= float(expl["ml_score"]) <= 1.0
    assert "recommendation" in expl
    assert "billed_vs_benchmark" in expl


def test_detector_singleton_is_registered(seeded_df):
    det = mba.train_detector(seeded_df)
    assert mba.get_detector() is det
    assert det.is_trained


def test_batch_scoring_matches_row_count(seeded_df):
    det = mba.train_detector(seeded_df)
    scores = det.predict_anomaly(seeded_df)
    assert len(scores) == len(seeded_df)


def test_explanation_reports_rule_and_ml(seeded_df):
    det = mba.train_detector(seeded_df)
    expl = det.explanation(billed=BENCHMARK * 0.45, benchmark=BENCHMARK)

    assert expl["method"] == "isolation_forest"
    assert expl["billed_vs_benchmark"] == "45%"
    assert "anomaly" in expl["recommendation"].lower()


# ---------------------------------------------------------------------------
# 4. Integration against the real seeded Lucknow data
# ---------------------------------------------------------------------------

def _load_seeded_billing() -> pd.DataFrame:
    try:
        from backend.app.db import SessionLocal
        from backend.data.db_schema import BillingRecord

        db = SessionLocal()
        try:
            rows = db.query(
                BillingRecord.zone_id,
                BillingRecord.billed_litres,
                BillingRecord.benchmark_litres,
                BillingRecord.household_size,
            ).all()
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unavailable: {exc}")

    if len(rows) < 50:
        pytest.skip("seed data not present — run backend/data/lucknow_seed.py")

    return pd.DataFrame(
        [{
            "zone_id": r[0],
            "billed_litres": r[1],
            "benchmark_litres": r[2],
            "household_size": r[3] or 4,
        } for r in rows]
    )


def test_live_theft_zones_outrank_clean_zone():
    """
    The known theft zones seeded by lucknow_seed.py must produce a higher mean
    anomaly score than a zone with no seeded theft.
    """
    df = _load_seeded_billing()

    det = mba.BillingAnomalyDetector(contamination=0.10, random_state=42).fit(df)
    df = df.copy()
    df["score"] = det.predict_anomaly(df)

    zone_means = df.groupby("zone_id")["score"].mean()

    theft_mean = zone_means[zone_means.index.isin(THEFT_ZONES)].mean()
    clean_mean = zone_means.get(CLEAN_ZONE)

    assert clean_mean is not None, f"{CLEAN_ZONE} missing from seed data"
    assert theft_mean > clean_mean, (
        f"Theft zones mean {theft_mean:.3f} not above {CLEAN_ZONE} {clean_mean:.3f}"
    )

    total_flagged = int((df["score"] >= 0.5).sum())
    assert total_flagged > 0, "model flagged nothing across the whole seeded dataset"
