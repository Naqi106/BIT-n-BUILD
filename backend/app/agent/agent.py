"""
AltoMare AI Agent Core Module (Block 3)
Wires Groq tool calling to existing analytical engines and deterministic tools.

Flow:
1. Receive InvestigationRequest (zone_id, question) and optional database session.
2. Verify GROQ_API_KEY; fallback cleanly if absent.
3. Initiate multi-step tool-calling loop (capped at MAX_TOOL_ROUNDS).
4. Execute requested analytical tools in-process using direct Python calls.
5. Provide tool results back to Groq for multi-step reasoning.
6. Parse and validate structured output against AgentInvestigation schema.
7. Return safe fallback on any API, parsing, or loop failure.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from groq import AsyncGroq
from sqlalchemy.orm import Session

from .schemas import AgentInvestigation, InvestigationRequest, EvidenceItem, Recommendation
from .fallback import build_fallback_investigation
from .prompts import SYSTEM_PROMPT
from .memory import get_zone_memory, build_memory_context_block
from .tools import (
    run_water_balance,
    run_mnf,
    run_uarl,
    run_billing_anomaly,
    run_ppa,
    get_correlation_status,
)

load_dotenv()

logger = logging.getLogger("altomare.agent")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
MAX_TOOL_ROUNDS = 5

# Tool definitions exposed to Groq
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_water_balance",
            "description": "Calculates gross water balance loss, NRW percentage, and severity for a zone using inflow and billing telemetry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_mnf",
            "description": "Estimates 24-hour physical leakage using Minimum Night Flow (2:00 AM - 4:00 AM) telemetry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_uarl",
            "description": "Calculates Unavoidable Annual Real Losses (UARL) baseline and Infrastructure Leakage Index (ILI).",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    },
                    "current_real_loss_litres": {
                        "type": "number",
                        "description": "Optional current real physical loss in litres per day to calculate ILI."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_billing_anomaly",
            "description": "Audits consumer billing records for suspicious consumption deviations and theft/tampering indicators.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_ppa",
            "description": "Executes Pressure Profile Analysis (PPA) simulation across pipe nodes to identify candidate leak locations. Output is simulated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_correlation_status",
            "description": "Checks for correlation between water loss/pressure drops and water-quality contamination complaints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone_id": {
                        "type": "string",
                        "description": "The unique identifier of the municipal zone."
                    }
                },
                "required": ["zone_id"],
            },
        },
    },
]

TOOL_DISPATCH = {
    "run_water_balance": run_water_balance,
    "run_mnf": run_mnf,
    "run_uarl": run_uarl,
    "run_billing_anomaly": run_billing_anomaly,
    "run_ppa": run_ppa,
    "get_correlation_status": get_correlation_status,
}


def execute_tool(tool_name: str, arguments: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Executes an agent tool by calling the registered Python function directly.
    NEVER makes localhost HTTP requests.
    """
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        logger.warning("Attempted to call unknown tool: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name}", "status": "ERROR"}

    logger.info("Tool called: %s", tool_name)
    try:
        result = func(**arguments, db=db)
        logger.info("Tool completed: %s with status: %s", tool_name, result.get("status"))
        return result
    except Exception as e:
        logger.error("Tool execution failed for %s: %s", tool_name, str(e))
        return {"error": str(e), "status": "ERROR"}


def parse_agent_response(raw_text: str, default_zone_id: str, executed_tools: Optional[set] = None) -> AgentInvestigation:
    """
    Parses and validates the raw text output from the LLM into an AgentInvestigation model.
    Handles potential markdown code fences or leading text.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    data = json.loads(cleaned)

    if executed_tools is not None and "evidence" in data:
        for ev in data.get("evidence", []):
            source = ev.get("source", "")
            source_base = source.split()[0] if source else ""
            if source_base and source_base not in executed_tools:
                raise ValueError(f"Hallucinated evidence source detected: {source_base} was not executed.")

    if "zone_id" not in data or not data["zone_id"]:
        data["zone_id"] = default_zone_id
    data["ai_available"] = True

    return AgentInvestigation.model_validate(data)


async def investigate(
    request: InvestigationRequest,
    db: Optional[Session] = None,
    client: Optional[AsyncGroq] = None,
) -> AgentInvestigation:
    """
    Main entrypoint for AI investigation of a zone.
    Executes a multi-round tool-calling loop with Groq, evaluates tool evidence,
    and returns a structured AgentInvestigation or safe fallback.
    """
    zone_id = request.zone_id
    question = request.question
    logger.info("Investigation started for zone %s: %s", zone_id, question)

    api_key = os.getenv("GROQ_API_KEY")
    if client is None:
        if not api_key:
            logger.warning("GROQ_API_KEY is not configured. Falling back to deterministic analysis.")
            return build_fallback_investigation(
                zone_id=zone_id,
                summary="AI analysis unavailable: GROQ_API_KEY is not configured.",
            )
        try:
            client = AsyncGroq(api_key=api_key)
        except Exception as e:
            logger.error("Failed to initialize Groq client: %s", str(e))
            return build_fallback_investigation(
                zone_id=zone_id,
                summary=f"AI client initialization failed: {str(e)[:150]}",
            )

    # ------------------------------------------------------------------
    # Optional: load historical memory context for this zone
    # Memory retrieval failure must never crash the agent.
    # ------------------------------------------------------------------
    memory_context_block = ""
    if db is not None:
        try:
            past_memories = get_zone_memory(db, zone_id=zone_id, limit=3)
            memory_context_block = build_memory_context_block(past_memories)
            if memory_context_block:
                logger.info("Injected %d memory entries for zone %s", len(past_memories), zone_id)
        except Exception as mem_err:
            logger.warning(
                "Failed to retrieve investigation memory for zone %s: %s. Continuing without memory.",
                zone_id, str(mem_err)
            )

    system_instruction = f"""{SYSTEM_PROMPT}

