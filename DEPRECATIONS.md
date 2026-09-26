# Deprecations

Section 4 of [`docs/roadmap.pdf`](docs/roadmap.pdf), split out into the repo as that
document instructs: being upfront about what was a prototype shortcut and what is now
finished is itself a credibility signal.

Status reflects this repository as it stands — **backend items are done, frontend items
are pending** because `frontend/src` is still placeholder-only.

| Item | Roadmap action | Status | What exists now |
|---|---|---|---|
| `confidence_score = 0.7` hardcoded constant | REPLACE | ✅ Done | Deleted, not merely unused. `engines/ml_confidence.py::compute_confidence()` scores completeness + reading count + variance + method agreement, and `latias.py` delegates to it. Guarded by `test_confidence_varies_with_input_not_a_constant` — if anything returns a fixed value again, the suite fails. |
| Rule-based `flag_anomalous_households()` 40% threshold | REPLACE *(keep as fallback)* | ✅ Done | Isolation Forest is the primary path (`engines/ml_billing_anomaly.py`, `CONTAMINATION=0.08`). The old rule survives only as the documented no-ML fallback (`FALLBACK_RATIO`), mirroring the Twilio/Groq fallback pattern rather than sitting around as dead code. `test_rule_fallback_*` covers it. |
| `demoNRWTrend` / `demoQualityTrend` arrays + fake-delay hooks | DELETE | ⏳ Pending (frontend) | No frontend chart code exists in this repo yet; charts must point at `GET /nrw/summary` when written. |
| Silent mock-zone fallback in `getZones()` | REPLACE | ⏳ Pending (frontend) | Must become a visible error/retry state. Never show unlabelled fake data as live. |
| Settings page "DEMO" badges on trend data | KEEP pattern, remove the need | ⏳ Pending (frontend) | Once real history is wired, the only thing still needing a badge is simulated PPA data — which should keep an honest label. |
| `simulate_ppa()` synthetic pressure readings | KEEP, but label clearly everywhere | ✅ Done | `GET /audit/ppa/{zone_id}` returns `is_simulated: true` on every node so the UI cannot forget to say "Simulated Level-1 sensor data". |
| `TARIFF_RATE_PER_LITRE` hardcoded module constant | UPGRADE | ✅ Done | Tariff is a per-zone column (`zones.tariff_rate`), consumed by payback, revenue recovery and the 30-day forecast (`/data/nrw-forecast` uses the zone's rate, town-wide uses the mean of zones). `DEFAULT_TARIFF_RATE` survives only as the documented default when a zone has none. |
| Manual-only `/revenue/recover`, nothing auto-populates `revenue_log` | AUTOMATE | ✅ Done | `POST /actions/resolve/{id}` writes `revenue_log` itself (`routers/actions.py`), so approved → executed → recovered populates without a manual POST. The manual endpoint is kept for demo control. |

## Corrections found during the rebuild

Not on the original list, but worth the same transparency:

- **`₹651 crore/year` → `₹650 million/year`.** The seed, the town-profile comment and the
  demo script all said "₹651 crore", which is 10× the figure the roadmap actually cites
  ("₹650M/yr"). The stored value was always right (`650_737_500` = ₹650.7 million ≈
  ₹65 crore) — only the labels were wrong. `verify_aggregate()` now asserts the annual
  loss against the ₹650M anchor so the mislabel cannot come back.
- **Test fixtures were writing to the shared demo database.** A `ZONE-TEST` row and the
  snapshots/alerts/actions it produced leaked into live data (13 zones instead of 12, and
  a town-wide forecast corrupted by ~2.7×). `backend/test/alltests.py` now deletes every
  row referencing the test zone on teardown, and the town aggregation ignores unregistered
  zones and incomplete weeks.
