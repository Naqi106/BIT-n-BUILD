"""
Trend Forecasting Model — Person 1 (Data + ML), Hours 10-15 (optional Tier 1)

Roadmap: "'If unfixed, projected loss over next 30 days is X litres / Rs Y' —
ties directly into the payback-period/ROI story." Marked optional/bonus, so it
follows the same defensive pattern as the other engines: a primary path and a
documented degraded path if scikit-learn cannot be loaded.

Primary path : sklearn LinearRegression over daily-loss and NRW-percentage
               series extracted from the nrw_snapshots table.
Fallback path : naive carry-forward (flat trend at the recent average) — the
               forecast still returns, clearly labelled with its method.

Usage
-----
    from backend.app.engines.trend_forecast import forecast

    result = forecast(snapshots_df, tariff_rate=0.005, horizon_days=30)
    if result["is_sufficient"]:
        print(result["interpretation"])
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

MIN_POINTS = 3          # below this a line fit is meaningless
HORIZON_DAYS = 30       # the roadmap's "next 30 days" claim
STABLE_BAND_PCT = 0.5   # |projected change| under this = no material trend
# Direction is always a one-sided question ("is loss increasing?"), so the
# critical values are one-sided: 1.645 = 95%, 2.33 = 99%.
T_SIGNIFICANCE = 1.645  # slope must clear this before we name a direction
T_HIGH = 2.33           # HIGH trend confidence


# ---------------------------------------------------------------------------
# Formatting helpers (shared by the endpoint's human-readable line)
# ---------------------------------------------------------------------------

def format_rupees(amount: float) -> str:
    """Indian numbering: Rs 1.23 crore / Rs 45.6 lakh / Rs 7,890."""
    if amount >= 1e7:
        return f"Rs {amount / 1e7:,.2f} crore"
    if amount >= 1e5:
        return f"Rs {amount / 1e5:,.2f} lakh"
    return f"Rs {amount:,.0f}"


def format_litres(litres: float) -> str:
    """Million litres (ML) for cumulative volumes, MLD for daily rates."""
    if abs(litres) >= 1e6:
        return f"{litres / 1e6:,.2f} ML"
    return f"{litres:,.0f} litres"


def _confidence_from_t(t_stat: float) -> str:
    """Trend confidence from the slope's t-statistic, not from r2: with 13
    noisy weekly points r2 stays low even when the slope is 3x its standard
    error, so r2 would under-report a genuinely reliable trend."""
    if t_stat >= T_HIGH:
        return "HIGH"
    if t_stat >= T_SIGNIFICANCE:
        return "MEDIUM"
    return "LOW"


def _direction(change_pct: float, t_stat: float) -> str:
    """
    WORSENING/IMPROVING only when the slope is both statistically
    significant (one-sided t >= 1.645, i.e. 95%) AND material over the
    horizon (>= STABLE_BAND_PCT); otherwise the honest answer is STABLE.

    Both conditions matter: the seed data carries +-1.5pp of week-to-week
    noise, so a positive slope on its own proves nothing, and a significant
    0.1% drift would be technically true but meaningless to a judge.
    """
    if t_stat >= T_SIGNIFICANCE and change_pct > STABLE_BAND_PCT:
        return "WORSENING"
    if t_stat >= T_SIGNIFICANCE and change_pct < -STABLE_BAND_PCT:
        return "IMPROVING"
    return "STABLE"


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------

def _fit_line(
    x: np.ndarray, y: np.ndarray
) -> tuple[float, float, float, float, str]:
    """
    Least-squares fit returning (slope, intercept, r_squared, slope_se, method).

    Primary : sklearn LinearRegression (roadmap's scikit-learn model list).
    Fallback: flat line at the series mean if sklearn cannot be imported —
              clearly reported so no caller mistakes it for a real trend.

    slope_se is the standard error of the slope; the caller turns it into a
    t-statistic so a trend is only called WORSENING/IMPROVING when it is
    distinguishable from the seed data's week-to-week noise.
    """
    try:
        from sklearn.linear_model import LinearRegression

        model = LinearRegression().fit(x.reshape(-1, 1), y)
        slope = float(model.coef_[0])
        intercept = float(model.intercept_)
        r2 = float(model.score(x.reshape(-1, 1), y))

        residuals = y - model.predict(x.reshape(-1, 1))
        n = len(x)
        sxx = float(np.sum((x - x.mean()) ** 2))
        if n > 2 and sxx > 0:
            sse = float(np.sum(residuals ** 2))
            slope_se = float(np.sqrt((sse / (n - 2)) / sxx))
        else:
            slope_se = 0.0

        return slope, intercept, max(0.0, min(1.0, r2)), slope_se, "linear_regression"
    except Exception:  # pragma: no cover - exercised only without sklearn
        return 0.0, float(np.mean(y)), 0.0, 0.0, "naive_carry_forward"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def forecast(
    snapshots: pd.DataFrame,
    tariff_rate: float = 0.005,
    horizon_days: int = HORIZON_DAYS,
    zone_id: Optional[str] = None,
) -> dict:
    """
    Project future non-revenue water loss from historical snapshots.

    Parameters
    ----------
    snapshots : DataFrame with columns [timestamp, loss_litres, nrw_percentage]
                — loss_litres is a DAILY loss volume observed per snapshot.
    tariff_rate : Rs per litre (zone tariff, default town rate).
    horizon_days : forecast window, default 30 per the roadmap phrasing.

    Returns a JSON-safe dict. ``is_sufficient`` is False (never an exception)
    when there is not enough history, so the caller can show an explicit
    "not enough data" state instead of a fabricated number.
    """
    label = zone_id or "the town"

    required = {"timestamp", "loss_litres", "nrw_percentage"}
    if snapshots is None:
        raise ValueError(f"forecast() requires columns {sorted(required)}")
    if snapshots.empty or len(snapshots.columns) == 0:
        # A zone with no snapshot history yet is a data-absence state, not
        # malformed input -- report it honestly instead of raising (a zero-
        # row load yields a column-less frame, which would otherwise trip
        # the required-columns check below).
        return {
            "zone_id": zone_id,
            "is_sufficient": False,
            "observations": 0,
            "required_observations": MIN_POINTS,
            "message": (
                f"{label}: no snapshots recorded yet — nothing to project a trend from."
            ),
        }
    if not required.issubset(snapshots.columns):
        raise ValueError(f"forecast() requires columns {sorted(required)}")

    df = snapshots[list(required)].dropna().copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna().sort_values("timestamp").reset_index(drop=True)

    if len(df) < MIN_POINTS:
        return {
            "zone_id": zone_id,
            "is_sufficient": False,
            "observations": int(len(df)),
            "required_observations": MIN_POINTS,
            "message": (
                f"{label}: only {len(df)} snapshot(s) available — "
                f"at least {MIN_POINTS} are needed to project a trend."
            ),
        }

    t0 = df["timestamp"].iloc[0]
    x = (df["timestamp"] - t0).dt.total_seconds().to_numpy() / 86400.0
    loss = df["loss_litres"].to_numpy(dtype=float)
    nrw = df["nrw_percentage"].to_numpy(dtype=float)

    loss_slope, loss_intercept, loss_r2, loss_se, method = _fit_line(x, loss)
    nrw_slope, nrw_intercept, nrw_r2, _, _ = _fit_line(x, nrw)

    # t-statistic of the loss slope (capped: JSON has no Infinity)
    if loss_se > 0:
        t_stat = min(abs(loss_slope) / loss_se, 99.0)
    else:
        t_stat = 99.0 if loss_slope != 0 else 0.0

    # Recent baseline: mean of the last 3 snapshots, less jumpy than the last row
    tail = min(3, len(df))
    current_daily_loss = float(np.mean(loss[-tail:]))
    current_nrw = float(np.mean(nrw[-tail:]))

    x_last = float(x[-1])
    x_end = x_last + horizon_days
    projected_daily_loss = loss_intercept + loss_slope * x_end
    projected_nrw = nrw_intercept + nrw_slope * x_end

    # Cumulative loss over the horizon: sum of the fitted daily value per day
    days = np.arange(1, horizon_days + 1, dtype=float)
    cumulative = float(np.sum(loss_intercept + loss_slope * (x_last + days)))
    projected_rupees = cumulative * float(tariff_rate)

    change_pct = (
        (projected_daily_loss - current_daily_loss) / current_daily_loss * 100.0
        if current_daily_loss > 0
        else 0.0
    )
    direction = _direction(change_pct, t_stat)
    confidence = _confidence_from_t(t_stat)

    interpretation = (
        f"If unfixed, {label} is projected to lose "
        f"{format_litres(cumulative)} over the next {horizon_days} days "
        f"({format_rupees(projected_rupees)} at Rs {tariff_rate}/litre); "
        f"daily loss moves from {format_litres(current_daily_loss)}/day to "
        f"{format_litres(projected_daily_loss)}/day and NRW from "
        f"{current_nrw:.1f}% to {projected_nrw:.1f}% "
        f"[trend: {direction}, confidence: {confidence}]."
    )

    return {
        "zone_id": zone_id,
        "is_sufficient": True,
        "method": method,
        "observations": int(len(df)),
        "window_days": float(x_last),
        "horizon_days": int(horizon_days),
        "tariff_rate": float(tariff_rate),
        # loss trend (daily volume)
        "current_loss_litres_per_day": round(current_daily_loss, 2),
        "projected_loss_litres_per_day": round(projected_daily_loss, 2),
        "loss_slope_litres_per_day_per_day": round(loss_slope, 2),
        "loss_change_pct": round(change_pct, 2),
        "loss_r2": round(loss_r2, 3),
        "slope_t_stat": round(t_stat, 2),
        "trend_confidence": confidence,
        "direction": direction,
        # cumulative projection
        "projected_loss_litres": round(cumulative, 2),
        "projected_loss_rupees": round(projected_rupees, 2),
        # NRW trend (percentage points)
        "current_nrw_pct": round(current_nrw, 2),
        "projected_nrw_pct": round(projected_nrw, 2),
        "nrw_slope_pp_per_day": round(nrw_slope, 5),
        "nrw_r2": round(nrw_r2, 3),
        "interpretation": interpretation,
    }


def load_zone_snapshots(db, zone_id: str) -> pd.DataFrame:
    """Load a zone's snapshots as a DataFrame, oldest first."""
    from backend.data.db_schema import NRWSnapshot

    rows = (
        db.query(NRWSnapshot)
        .filter(NRWSnapshot.zone_id == zone_id)
        .order_by(NRWSnapshot.timestamp)
        .all()
    )
    return pd.DataFrame([{
        "timestamp": r.timestamp,
        "loss_litres": r.loss_litres,
        "nrw_percentage": r.nrw_percentage,
    } for r in rows])


def load_town_snapshots(db) -> pd.DataFrame:
    """
    Town-wide series: daily loss summed across every REGISTERED zone.

    Guards against stray rows so one bad row cannot corrupt the town total:
      * only snapshots whose zone_id exists in the zones table count;
      * snapshots are bucketed into weeks and de-duplicated per zone+week
        (latest wins), so a zone seeded twice is never double-counted;
      * only weeks reported by the maximum number of zones are kept, so a
        bucket holding a couple of stray rows is dropped instead of dragging
        the town-wide loss down by orders of magnitude.
    """
    from backend.data.db_schema import NRWSnapshot, Zone

    empty = pd.DataFrame(columns=["timestamp", "loss_litres", "nrw_percentage"])

    registered = {row[0] for row in db.query(Zone.id).all()}
    rows = db.query(NRWSnapshot).all()
    if not rows or not registered:
        return empty

    frame = pd.DataFrame([{
        "zone_id": r.zone_id,
        "timestamp": r.timestamp,
        "loss_litres": r.loss_litres,
        "nrw_percentage": r.nrw_percentage,
    } for r in rows])
    frame = frame[frame["zone_id"].isin(registered)].copy()
    if frame.empty:
        return empty

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    if frame.empty:
        return empty

    frame["bucket"] = frame["timestamp"].dt.floor("7D")
    frame = (
        frame.sort_values("timestamp")
        .groupby(["zone_id", "bucket"], as_index=False)
        .last()
    )

    per_bucket = (
        frame.groupby("bucket")
        .agg(
            loss_litres=("loss_litres", "sum"),
            nrw_percentage=("nrw_percentage", "mean"),
            zones=("zone_id", "nunique"),
        )
        .reset_index()
    )
    complete = per_bucket[per_bucket["zones"] == per_bucket["zones"].max()]
    complete = complete.sort_values("bucket")
    if complete.empty:
        return empty

    return pd.DataFrame({
        "timestamp": complete["bucket"].to_numpy(),
        "loss_litres": complete["loss_litres"].to_numpy(),
        "nrw_percentage": complete["nrw_percentage"].to_numpy(),
    })