You are investigating zone '{zone_id}'.
User inquiry: "{question}"

{memory_context_block}

Use your analytical tools to inspect the zone before formulating recommendations.
Rules for final output:
1. After all tool results are returned, your final response MUST be a single valid JSON object.
2. Match this exact JSON structure:
{{
  "zone_id": "{zone_id}",
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN",
  "likely_cause": "<e.g. physical_leakage | apparent_loss_theft | meter_inaccuracy | inconclusive>",
  "confidence": <float 0.0 to 1.0>,
  "summary": "<comprehensive 2-3 sentence findings summary>",
  "evidence": [
    {{
      "source": "<tool name, e.g. run_water_balance, run_ppa (SIMULATED), etc.>",
      "metric": "<metric name>",
      "value": <numeric or string value>,
      "unit": "<e.g. litres, %, bar, or null>",
      "explanation": "<brief explanation>"
    }}
  ],
  "recommendations": [
    {{
      "action": "<action description>",
      "priority": "LOW" | "MEDIUM" | "HIGH" | "URGENT",
      "reason": "<rationale based on evidence>"
    }}
  ],
  "missing_data": ["<telemetry or data points that were missing or NO_DATA>"],
  "ai_available": true
}}

CRITICAL ACCURACY CONSTRAINTS:
- Do not invent numbers.
- If pressure profile data from run_ppa is cited, always clearly note that it is SIMULATED data and not physical IoT confirmation.
- If water quality status is NOT_AVAILABLE, state that water quality correlation is currently unconfigured; do not invent contamination claims.
- Return ONLY the JSON object.
"""

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Investigate zone '{zone_id}'. Question: {question}"},
    ]

    executed_tools = set()
    round_count = 0
    while round_count < MAX_TOOL_ROUNDS:
        round_count += 1
        tool_choice = "required" if round_count == 1 else "auto"
        try:
            response = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice=tool_choice,
                temperature=0.1,
                max_completion_tokens=2048,
                reasoning_effort="low",
            )
        except Exception as e:
            logger.error("LLM call failed on round %d: %s", round_count, str(e))
            return build_fallback_investigation(
                zone_id=zone_id,
                summary=f"AI service temporarily unavailable: {str(e)[:150]}",
            )

        choice = response.choices[0]
        message = choice.message

        # Check if the model requested tool executions
        if message.tool_calls:
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in message.tool_calls:
                func_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception:
                    args = {}

                if "zone_id" not in args:
                    args["zone_id"] = zone_id

                tool_result = execute_tool(func_name, args, db=db)
                if tool_result.get("status") != "ERROR":
                    executed_tools.add(func_name)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": func_name,
                    "content": json.dumps(tool_result),
                })
        else:
            # Model finished tool calling and produced the final response
            raw_output = message.content or ""
            try:
                investigation = parse_agent_response(raw_output, default_zone_id=zone_id, executed_tools=executed_tools)
                logger.info("Investigation successfully generated for zone %s with confidence %.2f", zone_id, investigation.confidence)
                return investigation
            except Exception as e:
                logger.warning("LLM produced invalid JSON schema: %s. Triggering fallback.", str(e))
                return build_fallback_investigation(
                    zone_id=zone_id,
                    summary=f"AI analysis completed but produced unvalidated structure: {str(e)[:150]}",
                )

    logger.warning("Investigation reached maximum tool rounds (%d) without terminating.", MAX_TOOL_ROUNDS)
    return build_fallback_investigation(
        zone_id=zone_id,
        summary=f"AI investigation stopped: maximum tool iterations ({MAX_TOOL_ROUNDS}) reached without completion.",
    )


async def run_manual_investigation(
    zone_id: str = "ZONE-TEST",
    question: str = "Why is this zone at risk?"
) -> AgentInvestigation:
    """
    Helper function for manual local execution with a live GROQ_API_KEY.
    Does NOT log or leak secrets.
    """
    req = InvestigationRequest(zone_id=zone_id, question=question)
    result = await investigate(req)
    print("\n=================== INVESTIGATION RESULT ===================")
    print(f"Zone ID:       {result.zone_id}")
    print(f"Risk Level:    {result.risk_level}")
    print(f"Likely Cause:  {result.likely_cause}")
    print(f"Confidence:    {result.confidence:.2f}")
    print(f"AI Available:  {result.ai_available}")
    print(f"Summary:       {result.summary}")
    print(f"Missing Data:  {result.missing_data}")
    print("Evidence:")
    for ev in result.evidence:
        unit_str = f" {ev.unit}" if ev.unit else ""
        print(f"  • [{ev.source}] {ev.metric}: {ev.value}{unit_str} ({ev.explanation or ''})")
    print("Recommendations:")
    for rec in result.recommendations:
        print(f"  • [{rec.priority}] {rec.action}: {rec.reason}")
    print("============================================================\n")
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_manual_investigation())