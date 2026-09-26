"""
Unit tests — Model 3: NRW trend forecasting (Tier 1 optional)
Person 1 (Data + ML), Hours 10-15 roadmap deliverable.

    python -m pytest backend/test/test_trend_forecast.py -v

Covers the roadmap's headline claim: "'If unfixed, projected loss over next
30 days is X litres / Rs Y'" — direction, cumulative projection, rupee
arithmetic, explicit insufficient-data behaviour, and the seeded worsening
zones (zone_3 Indira Nagar, zone_6 Chowk get a +0.4pp/week trend in
lucknow_seed.py from week 6 onward).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.engines.trend_forecast import (
    HORIZON_DAYS,
    MIN_POINTS,
    STABLE_BAND_PCT,
    T_HIGH,
    T_SIGNIFICANCE,
    forecast,
    format_litres,
    format_rupees,
)


def series(values, start="2026-06-27", freq="7D") -> pd.DataFrame:
    """Weekly snapshots of a DAILY loss volume, as lucknow_seed.py writes them."""
    stamps = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.DataFrame({
        "timestamp": stamps,
        "loss_litres": values,
        "nrw_percentage": [v / 500_000 for v in values],  # arbitrary but monotone
    })


# ---------------------------------------------------------------------------
# 1. Contract: range, method, r2
# ---------------------------------------------------------------------------

def test_worsening_trend_is_detected():
    loss = [25_000_000 + 100_000 * i for i in range(13)]  # +100 ML/week
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert result["is_sufficient"] is True
    assert result["method"] == "linear_regression"
    assert result["loss_slope_litres_per_day_per_day"] > 0
    assert result["direction"] == "WORSENING"
    assert result["loss_r2"] == pytest.approx(1.0, abs=1e-3)
    assert result["trend_confidence"] == "HIGH"


def test_improving_trend_is_detected():
    loss = [25_000_000 - 100_000 * i for i in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert result["direction"] == "IMPROVING"
    assert result["loss_slope_litres_per_day_per_day"] < 0


def test_flat_trend_is_stable():
    loss = [25_000_000] * 13
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert result["direction"] == "STABLE"
    assert result["loss_change_pct"] == pytest.approx(0.0, abs=0.01)


def test_noisy_flat_series_stays_within_stable_band():
    """Noise alone must not be reported as a worsening trend."""
    rng = np.random.default_rng(42)
    loss = [25_000_000 + rng.normal(0, 200_000) for _ in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert abs(result["loss_change_pct"]) <= STABLE_BAND_PCT
    assert result["direction"] in {"STABLE", "IMPROVING", "WORSENING"}
    assert result["trend_confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_r2_and_confidence_stay_in_range():
    rng = np.random.default_rng(1)
    loss = [25_000_000 + 50_000 * i + rng.normal(0, 1_500_000) for i in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert 0.0 <= result["loss_r2"] <= 1.0
    assert 0.0 <= result["nrw_r2"] <= 1.0
    assert 0.0 <= result["slope_t_stat"] <= 99.0

    # Confidence is derived from the slope's t-statistic, not r2
    t = result["slope_t_stat"]
    if t >= T_HIGH:
        assert result["trend_confidence"] == "HIGH"
    elif t >= T_SIGNIFICANCE:
        assert result["trend_confidence"] == "MEDIUM"
    else:
        assert result["trend_confidence"] == "LOW"
        # A slope indistinguishable from noise must never be called a trend
        assert result["direction"] == "STABLE"


def test_noise_only_slope_is_reported_as_stable():
    """13 noisy points with no real trend => STABLE, low confidence."""
    rng = np.random.default_rng(42)
    loss = [25_000_000 + rng.normal(0, 800_000) for _ in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    assert result["direction"] == "STABLE"
    assert result["trend_confidence"] == "LOW"


# ---------------------------------------------------------------------------
# 2. The roadmap's headline number: 30-day cumulative loss + rupees
# ---------------------------------------------------------------------------

def test_cumulative_projection_lies_between_rate_bounds():
    loss = [25_000_000 + 100_000 * i for i in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_x")

    n = result["horizon_days"]
    low = n * result["current_loss_litres_per_day"]
    high = n * result["projected_loss_litres_per_day"]

    assert low <= result["projected_loss_litres"] <= high
    assert result["horizon_days"] == HORIZON_DAYS


def test_rupees_equal_litres_times_tariff():
    loss = [25_000_000 + 100_000 * i for i in range(13)]
    tariff = 0.005
    result = forecast(series(loss), tariff_rate=tariff, zone_id="zone_x")

    expected = result["projected_loss_litres"] * tariff
    assert abs(result["projected_loss_rupees"] - expected) < 0.5


def test_longer_horizon_projects_more_loss_when_worsening():
    loss = [25_000_000 + 100_000 * i for i in range(13)]
    df = series(loss)

    r30 = forecast(df, tariff_rate=0.005, horizon_days=30)
    r60 = forecast(df, tariff_rate=0.005, horizon_days=60)

    assert r60["projected_loss_litres"] > r30["projected_loss_litres"]
    assert r60["projected_loss_rupees"] > r30["projected_loss_rupees"]


def test_interpretation_names_the_30_day_claim():
    loss = [25_000_000 + 100_000 * i for i in range(13)]
    result = forecast(series(loss), tariff_rate=0.005, zone_id="zone_3")

    text = result["interpretation"]
    assert "next 30 days" in text
    assert "Rs" in text
    assert "zone_3" in text
    assert "NRW from" in text


# ---------------------------------------------------------------------------
# 3. Explicit insufficient-data behaviour (never a fabricated number)
# ---------------------------------------------------------------------------

def test_too_few_snapshots_returns_explicit_message():
    result = forecast(series([25_000_000, 25_100_000]), zone_id="zone_new")

    assert result["is_sufficient"] is False
    assert result["observations"] == 2
    assert result["required_observations"] == MIN_POINTS
    assert "at least" in result["message"]
    assert "projected_loss_litres" not in result


def test_empty_frame_is_insufficient_not_a_crash():
    empty = pd.DataFrame(columns=["timestamp", "loss_litres", "nrw_percentage"])
    result = forecast(empty, zone_id="zone_new")
    assert result["is_sufficient"] is False
    assert result["observations"] == 0


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="timestamp"):
        forecast(pd.DataFrame({"loss_litres": [1, 2, 3]}))


# ---------------------------------------------------------------------------
# 4. Formatting helpers for the pitch line
# ---------------------------------------------------------------------------

def test_format_rupees_indian_units():
    assert format_rupees(650_700_000) == "Rs 65.07 crore"
    assert format_rupees(5_400_000) == "Rs 54.00 lakh"
    assert format_rupees(7_890) == "Rs 7,890"


def test_format_litres_units():
    assert format_litres(10_725_000_000) == "10,725.00 ML"
    assert format_litres(850_000) == "850,000 litres"


# ---------------------------------------------------------------------------
# 5. Integration against the seeded Lucknow snapshots
# ---------------------------------------------------------------------------

def _load(zone_id: str) -> pd.DataFrame:
    try:
        from backend.app.db import SessionLocal
        from backend.app.engines.trend_forecast import load_zone_snapshots, load_town_snapshots

        db = SessionLocal()
        try:
            df = (load_town_snapshots(db) if zone_id == "town"
                  else load_zone_snapshots(db, zone_id))
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unavailable: {exc}")

    if len(df) < MIN_POINTS:
        pytest.skip("seed data not present — run backend/data/lucknow_seed.py")
    return df


def test_seeded_worsening_zone_outranks_stable_zone():
    """
    lucknow_seed.py gives zone_3 (Indira Nagar) and zone_6 (Chowk) a
    +0.4pp/week NRW trend from week 6 onward, while zone_1 (Hazratganj)
    and zone_8 (Chinhat) only drift randomly. The fitted trends must
    separate the seeded worsening zones from the randomly drifting ones.
    """
    z3 = forecast(_load("zone_3"), tariff_rate=0.005, zone_id="zone_3")
    z6 = forecast(_load("zone_6"), tariff_rate=0.005, zone_id="zone_6")
    z1 = forecast(_load("zone_1"), tariff_rate=0.005, zone_id="zone_1")
    z8 = forecast(_load("zone_8"), tariff_rate=0.005, zone_id="zone_8")

    for r in (z3, z6, z1, z8):
        assert r["is_sufficient"] and r["observations"] >= 10

    # Seeded worsening zones are named as worsening, the stronger one with
    # high confidence; both outrank the drifting zones on slope.
    assert z6["direction"] == "WORSENING"
    assert z6["trend_confidence"] in {"MEDIUM", "HIGH"}
    assert z3["direction"] == "WORSENING"
    assert z3["loss_slope_litres_per_day_per_day"] > z1["loss_slope_litres_per_day_per_day"]
    assert z6["loss_slope_litres_per_day_per_day"] > z8["loss_slope_litres_per_day_per_day"]

    # Randomly drifting zones are never reported as worsening
    assert z1["direction"] == "STABLE"
    assert z8["direction"] != "WORSENING"


def test_forecast_endpoints():
    """GET /data/nrw-forecast (town) and /{zone_id} (zone) respond and 404 cleanly."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    town = client.get("/data/nrw-forecast")
    assert town.status_code == 200
    body = town.json()
    assert body["is_sufficient"] is True
    assert "next 30 days" in body["interpretation"]
    assert body["projected_loss_rupees"] > 0

    zone = client.get("/data/nrw-forecast/zone_6")
    assert zone.status_code == 200
    assert zone.json()["zone_id"] == "zone_6"
    assert zone.json()["observations"] >= MIN_POINTS

    missing = client.get("/data/nrw-forecast/zone_does_not_exist")
    assert missing.status_code == 404

    bad = client.get("/data/nrw-forecast", params={"horizon_days": 9999})
    assert bad.status_code == 422  # Query(ge=1, le=365) guard


def test_town_forecast_is_consistent_with_the_650m_anchor():
    """
    30-day town projection must reconcile with the published ~Rs 650 million
    annual loss anchor (README + town-profile endpoint): monthly ~= 650M/12.
    """
    town = forecast(_load("town"), tariff_rate=0.005)

    assert town["is_sufficient"] is True
    monthly = town["projected_loss_rupees"]
    assert 40_000_000 <= monthly <= 70_000_000, f"Rs {monthly:,.0f} for 30 days looks off"

    annualised = monthly * 12
    assert abs(annualised - 650e6) / 650e6 < 0.20, (
        f"annualised Rs {annualised/1e6:.0f}M not near the Rs 650M anchor"
    )
