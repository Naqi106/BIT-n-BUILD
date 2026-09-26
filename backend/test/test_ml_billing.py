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
    """
    Faithful reproduction of lucknow_seed.py's billing generation rule, at the
    same composition as the live DB (399 records: 9 theft households x 3 months
    = 27 theft rows, 124 normal households x 3 months = 372 normal rows).

        theft  : 3 households in zone_2/4/6, billed 35-65% of benchmark
        normal : billed 92-108% of benchmark
        monthly: billed_base x uniform(0.95, 1.05)
        benchmark = household_size x 135 L/day x 30 days, size random 3-7
    """
    rng = random.Random(42)
    rows = []

    def add_household(is_theft: bool) -> None:
        hh_size = rng.randint(3, 7)
        benchmark = hh_size * 135 * 30
        billed_base = round(
            benchmark * (rng.uniform(0.35, 0.65) if is_theft else rng.uniform(0.92, 1.08))
        )
        label = "theft" if is_theft else "normal"
        for _ in range(3):  # three monthly billing periods
            rows.append({
                "billed_litres": round(billed_base * rng.uniform(0.95, 1.05)),
                "benchmark_litres": benchmark,
                "household_size": hh_size,
                "_label": label,
            })

    for _ in range(9):    # 3 theft households in each of zone_2 / zone_4 / zone_6
        add_household(is_theft=True)
    for _ in range(124):  # every other household in the 12 seeded zones
        add_household(is_theft=False)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Training + scoring behaviour
# ---------------------------------------------------------------------------

def test_detector_trains(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)
    assert det.is_trained
    assert det.model is not None


def test_seeded_theft_households_are_flagged(seeded_df):
    """Core requirement: the 12 known theft households must be caught."""
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    theft_mask = seeded_df["_label"].eq("theft").values
    theft_flagged = int((scores[theft_mask] >= mba.FLAG_THRESHOLD).sum())
    n_theft = int(theft_mask.sum())

    # Allow one miss — Isolation Forest is unsupervised, not a guarantee
    assert theft_flagged >= n_theft - 1, (
        f"Only {theft_flagged}/{n_theft} known theft households flagged"
    )


def test_theft_scores_rank_above_normal(seeded_df):
    """Average score for theft households must exceed average for normal ones."""
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    theft_mask = seeded_df["_label"].eq("theft").values
    mean_theft = scores[theft_mask].mean()
    mean_normal = scores[~theft_mask].mean()

    assert mean_theft > mean_normal, (
        f"Theft mean {mean_theft:.3f} not above normal mean {mean_normal:.3f}"
    )


def test_false_positive_rate_is_reasonable(seeded_df):
    """Rule-based predecessor used a hard 40% cut; ML must not flag everything."""
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)
    scores = det.predict_anomaly(seeded_df)

    normal_mask = seeded_df["_label"].eq("normal").values
    fp_rate = float((scores[normal_mask] >= mba.FLAG_THRESHOLD).mean())

    assert fp_rate <= 0.05, f"False-positive rate {fp_rate:.0%} too high"


def test_extreme_cases_score_in_expected_direction(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)

    severe_theft = det.score_household(billed=BENCHMARK * 0.35, benchmark=BENCHMARK)
    honest = det.score_household(billed=BENCHMARK, benchmark=BENCHMARK)

    assert severe_theft > honest, (
        f"severe theft {severe_theft:.3f} must outrank honest {honest:.3f}"
    )
    assert 0.0 <= severe_theft <= 1.0
    assert 0.0 <= honest <= 1.0


def test_scores_are_normalised_to_unit_interval(seeded_df):
    det = mba.BillingAnomalyDetector(contamination=mba.CONTAMINATION, random_state=42).fit(seeded_df)
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

    total_flagged = int((df["score"] >= mba.FLAG_THRESHOLD).sum())
    assert total_flagged > 0, "model flagged nothing across the whole seeded dataset"


# ---------------------------------------------------------------------------
# 5. Hours 10-15 threshold tuning — pinned so a constant change fails loudly
# ---------------------------------------------------------------------------

def test_tuned_thresholds_hold_on_seeded_data():
    """
    Reproduces backend/test/tune_thresholds.py's headline result:
    at CONTAMINATION=0.08 / FLAG_THRESHOLD=0.50 the detector must catch every
    ground-truth theft household (ratio < 0.70) while keeping precision >= 0.80,
    i.e. the numbers the AI Copilot cites to a judge stay defensible.
    """
    df = _load_seeded_billing()

    y_true = (df["billed_litres"] / df["benchmark_litres"] < 0.70).values

    det = mba.BillingAnomalyDetector(
        contamination=mba.CONTAMINATION, random_state=42
    ).fit(df)
    y_pred = det.predict_anomaly(df) >= mba.FLAG_THRESHOLD

    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    assert recall >= 0.99, f"missed {fn} seeded theft households (recall {recall:.2f})"
    assert precision >= 0.80, f"precision {precision:.2f} below tuned 0.80 floor"
    assert y_pred.sum() <= len(df) * 0.12, (
        f"{int(y_pred.sum())}/{len(df)} flagged — tuned cut should stay near 8%"
    )


