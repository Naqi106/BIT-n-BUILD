from .fallback import build_fallback_investigation
from .schemas import AgentInvestigation, InvestigationRequest


async def investigate(
    request: InvestigationRequest,
) -> AgentInvestigation:
    """
    Block 1 skeleton.

    Tool calling, evidence collection, and LLM reasoning
    will be added in later blocks.
    """

    return build_fallback_investigation(
        zone_id=request.zone_id,
        summary="AI investigation pipeline is not connected yet.",
    )