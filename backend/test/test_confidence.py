"""
Unit tests — Model 2: confidence score (replaces the hardcoded 0.7)
Person 1 (Data + ML), Hours 7-10 roadmap deliverable.

    python -m pytest backend/test/test_confidence.py -v

Covers the four documented features from roadmap Section 3.3:
  data completeness, reading count, reading variance, method agreement.

The final test is a regression guard for Section 4 ("the fake constant must be
deleted, not just unused"): confidence must vary with its inputs.
"""

import pytest

from backend.app.engines.ml_confidence import (
    compute_confidence,
    get_confidence_breakdown,
    interpret,
)
from backend.app.engines.latias import calculate_dynamic_confidence, process_zone


FULL = dict(
    has_inflow=True,
    has_billing=True,
    has_mnf=True,
    reading_count=90,
    reading_variance=0.05,
    methods_agreed=3,
)

SPARSE = dict(
    has_inflow=True,
    has_billing=False,
    has_mnf=False,
    reading_count=5,
    reading_variance=0.40,
    methods_agreed=1,
)


# ---------------------------------------------------------------------------
# 1. Contract: range and type
# ---------------------------------------------------------------------------

def test_returns_float_within_unit_interval():
    score = compute_confidence(**FULL)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_sparse_input_also_stays_in_range():
    score = compute_confidence(**SPARSE)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 2. Feature: data completeness
# ---------------------------------------------------------------------------

def test_full_data_sources_score_higher_than_partial():
    full = compute_confidence(**FULL)
    partial = compute_confidence(
        has_inflow=True, has_billing=False, has_mnf=True,
        reading_count=90, reading_variance=0.05, methods_agreed=3,
    )
    assert full > partial


def test_each_missing_data_type_lowers_score():
    all_three = compute_confidence(True, True, True, 90, 0.05, 3)
    two = compute_confidence(True, True, False, 90, 0.05, 3)
    one = compute_confidence(True, False, False, 90, 0.05, 3)

    assert all_three > two > one


def test_inflow_only_is_low_confidence():
    """Missing billing + MNF means we must not hand back a confident number."""
    score = compute_confidence(
        has_inflow=True, has_billing=False, has_mnf=False,
        reading_count=1, reading_variance=0.9, methods_agreed=1,
    )
    assert score < 0.50
    assert "Low" in interpret(score)


# ---------------------------------------------------------------------------
# 3. Feature: reading count
# ---------------------------------------------------------------------------

def test_more_readings_never_lower_the_score():
    scores = [
        compute_confidence(True, True, True, n, 0.1, 3)
        for n in (1, 5, 10, 20, 50, 90)
    ]
    assert scores == sorted(scores), f"non-monotonic: {scores}"


def test_single_reading_is_penalised():
    one = compute_confidence(True, True, True, 1, 0.1, 3)
    many = compute_confidence(True, True, True, 90, 0.1, 3)
    assert many > one


# ---------------------------------------------------------------------------
# 4. Feature: reading variance
# ---------------------------------------------------------------------------

def test_higher_variance_lowers_score():
    stable = compute_confidence(True, True, True, 90, 0.02, 3)
    noisy = compute_confidence(True, True, True, 90, 0.60, 3)
    assert stable > noisy


def test_variance_extremes_do_not_break_range():
    zero_var = compute_confidence(True, True, True, 90, 0.0, 3)
    huge_var = compute_confidence(True, True, True, 90, 5.0, 3)
    assert 0.0 <= zero_var <= 1.0
    assert 0.0 <= huge_var <= 1.0


# ---------------------------------------------------------------------------
# 5. Feature: method agreement
# ---------------------------------------------------------------------------

def test_more_agreeing_methods_raise_score():
    one = compute_confidence(True, True, True, 90, 0.1, 1)
    two = compute_confidence(True, True, True, 90, 0.1, 2)
    three = compute_confidence(True, True, True, 90, 0.1, 3)
    assert one < two < three


def test_unknown_method_count_does_not_crash():
    score = compute_confidence(True, True, True, 90, 0.1, 7)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# 6. Regression guard — the deleted hardcoded 0.7 (roadmap Section 4)
# ---------------------------------------------------------------------------

def test_confidence_varies_with_input_not_a_constant():
    """Different evidence must never all collapse to one fixed number."""
    scores = {
        compute_confidence(**FULL),
        compute_confidence(**SPARSE),
        compute_confidence(True, True, False, 20, 0.3, 2),
        compute_confidence(False, False, False, 0, 1.0, 1),
    }
    assert len(scores) > 1, "confidence_score is effectively constant again"


def test_latias_delegates_to_ml_confidence():
    """process_zone() must not be able to return the old fixed 0.7."""
    rich = calculate_dynamic_confidence(
        has_inflow=True, has_billing=True, has_mnf=True,
        methods_count=3, readings_count=90, reading_variance=0.05,
    )
    poor = calculate_dynamic_confidence(
        has_inflow=True, has_billing=False, has_mnf=False,
        methods_count=1, readings_count=2, reading_variance=0.8,
    )
    assert rich != poor
    assert rich > poor


def test_process_zone_confidence_reflects_available_data():
    with_mnf = process_zone(
        "zone_t", inflow_litres=100_000, billed_litres=45_000,
        night_flow_litres=2_500, readings_count=90,
    )
    without_mnf = process_zone(
        "zone_t", inflow_litres=100_000, billed_litres=45_000,
        night_flow_litres=None, readings_count=5,
    )

    assert with_mnf["confidence_score"] != without_mnf["confidence_score"]
    assert with_mnf["confidence_score"] > without_mnf["confidence_score"]
    assert "mnf" in with_mnf["detection_methods"]
    assert "mnf" not in without_mnf["detection_methods"]


def test_process_zone_confidence_is_dynamic_across_zones():
    """Two zones with different evidence must not share one confidence number."""
    a = process_zone("zone_a", inflow_litres=58_000_000, billed_litres=22_000_000,
                     night_flow_litres=1_100_000, readings_count=90)
    b = process_zone("zone_b", inflow_litres=20_000_000, billed_litres=19_000_000,
                     night_flow_litres=None, readings_count=2)

    assert a["confidence_score"] != b["confidence_score"]
    assert a["confidence_score"] != 0.7
    assert b["confidence_score"] != 0.7


# ---------------------------------------------------------------------------
# 7. Breakdown + interpretation for the Copilot evidence UI
# ---------------------------------------------------------------------------

def test_breakdown_exposes_all_four_components():
    bd = get_confidence_breakdown("zone_2", **FULL)

    assert bd["zone_id"] == "zone_2"
    assert 0.0 <= bd["confidence_score"] <= 1.0
    assert set(bd["components"]) == {
        "data_completeness", "count_weight", "variance_weight", "method_weight",
    }
    assert bd["calculated_at"]
    assert bd["interpretation"]


def test_breakdown_is_consistent_with_compute_confidence():
    bd = get_confidence_breakdown("zone_4", **SPARSE)
    assert bd["confidence_score"] == compute_confidence(**SPARSE)


def test_interpretation_bands():
    assert "High" in interpret(0.90)
    assert "Moderate" in interpret(0.65)
    assert "Low" in interpret(0.30)
