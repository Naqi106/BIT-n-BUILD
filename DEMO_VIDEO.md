# AltoMare — Final Demo Video Script (2:45–3:15)

Integrated script: Team Larpers' narrative arc + verified click-path & on-screen strings.
Every "expect" below is the literal UI text from the code. Target **~3:05**.

---

## Fact-check deltas (why the final wording differs from the draft)

| Draft claim | Verdict | Final wording decision |
|---|---|---|
| "it's a ₹____ crores problem" (blank) | fill it | "**₹650.7 million** walking out annually" (never "₹651 crore") |
| "real, published water-loss data — not made-up numbers" | town anchors are published (AMRUT 2.0 / Jal Shakti, cited on landing); zone rows are computed live from the DB | "published anchors … not **hardcoded** mockups" |
| confidence = "a second model" | it's a computed weighted score: data completeness + reading count + variance + methods agreeing (the old hardcoded `0.7` was deleted) | "computed from data completeness, reading variance, and how many methods agree — not a fixed, made-up number" — your point stands |
| satellite "checks soil moisture" | live key-free Sentinel-2 catalog query = **real** scene date + cloud cover; NDWI score shows **`bands_not_configured`** with "no score is invented without them" | adjusted VO below matches the card exactly |
| copilot "action with estimated cost and payback" | ✅ verified — Recommendations show "cost/payback computed from real daily loss … L" + create-action button | kept as written |
| billing "ranked by suspicion score" | ✅ verified — "suspicion score 0–1" ScoreBars, anomalies first, Isolation Forest | kept as written |
| WhatsApp: "pushes straight… show screenshot" | ❌ trial wall — **no real delivery screenshot exists; never fabricate one** | point at the button + "wired to Twilio" phrasing + judge fallback line |

---

## 0. Pre-flight (once, before rehearsal)

```bash
python -m backend.data.lucknow_seed          # pristine: exactly ALT-1 (zone_2, CRITICAL)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000   # from repo root
cd frontend && npm run dev                   # http://localhost:5173
```
> ⚠️ **Use `localhost`, NOT `127.0.0.1`** — Vite binds `[::1]` only on this machine;
> `http://127.0.0.1:5173` connection-refuses. Backend stays on `127.0.0.1:8000` ✓
- `:8000/health` → 200; landing shows green **API Status ● 2.0.0**
- **Warm-up click-through of every page once** (dev server compiles on first visit)
- **Open the Satellite card once** (Zones → any zone → Satellite Second Opinion): expect
  green `OK` pill + real scene date/cloud + amber `bands_not_configured` pill.
  If it says `CATALOG_UNAVAILABLE` → fix network, or cut Section 3.
- **Run one Copilot investigation once** to pre-check answer quality (GROQ key live)
- DND on, chat apps closed, bookmarks hidden, zoom 100%, console closed, script on second screen
- DB at record time = **1 alert**; sidebar Live Alerts badge = 1
- Record-time banners = **seeded wording only** — if you ran the Copilot pre-check
  above, run the "Before the FINAL take" cleanup below afterwards; it rolls back
  investigation notes too (banner must not show a stray "(today)" prose entry)

**Timing realities (measured, so nothing feels "hung" on camera):** page API loads
take ~1.2–3 s (remote DB) — Billing audit ~5 s, Copilot investigation ~15 s,
satellite scene query ~2 s. Spinners are normal product behavior; rehearse the
pauses into your pacing. All 22 frontend modules + every GET endpoint are
pre-warmed — first-click compile lag is already eliminated.

---

## 🎬 INTRO (0:00–0:25)

**🖱** Open `http://localhost:5173/`. Hover green **API Status: ● 2.0.0 Online** → slow
scroll past hero → rest 2s on the citation card as the numbers are spoken → click
**"Get Started →"**.

**👀 Expect:** "Telemetry & Intelligence Active" · "Hello, Operator." · **"Let's plug the
leaks."** · stat card **"Annual revenue loss ₹650.7M"** · "55% town NRW and ₹650.7M/yr
revenue loss cited from **AMRUT 2.0 MIS** and the **Jal Shakti Annual Report** — every
figure traceable."

