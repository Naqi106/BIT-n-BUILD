"""
Threshold tuning sweep — Person 1 (Data + ML), Hours 10-15.

    python -m backend.test.tune_thresholds

Tunes the Isolation Forest operating point against the LIVE seeded Lucknow
billing data, using ground-truth labels derived from lucknow_seed.py's own
generation rule:

    theft   : billed 35-65%  of benchmark  ->  ratio < 0.70
    normal  : billed 92-108% of benchmark  ->  ratio >= 0.70

Because FLAG_THRESHOLD is anchored to the model's contamination boundary
(score 0.50 <=> decision_function 0), `contamination` is the only real knob.
Each candidate is scored twice — once on the live DB and once on an
independent synthetic re-sample drawn from the identical generation rule — and
a configuration only counts as tuned if BOTH reproduce. That check is what
rejected min-max normalisation (recall swung 0.59 -> 1.00 between samples).

The winning constants are hard-coded in
backend/app/engines/ml_billing_anomaly.py and re-asserted by
backend/test/test_ml_billing.py::test_tuned_thresholds_hold_on_seeded_data.
"""

from __future__ import annotations

import random

import numpy as np
import pandas as pd

from backend.app.engines.ml_billing_anomaly import (
    CONTAMINATION,
    FLAG_THRESHOLD,
    BillingAnomalyDetector,
)

THEFT_ZONES = {"zone_2", "zone_4", "zone_6"}
CLEAN_ZONE = "zone_8"

CONTAMINATION_SWEEP = [0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15, 0.20]
PRECISION_FLOOR = 0.80
RECALL_FLOOR = 0.99


def load_seeded_billing() -> pd.DataFrame:
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

    if not rows:
        raise SystemExit("No billing records — run backend/data/lucknow_seed.py first.")

    df = pd.DataFrame(
        [{
            "zone_id": r[0],
            "billed_litres": r[1],
            "benchmark_litres": r[2],
            "household_size": r[3] or 4,
        } for r in rows]
    )
    df["is_theft"] = (df["billed_litres"] / df["benchmark_litres"]) < 0.70
    return df


def resample_seeded_billing(seed: int = 7) -> pd.DataFrame:
    """Independent synthetic re-sample with lucknow_seed.py's exact rule."""
    rng = random.Random(seed)
    rows = []

    def add_household(is_theft: bool) -> None:
        hh_size = rng.randint(3, 7)
        benchmark = hh_size * 135 * 30
        billed_base = round(
            benchmark * (rng.uniform(0.35, 0.65) if is_theft else rng.uniform(0.92, 1.08))
        )
        for _ in range(3):
            rows.append({
                "zone_id": "resample",
                "billed_litres": round(billed_base * rng.uniform(0.95, 1.05)),
                "benchmark_litres": benchmark,
                "household_size": hh_size,
                "is_theft": is_theft,
            })

    for _ in range(9):
        add_household(True)
    for _ in range(124):
        add_household(False)
    return pd.DataFrame(rows)


def score(df: pd.DataFrame, contamination: float) -> np.ndarray:
    det = BillingAnomalyDetector(contamination=contamination, random_state=42).fit(df)
    return det.predict_anomaly(df)


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return precision, recall, f1


def zone_ranking_ok(df: pd.DataFrame, scores: np.ndarray) -> bool:
    tmp = df.copy()
    tmp["score"] = scores
    means = tmp.groupby("zone_id")["score"].mean()
    theft_mean = means[means.index.isin(THEFT_ZONES)].mean()
    clean_mean = means.get(CLEAN_ZONE, np.nan)
    return bool(theft_mean > clean_mean)


def main() -> None:
    live = load_seeded_billing()
    synth = resample_seeded_billing()
    print(f"live     : {len(live)} records, {int(live.is_theft.sum())} ground-truth theft, "
          f"{live.zone_id.nunique()} zones")
    print(f"resample : {len(synth)} records, {int(synth.is_theft.sum())} ground-truth theft")
    print(f"flag threshold held at {FLAG_THRESHOLD} (model contamination boundary)\n")

    rows = []
    for contamination in CONTAMINATION_SWEEP:
        live_scores = score(live, contamination)
        synth_scores = score(synth, contamination)
        live_pred = live_scores >= FLAG_THRESHOLD
        synth_pred = synth_scores >= FLAG_THRESHOLD

        lp, lr, lf = prf(live.is_theft.values, live_pred)
        sp, sr, sf = prf(synth.is_theft.values, synth_pred)
        rows.append({
            "contamination": contamination,
            "flagged_pct": float(live_pred.mean()),
            "live_precision": lp,
            "live_recall": lr,
            "live_f1": lf,
            "synth_precision": sp,
            "synth_recall": sr,
            "synth_f1": sf,
            "zones_ok": zone_ranking_ok(live, live_scores),
        })

    table = pd.DataFrame(rows)
    fmt = {c: "{:.3f}".format for c in table.columns if table[c].dtype.kind == "f"}
    fmt["flagged_pct"] = "{:.1%}".format
    print(table.to_string(index=False, formatters=fmt))

    eligible = table[
        (table["zones_ok"])
        & (table["live_precision"] >= PRECISION_FLOOR)
        & (table["live_recall"] >= RECALL_FLOOR)
        & (table["synth_precision"] >= PRECISION_FLOOR)
        & (table["synth_recall"] >= RECALL_FLOOR)
    ]
    if eligible.empty:
        raise SystemExit(f"\nNo contamination met precision>={PRECISION_FLOOR} "
                         f"and recall>={RECALL_FLOOR} on BOTH samples.")

    best = eligible.sort_values(
        ["live_f1", "synth_f1", "flagged_pct"], ascending=[False, False, True]
    ).iloc[0]

    print("\n=== RECOMMENDED ===")
    print(f"  contamination = {best['contamination']}"
          f"{'  (currently committed)' if best['contamination'] == CONTAMINATION else '  <-- CHANGE COMMITTED VALUE'}")
    print(f"  flag threshold= {FLAG_THRESHOLD}")
    print(f"  flagged       = {best['flagged_pct']:.1%} of households")
    print(f"  live  p/r/f1  = {best['live_precision']:.3f} / {best['live_recall']:.3f} / {best['live_f1']:.3f}")
    print(f"  synth p/r/f1  = {best['synth_precision']:.3f} / {best['synth_recall']:.3f} / {best['synth_f1']:.3f}")
    print(f"  zone ranking  = {best['zones_ok']}")


if __name__ == "__main__":
    main()
