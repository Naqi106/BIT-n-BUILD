"""
AltoMare Live AI Agent End-to-End Demo Runner (Block 3 Validation).

Demonstrates the live end-to-end investigation pipeline:
Synthetic Demo Data -> Local SQLite (agent_demo.db) -> tools.py -> Real Groq API -> AgentInvestigation.

MANUAL EXECUTION ONLY. Not part of automated tests.
NEVER prints or leaks secrets.
"""

import os
import sys
import asyncio
import logging

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

# 1. Point to the isolated synthetic demo database
DEMO_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent_demo.db"))
os.environ["DATABASE_URL"] = f"sqlite:///{DEMO_DB_PATH}"

# Load credentials from .env
load_dotenv(os.path.join(REPO_ROOT, ".env"))

# Configure concise logging to visualize tool calls
logging.basicConfig(level=logging.INFO, format="%(message)s")
# Suppress noisy HTTP connection logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from backend.data.seed_agent_demo import get_demo_engine, seed_demo_data
from backend.app.agent.agent import investigate
from backend.app.agent.schemas import InvestigationRequest


async def run_live_demo():
    print("\n" + "=" * 55)
    print("ALTOmare LIVE AGENT DEMO (BLOCK 3 END-TO-END VALIDATION)")
    print("=" * 55)
    print("DATASET: SYNTHETIC DEMO DATA")
    print("DATABASE: local backend/data/agent_demo.db")
    print("ZONE: ZONE-DEMO-01")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[ERROR] GROQ_API_KEY is missing or empty in .env.")
        print("Please configure GROQ_API_KEY in .env before running this demo.")
        sys.exit(1)

    # Ensure demo database is freshly seeded
    seed_demo_data()

    engine = get_demo_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    req = InvestigationRequest(
        zone_id="ZONE-DEMO-01",
        question="Why is this zone at risk and what should the utility investigate first?"
    )

    print("\n>>> Launching live investigation with real Groq LLM...")
    print(">>> Listening for real tool calls from Groq...\n")

    try:
        investigation = await investigate(request=req, db=db)
    finally:
        db.close()

    print("\n" + "=" * 55)
    print("ALTOmare LIVE AGENT DEMO REPORT")
    print("=" * 55)
    print(f"ZONE:          {investigation.zone_id}")
    print(f"AI AVAILABLE:  {investigation.ai_available}")
    print(f"Risk Level:    {investigation.risk_level}")
    print(f"Likely Cause:  {investigation.likely_cause}")
    print(f"Confidence:    {investigation.confidence:.2f}")

    print("\nSUMMARY:")
    print(investigation.summary)

    print("\nEVIDENCE:")
    if investigation.evidence:
        for ev in investigation.evidence:
            unit_str = f" {ev.unit}" if ev.unit else ""
            print(f"- [{ev.source}] {ev.metric}: {ev.value}{unit_str}")
            if ev.explanation:
                print(f"    Reasoning: {ev.explanation}")
    else:
        print("- (No evidence items recorded)")

    print("\nRECOMMENDATIONS:")
    if investigation.recommendations:
        for rec in investigation.recommendations:
            print(f"- [{rec.priority}] {rec.action}")
            print(f"    Rationale: {rec.reason}")
    else:
        print("- (No recommendations recorded)")

    print("\nMISSING DATA:")
    if investigation.missing_data:
        for item in investigation.missing_data:
            print(f"- {item}")
    else:
        print("- None")

    print("=" * 55 + "\n")
    return investigation


if __name__ == "__main__":
    asyncio.run(run_live_demo())