**🎤 VO:**
> "Every year, India loses nearly 40% of its treated water before it ever reaches a
> paying customer — and in Lucknow it's worse: 55% non-revenue water, of 650 million
> litres a day, ₹650.7 million walking out of the system every year. This isn't just a
> leak problem — it's a revenue problem. Most tools only hunt for physical pipe leaks.
> But almost half of that lost water isn't leaking out of pipes at all — it's water
> that's delivered, used, and never billed.
>
> This is AltoMare — a system that doesn't just find where water is being lost. It
> tells you why, ranks what to fix first by real return on investment, and tracks the
> actual revenue you recover after you fix it."

*(40% is a widely-cited national figure — keep it hedged with "nearly". If challenged,
fall back to the on-screen anchor: "Lucknow's own 55%, cited from AMRUT 2.0.")*

---

## 🗺 SECTION 1 — Dashboard & Real Data (0:25–0:50)

**🖱** Dashboard: hover the 4 KPI cards + trend chart (6s) → sidebar **Zones & DMAs** →
click **one** zone detail → hover Inflow / Billed / loss + sparkline (15s).

**👀 Expect:**
- Dashboard: **Town NRW Loss Rate ≈52.6%** ("anchor 55.0%") · **Daily Revenue at Risk**
  "₹…/day" + "Town anchor: ₹650.7M/yr" · **Active Leak Alerts = 1** ("1 critical, 0 high")
  · **Telemetry Coverage 100%** ("12 / 12 zones reporting this week") ·
  "Town NRW Trend vs 55.0% Anchor" (13 weekly points)
- Zones: **"District Metered Areas"** · zone detail: NRW, Inflow, Physical + app. loss,
  Billed, "**13 weekly snapshots**" sparkline

**🎤 VO:**
> "This is the live dashboard, built on published water-loss data — AMRUT 2.0 and Jal
> Shakti anchors, not hardcoded mockups. Each zone shows inflow, billed consumption,
> and the gap between them — that gap is Non-Revenue Water."

---

## 🔍 SECTION 2 — Detection Engine + Machine Learning (0:50–1:20)

**🖱**
1. Sidebar **Live Alerts** → point at the seeded **ALT-1** row (2s)
2. Run Detection strip → select **Chowk & Aminabad (zone_6)** (worst zone, ~70.6% NRW)
3. Click **▶ Run Detection** ("Running…") → read the verdict tiles
4. ⏱ *if on time:* click **Run Detection a 2nd time** → dedup banner, no new row

**👀 Expect:**
- Seeded row: **ALT-1 · Aliganj & Sector D · CRITICAL · 37,548,643 L/day · 98%** ·
  methods `water_balance,uarl,mnf`
- After run 1: rose banner **"Leak detected — Chowk & Aminabad · ALT-x filed"** + tiles
  **NRW ≈70.6%** / water-balance loss / UARL baseline / confidence · **new CRITICAL row
  at the top of the table**
- After run 2 (optional): **"ALT-x already ACTIVE (reused)"** + "…reused ALT-x instead
  of filing a duplicate row. Resolve it to re-arm detection." · no new row

**🎤 VO:**
> "Under the hood, AltoMare runs multiple independent checks — a component-based water
> audit, minimum night-flow analysis, and billing anomaly detection — to figure out
> whether a loss is a physical leak or something else.
>
> The billing anomaly check specifically runs on a machine-learning model — an Isolation
> Forest — trained to spot households whose consumption pattern looks statistically
> abnormal, without needing to hand-write rigid rules for every kind of fraud.
>
> Watch the engine run live on our worst zone." *(click)* "Verdict in seconds — a
> new alert filed — and that alert's confidence isn't a fixed number: it's computed from
> data completeness, reading variance, and how many methods agree."

---

## 🛰 SECTION 3 — Satellite Verification (1:20–1:35)

**🖱** Sidebar **Zones & DMAs** → open **Chowk & Aminabad** (the just-flagged zone) →
scroll to **"Satellite Second Opinion"** → point at the pills + source line.

**👀 Expect:** pills **`OK`** (live scene found) + **`bands_not_configured`** ·
interpretation paragraph · flag pills **`billing_anomaly`** / **`nrw_trend_worsening`** ·
"source: **Sentinel-2 L2A catalog via Element84 Earth Search (live, key-free)**" ·
message "…No score is invented without them."

