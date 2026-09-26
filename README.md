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

The demo dataset is anchored to Lucknow's real, published city-wide NRW figures (~55% NRW, ~₹650M/year in losses). Zone-level data is generated to be mathematically consistent with that real aggregate, since granular household/zone-level billing data isn't publicly available for any Indian town today.

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
frontend/
  src/
    pages/
    services/
    data/
```

## Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in your own credentials
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Honest Limitations

- Zone-level detection, not street-level leak location, without additional sensor instrumentation
- Detection accuracy depends on the quality of billing data fed into the system
- Leak-quality contamination correlation is a statistical signal for field verification, not proof of causation

---

Team Larpers