def test_scores_reproduce_across_independent_resample():
    """
    The calibration must not depend on which rows happen to land in the
    training sample: an independent re-sample drawn from the same generation
    rule has to yield the same precision/recall. This is the regression test
    for the min-max normalisation that was replaced (recall 1.00 -> 0.59).
    """
    rng = random.Random(7)
    rows = []

    def add_household(is_theft: bool) -> None:
        hh_size = rng.randint(3, 7)
        benchmark = hh_size * 135 * 30
        billed_base = round(
            benchmark * (rng.uniform(0.35, 0.65) if is_theft else rng.uniform(0.92, 1.08))
        )
        for _ in range(3):
            rows.append({
                "billed_litres": round(billed_base * rng.uniform(0.95, 1.05)),
                "benchmark_litres": benchmark,
                "household_size": hh_size,
                "_theft": is_theft,
            })

    for _ in range(9):
        add_household(True)
    for _ in range(124):
        add_household(False)

    df = pd.DataFrame(rows)
    y_true = df["_theft"].values

    det = mba.BillingAnomalyDetector(
        contamination=mba.CONTAMINATION, random_state=42
    ).fit(df)
    y_pred = det.predict_anomaly(df) >= mba.FLAG_THRESHOLD

    tp = int((y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    assert recall >= 0.99, f"resample recall {recall:.2f} diverged from live recall 1.00"
    assert precision >= 0.80, f"resample precision {precision:.2f} below tuned floor"


def test_agent_tool_agrees_with_audit_endpoint():
    """
    The AI Copilot cites run_billing_anomaly(); judges compare that number
    against GET /audit/billing/{zone_id} on the BillingAudit screen. Both
    must run the same model at the same threshold or the demo contradicts
    itself. (Found after Person 3's agent landed reading the static rule
    columns instead — 22 vs 32 flagged on zone_2.)
    """
    from fastapi.testclient import TestClient
    from backend.app.agent.tools import run_billing_anomaly
    from backend.app.main import app

    # Train exactly as app startup does, so both paths see one model
    mba.train_detector(_load_seeded_billing())
    client = TestClient(app)

    for zone_id, expect_flags in (("zone_2", True), ("zone_8", False)):
        tool = run_billing_anomaly(zone_id)
        audit = client.get(f"/audit/billing/{zone_id}").json()

        assert tool["status"] == "SUCCESS"
        assert tool["detection_method"] == "isolation_forest"
        assert tool["anomaly_count"] == audit["total_anomalies"], (
            f"{zone_id}: Copilot says {tool['anomaly_count']}, "
            f"audit endpoint says {audit['total_anomalies']}"
        )
        assert tool["total_accounts_audited"] == audit["total_records"]

        if audit["total_anomalies"]:
            # Highest-scoring household must be the same in both
            assert tool["top_suspicious_consumer_ids"][0] == audit["items"][0]["consumer_id"]
        if expect_flags:
            assert tool["anomaly_count"] > 0
        else:
            assert tool["anomaly_count"] == 0, "clean zone flagged by one path only"


def test_agent_tool_falls_back_to_rule_when_model_untrained():
    """Untrained model => stored rule column, clearly labelled as fallback."""
    from backend.app.agent.tools import run_billing_anomaly

    saved = mba._detector
    mba._detector = None
    try:
        tool = run_billing_anomaly("zone_2")
        assert tool["status"] == "SUCCESS"
        assert tool["detection_method"] == "rule_fallback"
        assert tool["anomaly_count"] >= 0
    finally:
        mba._detector = saved


def test_tuned_constants_are_documented_and_sane():
    """Guards the sweep table in ml_billing_anomaly.py against silent edits."""
    assert mba.MODERATE_THRESHOLD < mba.FLAG_THRESHOLD < 1.0
    assert 0 < mba.FALLBACK_RATIO < 1
    assert 0 < mba.CONTAMINATION < 1


def test_explanation_bands_align_with_flag_threshold():
    """
    'Strong anomaly' text must agree with the actual flag decision, and the
    severity text must never increase as the score falls.
    """
    mba.train_detector(
        pd.DataFrame([
            {"billed_litres": b, "benchmark_litres": BENCHMARK, "household_size": 4}
            for b in [
                *[round(BENCHMARK * r) for r in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60)],
                *[round(BENCHMARK * r) for r in (0.92, 0.95, 1.00, 1.05, 1.08)],
            ]
        ])
    )

    severity = {"Strong": 2, "Moderate": 1, "No anomaly": 0}
    any_flagged = False

    for ratio in (0.35, 0.45, 0.55, 0.70, 0.90, 1.00, 1.10):
        flagged, expl = mba.is_anomaly(billed=BENCHMARK * ratio, benchmark=BENCHMARK)
        level = next(v for k, v in severity.items() if expl["recommendation"].startswith(k))
        score = float(expl["ml_score"])

        # The text and the flag must never disagree
        if flagged:
            any_flagged = True
            assert level == 2, f"flagged at ratio {ratio} but got: {expl['recommendation']}"
            assert score >= mba.FLAG_THRESHOLD
        else:
            assert level < 2, f"unflagged at ratio {ratio} but text says strong anomaly"

        # Band boundaries must match the documented constants
        if score >= mba.FLAG_THRESHOLD:
            assert level == 2
        elif score >= mba.MODERATE_THRESHOLD:
            assert level == 1
        else:
            assert level == 0

    assert any_flagged, "detector flagged nothing in the sweep — bands untested"

    # An honest household is never presented as a strong anomaly
    _, honest = mba.is_anomaly(billed=BENCHMARK, benchmark=BENCHMARK)
    assert not honest["recommendation"].startswith("Strong")
