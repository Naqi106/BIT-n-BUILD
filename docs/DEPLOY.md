# Deploying AltoMare (Render + Vercel)

Free-tier deployment: **Vercel** hosts the static frontend, **Render** hosts the
FastAPI backend, and both talk to the **same shared Supabase Postgres** the local
dev server already uses — judges see exactly the curated demo data.

```
Browser ──▶ Vercel (static SPA, dist/)  ──GET──▶  Render (FastAPI, render.yaml) ──▶ Supabase Postgres
                VITE_API_BASE (build time)            DATABASE_URL, GROQ_API_KEY (env vars)
```

Everything needed is already committed:

| File | Purpose |
|---|---|
| `render.yaml` | Render Blueprint: build command, `$PORT` binding, `/health` check, auto-deploy |
| `frontend/vercel.json` | SPA fallback — deep links like `/app/alerts` serve `index.html` |
| `backend/requirements.txt` | Full runtime deps incl. `psycopg2-binary` (SQLAlchemy's `postgresql://` driver) |
| `backend/app/main.py` | CORS already `allow_origins=["*"]` — cross-origin works as-is |

Secrets (`.env`, gitignored) are **never uploaded** — you paste them into the
Render/Vercel dashboards once.

---

## 1. Render — the API (~10 min)

1. <https://render.com> → **Sign up** → *Continue with GitHub* (the `Naqi106` account).
2. **New +** → **Blueprint** → connect/select the GitHub repo **`Naqi106/BIT-n-BUILD`**.
3. Render detects `render.yaml` at the repo root and proposes service
   **`altomare-api`**. It prompts for the two `sync: false` secrets:

   | Env var | Where to get the value |
   |---|---|
   | `DATABASE_URL` | The `DATABASE_URL=` line of `backend/.env` on the dev machine (Supabase **pooler**, port **6543**). Or: Supabase Dashboard → Project Settings → Database → *Connection string* → **Session pooler**. |
   | `GROQ_API_KEY` | The `GROQ_API_KEY=` line of `backend/.env`. (Omitting it degrades the Copilot to a rule-based summary — not demo-day material.) |

   Optional later: the five `TWILIO_*` / `FIELD_STAFF_*` variables — without them
   alerts use the documented mock fallback (WhatsApp delivery is parked anyway).

4. **Apply / Create Blueprint** → first build ≈ 5–8 min (pip installs pandas,
   scikit-learn, torch-free stack).

### Verify — both checks, do not skip the second

1. `GET https://<your-service>.onrender.com/health`
   → `{"status": "ok", "version": "2.0.0"}`
2. `GET https://<your-service>.onrender.com/data/town-profile`
   → must contain `"total_nrw_percent": 55` **and**
   `"estimated_annual_loss_inr": 650737500`

Check 2 proves the service reached **Supabase**. If you see an empty/zero
profile, `DATABASE_URL` was not set and the app silently fell back to an empty
local SQLite (`db.py` default) — fix the env var and restart.

## 2. Vercel — the frontend (~5 min)

1. <https://vercel.com> → **Sign up** → *Continue with GitHub*.
2. **Add New… → Project** → import the **same repo** → *Import*.
3. **Root Directory**: `frontend`  ← *Important Settings → Root Directory*.
   (Framework preset **Vite** auto-fills build `npm run build`, output `dist`.)
4. **Environment Variables** (build time, required):

   ```
   VITE_API_BASE = https://<your-service>.onrender.com
   ```

   Exact Render URL, **no trailing slash**. Without it the deployed site would
   call `http://127.0.0.1:8000` — i.e. each visitor's own laptop.
5. **Deploy** → you get `https://<project>.vercel.app`.

## 3. Post-deploy smoke (2 min)

1. Open the Vercel URL → the dashboard renders, **API status is green**.
2. DevTools console → no CORS / failed-fetch errors.
3. `Alerts` page shows exactly **ALT-1 · zone_2 · CRITICAL · ACTIVE** (badge = 1).
4. Optional: hit Render `/health` once to warm it (see cold starts below).

> **Shared-DB rule:** the deployed app mutates the *same* Supabase database as
> localhost. The pristine-state discipline in your local `DEMO_VIDEO.md` runbook
> (kept out of the repo) applies to live clicks on the deployed site too — after
> any detect/dispatch rehearsal, run its FK-safe cleanup one-liner before judges touch it.

---

## Operations

- **Re-deploy:** push to `main` — Render redeploys on push (`autoDeploy: true`)
  and Vercel redeploys its Git integration. `VITE_API_BASE` persists in Vercel
  project settings across builds (re-set it only if you rename the Render URL).
- **Free-tier sleep:** Render free services stop after ~15 min idle; the first
  API call then takes ~40–60 s (or open `/health` once to wake it before a demo).
- **Zero cost:** Render Free (750 h/mo) + Vercel Hobby = $0.
- **Secrets:** only in dashboards. `.env` stays gitignored; nothing sensitive in git.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Frontend loads, every API call 404s | `VITE_API_BASE` unset/typo'd at build time | Set it in Vercel → **Redeploy** (it is baked into the JS bundle) |
| `/health` ok but empty town profile | `DATABASE_URL` missing → SQLite fallback | Set it in Render env → Restart; re-run the town-profile check |
| Copilot returns rule-based summary | No `GROQ_API_KEY` | Add the key in Render → Restart |
| Render deploy fails at build | Rare: pinned `PYTHON_VERSION` unsupported | Remove the pin (defaults) or set a version Render lists |
| CORS error in console | Should not happen — API allows `*` | Check the URL is `https://…onrender.com` (no typo in origin) |
| WhatsApp click sends nothing | By design — mock fallback (trial account parked) | README → Twilio section if ever re-enabled |
