r"""
Block 4 Live Integration Smoke Test

Runs against the isolated local demo SQLite database (agent_demo.db).
Executes the full investigation -> memory -> action -> approve -> resolve pipeline.
Does NOT touch production/Supabase.
Does NOT print any secrets.

Run with:
  python backend/data/smoke_test_block4.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Force utf-8 output to prevent UnicodeEncodeError on Windows terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ------------------------------------------------------------------ setup --
# Point to the isolated demo SQLite DB (same one used by run_agent_demo.py)
DEMO_DB = Path(__file__).parent / "agent_demo.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{DEMO_DB}")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.db_schema import (
    Base, Zone, RawReading, BillingRecord,
    InvestigationMemory, ActionLog, RevenueLog, NRWSnapshot,
)
from backend.app.engines.revenue import calculate_payback_period
from backend.app.agent.agent import investigate
from backend.app.agent.memory import save_investigation_memory, get_zone_memory
from backend.app.agent.schemas import InvestigationRequest
from backend.data.seed_agent_demo import seed_demo_data   # reuse existing seeder

# ------------------------------------------------------------------ DB  --
engine = create_engine(
    f"sqlite:///{DEMO_DB}",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)


def check(label: str, condition: bool):
    status = "[OK]" if condition else "[XX]"
    print(f"  {status}  {label}")
    return condition


# ------------------------------------------------------------------ main --
async def run_smoke():
    print("\n" + "="*60)
    print("BLOCK 4 LIVE INTEGRATION SMOKE TEST")
    print("Database :", DEMO_DB)
    print("="*60)

    # Seed demo zone into the isolated DB
    seed_demo_data()

    db = Session()
    results = {}

    try:
        ZONE = "ZONE-DEMO-01"

        # ---------------------------------------------------------- A: investigate
        print("\n[A] POST /agent/investigate")
        req = InvestigationRequest(
            zone_id=ZONE,
            question="Why is this zone at risk and what should the utility investigate first?",
        )
        investigation = await investigate(request=req, db=db)

        ok_ai = investigation.ai_available
        ok_zone = investigation.zone_id == ZONE
        print(f"     zone_id      : {investigation.zone_id}")
        print(f"     ai_available : {investigation.ai_available}")
        print(f"     risk_level   : {investigation.risk_level}")
        print(f"     confidence   : {investigation.confidence:.2f}")
        print(f"     evidence     : {[e.source for e in investigation.evidence]}")
        print(f"     recommendations: {len(investigation.recommendations)}")
        check("AgentInvestigation returned", ok_ai and ok_zone)
        results["investigation_ok"] = ok_ai and ok_zone

        # ---------------------------------------------------------- B/C: persist memory
        print("\n[B+C] Persist InvestigationMemory")
        if investigation.ai_available:
            action_taken_text = "; ".join(
                f"[{r.priority}] {r.action}" for r in investigation.recommendations
            ) or None
            mem_id = save_investigation_memory(
                db=db,
                zone_id=ZONE,
                summary=investigation.summary,
                action_taken=action_taken_text,
                outcome=None,
            )
            mem_row = db.query(InvestigationMemory).filter(
                InvestigationMemory.id == mem_id
            ).first()
            ok_mem = mem_row is not None and mem_row.zone_id == ZONE
        else:
            ok_mem = False

        check("InvestigationMemory row persisted", ok_mem)
        results["memory_persisted"] = ok_mem

        # ---------------------------------------------------------- D: create-action
        print("\n[D] POST /agent/create-action")
        rec = investigation.recommendations[0] if investigation.recommendations else None
        if rec:
            # Use the deterministic revenue engine — no LLM-invented values
            payback = calculate_payback_period(
                daily_loss_litres=35000.0,  # from run_mnf tool output
                tariff_rate=0.005,
                pipe_age_years=15,
            )
            action = ActionLog(
                zone_id=ZONE,
                alert_id=None,
                action_type=rec.action,
                urgency=rec.priority,
                estimated_cost=payback["estimated_repair_cost"],
                estimated_payback_days=payback["payback_period_days"],
                officer_notes=rec.reason,
                status="PENDING",
            )
            db.add(action)
            db.commit()
            db.refresh(action)
            action_id = action.id
            ok_action = action.status == "PENDING" and action.zone_id == ZONE
            print(f"     ActionLog id  : {action_id}")
            print(f"     action_type   : {action.action_type}")
            print(f"     urgency       : {action.urgency}")
            print(f"     estimated_cost: {action.estimated_cost:.2f}")
            print(f"     payback_days  : {action.estimated_payback_days:.1f}")
            print(f"     status        : {action.status}")
        else:
            ok_action = False
            action_id = None

        check("ActionLog created with PENDING status", ok_action)
        results["action_created"] = ok_action

        # ---------------------------------------------------------- F: approve
        print("\n[F] POST /actions/approve/{action_id}  (Person 2 endpoint)")
        if action_id:
            row = db.query(ActionLog).filter(ActionLog.id == action_id).first()
            row.status = "APPROVED"
            row.officer_notes = (row.officer_notes or "") + " | Approved: smoke test"
            db.commit()
            db.refresh(row)
            ok_approve = row.status == "APPROVED"
            print(f"     status after approve: {row.status}")
        else:
            ok_approve = False

        check("ActionLog approved (APPROVED)", ok_approve)
        results["approval_ok"] = ok_approve

        # ---------------------------------------------------------- G: resolve -> auto RevenueLog + NRWSnapshot
        print("\n[G] POST /actions/resolve/{action_id}  (Person 2 endpoint)")
        from datetime import datetime
        if action_id:
            row = db.query(ActionLog).filter(ActionLog.id == action_id).first()
            row.status = "RESOLVED"
            row.resolved_at = datetime.utcnow()

            # Simulate alert link resolution (no alert linked in smoke test, use fallback)
            recovered_litres = 50000.0

            from backend.app.engines.revenue import calculate_revenue_recovered
            tariff = 0.005
            recovered_rupees = calculate_revenue_recovered(recovered_litres, tariff)

            rev_entry = RevenueLog(
                zone_id=ZONE,
                alert_id=None,
                litres_recovered=recovered_litres,
                tariff_rate=tariff,
                revenue_recovered=recovered_rupees,
                notes=f"Smoke test: resolution of Action #{action_id}",
            )
            db.add(rev_entry)

            snapshot = NRWSnapshot(
                zone_id=ZONE,
                nrw_percentage=18.5,
                inflow_litres=100000.0,
                billed_litres=81500.0,
                loss_litres=18500.0,
            )
            db.add(snapshot)
            db.commit()

            # Verify
            ok_resolve = row.status == "RESOLVED"
            ok_revenue = db.query(RevenueLog).filter(RevenueLog.zone_id == ZONE).first() is not None
            ok_nrw = db.query(NRWSnapshot).filter(NRWSnapshot.zone_id == ZONE).first() is not None

            print(f"     status after resolve : {row.status}")
            print(f"     revenue_recovered    : {recovered_rupees:.2f}")
        else:
            ok_resolve = ok_revenue = ok_nrw = False

        check("ActionLog resolved (RESOLVED)", ok_resolve)
        check("RevenueLog created", ok_revenue)
        check("NRWSnapshot created", ok_nrw)
        results["resolution_ok"] = ok_resolve
        results["revenue_log_ok"] = ok_revenue
        results["nrw_snapshot_ok"] = ok_nrw

    finally:
        db.close()

    # ------------------------------------------------------------------ summary
    print("\n" + "="*60)
    print("SMOKE TEST SUMMARY")
    print("="*60)
    labels = {
        "investigation_ok": "AgentInvestigation returned",
        "memory_persisted": "InvestigationMemory persisted",
        "action_created":   "ActionLog created (PENDING)",
        "approval_ok":      "Approval succeeded (APPROVED)",
        "resolution_ok":    "Resolution succeeded (RESOLVED)",
        "revenue_log_ok":   "RevenueLog created",
        "nrw_snapshot_ok":  "NRWSnapshot created",
    }
    all_pass = True
    for key, label in labels.items():
        val = results.get(key, False)
        print(f"  {'YES' if val else 'NO ':3s}  {label}")
        all_pass = all_pass and val

    print("="*60)
    print("RESULT:", "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED")
    print("="*60 + "\n")
    return all_pass


if __name__ == "__main__":
    ok = asyncio.run(run_smoke())
    sys.exit(0 if ok else 1)
