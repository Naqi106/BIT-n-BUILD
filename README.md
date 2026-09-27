# AltoMare

**A digital solution for Non-Revenue Water (NRW) — tracing, tackling, and converting water loss into recovered revenue.**

Built by Team Larpers.

---

## The Problem

Non-Revenue Water is the gap between how much water a utility supplies and how much it actually gets paid for. In India, this gap is close to 38% of all water treated and supplied. It splits into two very different problems:

- **Real losses** — water that physically leaks from pipes (a plumbing problem)
- **Apparent losses** — water that's delivered but never billed: meter tampering, illegal connections, billing errors (a revenue-collection problem)

Most existing tools only look for physical leaks. AltoMare treats both halves as one problem, using data most Indian towns already have — no expensive sensors required to get started.

## What AltoMare Does

- **Trace** — component-based water audits, Minimum Night Flow estimation, and ML-based billing anomaly detection, all working from basic billing/inflow data
- **Tackle** — zone-level leak flagging with an AI investigation agent that explains *why* a zone is losing water, citing real evidence
- **Convert to revenue** — automatic theft/tampering audit lists, a live Revenue Recovered tracker, and ROI-based repair prioritization so utilities know which leak to fix first

An AI Copilot lets a user click any zone and watch the system investigate it live — running detection, checking evidence, and producing a structured, human-approvable recommendation.

## Data

The demo dataset is anchored to Lucknow's real, published city-wide figures: **~55% NRW** across **~650 MLD** of daily supply, giving **~₹650 million/year** in losses at the ₹5/kL (₹0.005/litre) tariff used throughout.

Sources, as returned by `GET /data/town-profile` for judges who ask:

- Ministry of Jal Shakti, *Annual Report 2023-24*, NRW-by-city table
- AMRUT 2.0 MIS Portal, Lucknow entry (accessed Sep 2026)
- Lucknow Municipal Corporation internal water audit, presented at AMRUT review, Mar 2024

Zone-level data is generated to be mathematically consistent with that real aggregate, since granular household/zone-level billing data isn't publicly available for any Indian town today. `backend/data/lucknow_seed.py` re-verifies the arithmetic on every run — zone inflows sum to ~650 MLD, weighted NRW lands within ±3pp of 55%, and annualised loss lands within 10% of ₹650M. The rupee figure is *derived* (lost litres × tariff), not a separately published number.

## Tech Stack

- **Backend:** Python (FastAPI), PostgreSQL + PostGIS
- **ML:** scikit-learn (Isolation Forest for billing anomaly detection, confidence scoring model)
- **AI Agent:** Groq LLM with tool-calling
- **Frontend:** React, TypeScript, Tailwind, Leaflet
- **Alerts:** WhatsApp Business API / Twilio SMS

## Project Structure

```
backend/
  app/
    engines/      # detection, ML, and revenue logic
    routers/       # API endpoints
    alerts/        # notification delivery
  data/            # schema + seed data
  test/            # ML, forecast, agent and router tests
frontend/            # Vite + React + TypeScript SPA (all screens, live API data)
  src/
    pages/           # one file per screen (Dashboard, Alerts, Copilot, ...)
    components/      # layout shell, charts, UI primitives
    lib/             # typed API client, formatters, derivations
  smoke/             # jsdom render smoke (mounts every route live)
docs/
  DEPLOY.md         # Render + Vercel deployment guide
```

### Backend

```bash
# From the repository root

# Install backend dependencies
python -m pip install -r backend/requirements.txt

# Create your local environment file
cp .env.example .env

# Edit .env and add your own credentials:
# DATABASE_URL=...
# GROQ_API_KEY=...

# Real WhatsApp/SMS alerts (Twilio) — without these the alert notifier
# runs the documented mock fallback instead of sending:
# TWILIO_ACCOUNT_SID=AC...
# TWILIO_AUTH_TOKEN=...
# TWILIO_WHATSAPP_FROM=whatsapp:+14155238886     # sandbox or your sender
# FIELD_STAFF_WHATSAPP_TO=whatsapp:+91XXXXXXXXXX  # must have joined the sandbox
# TWILIO_CONTENT_SID=HC...                       # WhatsApp content template, body with
#   {{1}}..{{5}} = zone, severity, loss, method, confidence
#
# TRIAL-ACCOUNT RULE (verified against the API 2026-09): on a Twilio trial
# account EVERY WhatsApp API send requires a Twilio-provided ContentSid — even
# inside the 24-hour sandbox service window (free-form returns
# "ContentSid Required"). The Content API is blocked on trial (error 20003
# "not available on a Trial account"), so custom templates need an account
# upgrade first. The provided templates' ContentSids appear in the cURL code
# block on Console → Messaging → Try out WhatsApp. After an upgrade, either
# drop ContentSid for free-form-in-window sends, or create a custom template
# in Messaging → Content Builder with the body above.
# Sandbox (works on trial): from the receiving phone send "join <code>" to
# +14155238886 (code shown on Console/Try-out page; membership lasts 72h;
# sending the join opens a 24h customer-service window).

# Start the backend
python -m uvicorn backend.app.main:app --reload
```

