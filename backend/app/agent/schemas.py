from typing import Any, Optional

from pydantic import BaseModel, Field


class InvestigationRequest(BaseModel):
    zone_id: str
    question: str = "Why is this zone at risk?"


class EvidenceItem(BaseModel):
    source: str
    metric: str
    value: Any
    unit: str | None = None
    explanation: str | None = None


class Recommendation(BaseModel):
    action: str
    priority: str
    reason: str


class AgentInvestigation(BaseModel):
    zone_id: str
    risk_level: str
    likely_cause: str
    confidence: float = Field(ge=0.0, le=1.0)

    summary: str

    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)

    ai_available: bool = True


# ==============================================================================
# Block 2 Convention: get_correlation_status()
# Water quality and contamination telemetry are currently unconfigured in the DB.
# The future agent tool MUST NOT fabricate correlations or fake quality metrics.
# When called, it must follow this safe convention:
# {
#     "correlation_detected": False,
#     "risk_level": "NONE",
#     "water_quality_events": 0,
#     "details": "No water-quality data source is currently configured.",
#     "is_simulated": False,
#     "status": "NOT_AVAILABLE"
# }
# ==============================================================================


# ==============================================================================
# Block 4 Schemas — Investigation Memory & Action Creation
# ==============================================================================

class MemoryResponse(BaseModel):
    """Single investigation memory record returned by GET /agent/memory/{zone_id}."""
    id: int
    zone_id: str
    summary: str
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    timestamp: Optional[str] = None


class CreateActionFromRecommendationRequest(BaseModel):
    """
    Request body for POST /agent/create-action.

    One recommendation from an AgentInvestigation is combined with the
    deterministic financial inputs required by the revenue engine so that
    no cost or payback values are invented by the LLM.
    """
    zone_id: str
    alert_id: Optional[int] = Field(
        None, description="Optional: link to an existing LeakAlert ID."
    )
    # --- mapped from AgentInvestigation.recommendations ---
    action: str = Field(..., description="Recommendation action text -> action_type in ActionLog")
    priority: str = Field(..., description="Recommendation priority -> urgency in ActionLog")
    reason: str = Field(..., description="Recommendation reason -> officer_notes in ActionLog")
    # --- deterministic financial inputs (must NOT be invented by the LLM) ---
    daily_loss_litres: float = Field(
        ..., ge=0.0,
        description="Daily water loss in litres used to calculate cost and payback."
    )
    tariff_rate: Optional[float] = Field(
        None, ge=0.0,
        description="Rs per litre. Defaults to the zone's tariff_rate from the DB if omitted."
    )
    pipe_age_years: Optional[int] = Field(
        None, ge=0, description="Pipe age in years fed to the repair-cost formula."
    )


class AgentActionResponse(BaseModel):
    """Response returned after creating an ActionLog entry from a recommendation."""
    action_id: int
    zone_id: str
    action_type: str
    urgency: str
    estimated_cost: float
    estimated_payback_days: float
    officer_notes: Optional[str]
    status: str
    message: str = "Action created and pending officer approval."