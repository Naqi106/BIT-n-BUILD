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