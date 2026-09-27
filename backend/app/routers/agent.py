"""
AltoMare AI Agent Router (Block 4)

Exposes the AI investigation pipeline as HTTP endpoints.

Routes:
  POST /agent/investigate        — Run investigation, persist memory, return result.
  GET  /agent/memory/{zone_id}   — Return historical investigation memory for a zone.
  POST /agent/create-action      — Convert one recommendation into Person 2's ActionLog.
"""

import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.data.db_schema import Zone, ActionLog
from backend.app.models import ActionCreate
from backend.app.engines.revenue import calculate_payback_period
from backend.app.agent.agent import investigate
from backend.app.agent.memory import save_investigation_memory, get_zone_memory
from backend.app.agent.schemas import (
    InvestigationRequest,
    AgentInvestigation,
    MemoryResponse,
    CreateActionFromRecommendationRequest,
    AgentActionResponse,
)

router = APIRouter(prefix="/agent", tags=["AI Copilot Agent"])

logger = logging.getLogger("altomare.agent.router")


# ---------------------------------------------------------------------------
# POST /agent/investigate
# ---------------------------------------------------------------------------
@router.post("/investigate", response_model=AgentInvestigation)
async def run_investigation(
    payload: InvestigationRequest,
    db: Session = Depends(get_db),
):
    """
    Run an AI investigation for a zone.

    Flow:
      1. Validate zone exists.
      2. Run investigate() — injects historical memory context automatically.
      3. If investigation succeeded (ai_available=True), persist summary to
         InvestigationMemory.
      4. Return the validated AgentInvestigation response.

    Memory is ONLY written after a successful validated investigation.
    """
    zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=404,
            detail=f"Zone '{payload.zone_id}' not found.",
        )

    result: AgentInvestigation = await investigate(request=payload, db=db)

    # Persist memory only for successful AI investigations
    if result.ai_available:
        try:
            # Summarise recommendations as action_taken context
            action_taken_text = "; ".join(
                f"[{r.priority}] {r.action}" for r in result.recommendations
            ) or None

            mem_id = save_investigation_memory(
                db=db,
                zone_id=result.zone_id,
                summary=result.summary,
                action_taken=action_taken_text,
                outcome=None,  # Outcome is recorded by the officer at resolution time
            )
            logger.info(
                "Persisted investigation memory id=%d for zone %s (confidence=%.2f)",
                mem_id, result.zone_id, result.confidence,
            )
        except Exception as e:
            # Memory persistence failure must NOT prevent returning the investigation result
            logger.error(
                "Failed to persist investigation memory for zone %s: %s",
                result.zone_id, str(e),
            )

    return result


# ---------------------------------------------------------------------------
# GET /agent/memory/{zone_id}
# ---------------------------------------------------------------------------
@router.get("/memory/{zone_id}", response_model=List[MemoryResponse])
def get_investigation_memory(
    zone_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Return historical investigation memory entries for a zone, newest first.

    Returns an empty list when no history exists.
    Validates that the zone exists before querying.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=404,
            detail=f"Zone '{zone_id}' not found.",
        )

    memories = get_zone_memory(db, zone_id=zone_id, limit=limit)
    return [MemoryResponse(**m) for m in memories]


# ---------------------------------------------------------------------------
# POST /agent/create-action
# ---------------------------------------------------------------------------
@router.post("/create-action", response_model=AgentActionResponse)
def create_action_from_recommendation(
    payload: CreateActionFromRecommendationRequest,
    db: Session = Depends(get_db),
):
    """
    Convert one AgentInvestigation Recommendation into an ActionLog entry
    using Person 2's existing ActionLog schema and state machine.

    Financial values (estimated_cost, estimated_payback_days) are calculated
    deterministically by the existing revenue engine — they are NEVER invented
    by the LLM.

    Mapping:
      recommendation.action   -> action_type
      recommendation.priority -> urgency
      recommendation.reason   -> officer_notes
      daily_loss_litres       -> fed to calculate_payback_period()
      tariff_rate             -> from payload, or zone.tariff_rate if omitted
      pipe_age_years          -> from payload, or default in revenue engine
    """
    zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=404,
            detail=f"Zone '{payload.zone_id}' not found.",
        )

    # Resolve tariff_rate: use caller-supplied value, else fall back to zone DB value
    tariff = payload.tariff_rate if payload.tariff_rate is not None else zone.tariff_rate

    # Deterministic financial calculation — never invented
    payback_kwargs: dict = dict(
        daily_loss_litres=payload.daily_loss_litres,
        tariff_rate=tariff,
    )
    if payload.pipe_age_years is not None:
        payback_kwargs["pipe_age_years"] = payload.pipe_age_years

    payback_result = calculate_payback_period(**payback_kwargs)
    estimated_cost = payback_result["estimated_repair_cost"]
    estimated_payback_days = payback_result["payback_period_days"]

    # Create ActionLog record using Person 2's existing model — NO duplicate logic
    action = ActionLog(
        zone_id=payload.zone_id,
        alert_id=payload.alert_id,
        action_type=payload.action,
        urgency=payload.priority,
        estimated_cost=estimated_cost,
        estimated_payback_days=estimated_payback_days,
        officer_notes=payload.reason,
        status="PENDING",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    logger.info(
        "Created ActionLog id=%d (zone=%s, urgency=%s, cost=%.2f, payback=%.1f days)",
        action.id, action.zone_id, action.urgency,
        action.estimated_cost, action.estimated_payback_days,
    )

    return AgentActionResponse(
        action_id=action.id,
        zone_id=action.zone_id,
        action_type=action.action_type,
        urgency=action.urgency,
        estimated_cost=action.estimated_cost,
        estimated_payback_days=action.estimated_payback_days,
        officer_notes=action.officer_notes,
        status=action.status,
    )