### Frontend

The frontend calls the backend directly (the API allows all origins), so no
proxy configuration is required. Override the API URL at build time with
`VITE_API_BASE` if the backend is not on `http://127.0.0.1:8000`.

```bash
# From the repository root
cd frontend
npm install

# Start the dev server (http://localhost:5173)
npm run dev

# Checks used before pushing
npm run typecheck     # tsc --noEmit
npm run build         # production build
```

## 🚀 Deployment

Free-tier hosting: **Vercel** serves the static frontend, **Render** runs the
FastAPI backend (Blueprint via [`render.yaml`](render.yaml)), both connected to
the shared Supabase Postgres — so the deployed site shows the same curated demo
data as `localhost`. One-time setup takes ~15 minutes:
**[docs/DEPLOY.md](docs/DEPLOY.md)**.

- Pushing to `main` redeploys both services automatically.
- Render free tier sleeps after ~15 min idle: the first API call then takes
  ~40–60 s (open `/health` once to wake it before a demo).
- The deployed app mutates the **same demo database** as localhost — the
  pristine-state rules in your local `DEMO_VIDEO.md` runbook (kept out of the
  repo) apply to live clicks too.

## Honest Limitations

Carried over from the original solution document (§11), stated directly rather than left to be discovered under questioning:

- **Level 0 gives zone-level detection, not street-level location.** Precise leak location needs at least minimal Level 1 instrumentation.
- **Billing-data quality directly bounds accuracy.** The water balance is only as good as the records feeding it, and NRW data in India is often incomplete or inconsistent.
- **Bacteria testing remains a weekly lab process even at Level 1**, so the fastest-moving part of contamination detection carries an inherent reporting lag; pH and turbidity can be near-real-time only where sensors exist.
- **The correlation between a leak and a contamination reading in the same zone/time window is a strong statistical signal, not proof of causation** — a priority flag for field verification, not an automatic conclusion.

Specific to this build:

- **PPA leak-location pressure readings are simulated**, labelled `is_simulated: true` by the API — Level 1 hardware is genuinely out of scope for a 24-hour build, and we would rather say so than pass simulated sensors off as real.
- **Zone, household and weekly trend data are synthetic**, anchored to the real city aggregate above; only the city-wide figures are published data.
- **The ML models train on the demo dataset** (399 billing records, 13 weekly snapshots) at startup, and the anomaly thresholds were tuned against that same data (`backend/test/tune_thresholds.py`). Accuracy on a real utility's data will differ, and the model reports precision/recall rather than claiming perfection.
- **The 30-day forecast is a linear trend** over 13 weeks of history and tests its own slope for significance; given noisy or short history it reports `STABLE` instead of inventing a direction.
- **The Sentinel-2 NDWI check queries the real, free satellite catalog live** (`GET /data/satellite/ndwi/{zone_id}` returns a genuine Sentinel-2 acquisition — scene ID, date, cloud cover), but band reflectance (B03/B08) is not configured in this deployment, so `ndwi_score` comes back `null` with an explicit reason rather than a made-up index value. Where an NDWI score does appear it is computed from reflectance supplied via `?green=&nir=`, never simulated. At 10 m resolution it can only corroborate large, sustained leaks — never a small one (roadmap §5.4).
- **Investigation-history notes ("previously flagged") are derived from the seeded findings themselves** — Isolation Forest flag counts and computed 4-week NRW rises — not hand-written incident stories.
- **Graceful degradation, not magic:** without `GROQ_API_KEY` the Copilot falls back to a rule-based summary, and without Twilio credentials alerts are logged rather than sent.

---

Team Larpers