**🎤 VO:**
> "For large, sustained leaks, AltoMare adds one more independent signal — free
> Sentinel-2 satellite imagery: a live query of the newest scene over that zone, paired
> with ground evidence — billing flags and the NRW trend. And where a reflectance number
> can't be computed honestly, the card says so instead of inventing one. A second
> opinion with zero extra hardware."

---

## 🤖 SECTION 4 — The AI Copilot (1:35–2:10)

**🖱** Sidebar **AI Copilot** (AGENT badge) → zone dropdown → **Chowk & Aminabad** →
keep prefilled question → **▶ Run Investigation** → after result: hover the
**Evidence trace** list, then the **Recommendations** card + its create-action button
(point, don't click).

**👀 Expect:** "Running investigation…" → verdict/summary in plain English ·
**"Evidence trace (N)"** listing real DB rows (alert, snapshots, forecast) ·
**"Recommendations (n)"** with line **"cost/payback computed from real daily loss … L"** ·
investigation memory panel · empty-state "The model returned an empty recommendation
list for this run" exists (honest degradation)

**🎤 VO:**
> "Here's where it comes together. Click on any flagged zone, and AltoMare's AI Copilot
> investigates it live — pulling real evidence, reasoning over it, and explaining in
> plain English what's happening. Every claim is backed by real data sitting right next
> to it — the alert, the snapshots, the forecast — in an evidence trace you can follow
> line by line.
>
> It recommends an action with an estimated cost and payback period — computed from the
> zone's real daily loss — and if it doesn't have enough evidence to be confident, it
> says so instead of guessing. One click turns any recommendation into a pending action
> for an officer."

---

## 📲 SECTION 5 — Field Alerts (2:10–2:20)

**🖱** Sidebar **Live Alerts** → on the **new zone_6 row** → **Dispatch Team** → modal
prefilled (action type, urgency from severity, **₹25000**, 30 days) →
**"Create dispatch action"** → toast → point at the **Revenue & Actions** sidebar badge
(now 1). Point at the **WhatsApp** button — **DO NOT CLICK IT.**

**👀 Expect:** modal **"Dispatch team — ALT-x · Chowk & Aminabad"** → toast **"Action #N
created for Chowk & Aminabad — pending officer approval. See Revenue & Actions."**

**🎤 VO:**
> "The moment a high-confidence alert is raised, AltoMare sends it to field staff in one
> click — the zone, the issue, and the recommended action: dispatch a crew through the
> officer workflow, or push the same alert over WhatsApp — the pipeline is wired
> straight to Twilio."

**⚠️ There is no real WhatsApp screenshot — do not fabricate one.** If a judge asks to
see it live, use this line:
> "The Twilio integration is live end-to-end — our account is on the free trial tier,
> which forces pre-approved templates, so we surface Twilio's exact status instead of
> faking a delivery. On the paid tier this sends as-is."

---

## 💰 SECTION 6 — Billing Fraud & Revenue Recovery (2:20–2:45)

**🖱**
1. Sidebar **Billing Audit** (ML badge) → stats → scroll the consumer table, point at
   ScoreBars (8–10s)
2. Sidebar **Revenue & Actions** → row = the action just created → **Approve** → toast →
   **Resolve** → modal **"Execute action #N"** → **"Mark resolved"** → toast → point at
   the new **revenue recovery row** (15s)

**👀 Expect:**
- Billing: "Records audited" · "Anomalies flagged" · **"suspicion score 0–1"** ·
  ScoreBars with anomalies flagged first · note "Nothing is executed until an officer
  approves" · "Export full audit (CSV)"
- Revenue: KPI **Pending 1** → after Approve: *"Action #N approved — it can now be
  executed (Resolve)."* → after Resolve: *"Action #N resolved — associated alert closed
  and a revenue recovery entry written to revenue_log."* → row RESOLVED + revenue table
  row (litres × tariff)

**🎤 VO:**
> "AltoMare also catches apparent losses. Here's the automatic billing audit list,
> ranked by suspicion score — every consumer scored zero to one by the model, flagged
> households surfaced first. Once an officer approves a fix, the Revenue Recovered
> tracker shows the actual money recovered — litres times tariff — tied directly to
> that action."

---

## 🎯 CLOSING (2:45–3:05)

**🖱** Sidebar **Dashboard** (rest on the KPI wall, 8s) → final frame: **Landing hero
"Let's plug the leaks."** (5s).

**🎤 VO:**
> "So that's AltoMare — one system that traces water loss, verifies it with machine
> learning and satellite data, tackles it with an AI investigator that shows its work,
> alerts field teams instantly, and converts loss into recovered revenue you can
> actually measure. Built to work with the data towns already have today — with 146
> automated tests keeping every number honest.
>
> This is Team Larpers, and this is AltoMare."

---

## 🚫 Traps — never on camera

| Never | Instead |
|---|---|
| Say **"₹651 crore"** | "**₹650.7 million**" exactly as shown |
| Click **WhatsApp** | point at it; fallback line ready above |
| Click **"Print full brief (PDF)"** | point only (system dialog ruins the take) |
| Call simulated data real | Leak page PPA = *simulated*, Contamination = *NOT_CONFIGURED* — say the labels aloud, they're selling points |
| First detect click on zone_2 | zone_2 already has ACTIVE ALT-1 → would show "reused" before "filed"; use **zone_6** |
| Live network dependency mid-take | satellite card + copilot both pre-tested in warm-up |

**Trim order if rehearsal runs long:** Section 6 billing glance → Section 2's optional
2nd detect click → Section 1 second page (keep KPI wall only) → drop the 40% national
sentence.

**If you finish early:** after Resolve, run Detection on zone_6 again → fresh alert
files (the resolved one re-arms detection) — full lifecycle on one zone.

## Before the FINAL take — seed does NOT clear alerts/actions/revenue/memory!

`lucknow_seed` never touches `LeakAlert` / `ActionLog` / `RevenueLog` /
`InvestigationMemory`, and Resolve writes an extra post-repair `NRWSnapshot`.
After a rehearsal (detect + dispatch + resolve + a Copilot investigation all
leave rows), restore the pristine on-camera state — exactly ALT-1, zero actions,
zero revenue, seeded "previously flagged" wording — from the repo root.
Children first (FK order matters: revenue → actions → alerts → snapshots/memory):

```bash
python -c "import sys; sys.path.insert(0, '.'); from datetime import datetime, timedelta, timezone; from backend.app.db import SessionLocal; from backend.data.db_schema import LeakAlert, ActionLog, RevenueLog, NRWSnapshot, InvestigationMemory; from sqlalchemy import or_, not_; stamp = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat(); db = SessionLocal(); db.query(RevenueLog).delete(); db.query(ActionLog).delete(); db.query(LeakAlert).filter(LeakAlert.id != 1).delete(); db.query(NRWSnapshot).filter(NRWSnapshot.inflow_litres == 100000, NRWSnapshot.timestamp >= stamp).delete(); db.query(InvestigationMemory).filter(InvestigationMemory.timestamp >= stamp, not_(or_(InvestigationMemory.summary.like('Quarterly billing audit%'), InvestigationMemory.summary.like('NRW trend review%')))).delete(); db.commit(); print('alerts:', db.query(LeakAlert).count(), '| actions:', db.query(ActionLog).count(), '| revenue:', db.query(RevenueLog).count(), '| snapshots:', db.query(NRWSnapshot).count(), '| memory:', db.query(InvestigationMemory).count()); db.close()"
```

What the two guarded filters do:

- **Post-repair snapshot** — every Resolve appends a zone_6 point with
  `inflow_litres == 100000` (the repair's fix value); the filter removes exactly
  those, recent-dated only, so a future seed is never touched.
- **Copilot memory** — every investigation appends a prose note that becomes the
  newest banner text. The filter drops recent non-seeded notes and keeps the
  seeded `Quarterly billing audit…` / `NRW trend review…` rows — the two live-DB
  tests in `test_investigation_memory.py` assert that exact wording, so run the
  suite only after this cleanup. (The take's own investigation re-appends entry
  #1 on camera, which is the demo beat anyway.)

**Never `python -m backend.data.lucknow_seed --clear`** — it FK-fails while
ALT-1 exists (zones cannot drop under the alert's foreign key). The one-liner
above is the sanctioned reset.

Re-verify: `GET /alerts` = 1 · `GET /actions/` = 0 · `GET /revenue/summary` = `[]`
· snapshots = 156 · memory = 8 rows, zone_6 banner = "NRW trend review…".
