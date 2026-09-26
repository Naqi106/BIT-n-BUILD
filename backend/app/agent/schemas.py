from typing import Any

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