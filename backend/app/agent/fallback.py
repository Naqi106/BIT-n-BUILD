from .schemas import AgentInvestigation


def build_fallback_investigation(
    zone_id: str,
    summary: str,
) -> AgentInvestigation:
    return AgentInvestigation(
        zone_id=zone_id,
        risk_level="UNKNOWN",
        likely_cause="insufficient_evidence",
        confidence=0.0,
        summary=summary,
        evidence=[],
        recommendations=[],
        missing_data=["AI analysis unavailable"],
        ai_available=False,
    )