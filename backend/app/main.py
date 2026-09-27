from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pandas as pd

from backend.app.db import SessionLocal
from backend.data.db_schema import init_db, BillingRecord
from backend.app.routers import core, audit, actions, data_pipeline, agent as agent_router
from backend.app.engines.ml_billing_anomaly import train_detector

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables
    init_db()
    
    # Train Isolation Forest model on startup
    db = SessionLocal()
    try:
        records = db.query(BillingRecord).all()
        if records:
            df = pd.DataFrame([{
                "billed_litres": r.billed_litres,
                "benchmark_litres": r.benchmark_litres,
                "household_size": r.household_size or 4,
            } for r in records])
            train_detector(df)
            print("[INFO] Isolation Forest model trained with", len(df), "records.")
    except Exception as e:
        print("[WARNING] Could not train Isolation Forest model at startup:", e)
    finally:
        db.close()
        
    yield
    # Shutdown

app = FastAPI(
    title="AltoMare Non-Revenue Water Platform API",
    description="Backend API for water balance audits, MNF estimation, billing fraud, and payback ROI.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(core.router)
app.include_router(audit.router)
app.include_router(actions.router)
app.include_router(data_pipeline.router)  # Person 1 — CSV upload + town profile
app.include_router(agent_router.router)   # Person 3 — AI Copilot Agent

@app.get("/")
def root():
    return {
        "platform": "AltoMare NRW Platform",
        "status": "online",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    """Liveness probe for monitors and tooling (static — cannot flake)."""
    return {"status": "ok", "service": "altomare-api", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
