"""Intent Recognition Agent — rules-first, LLM fallback."""
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.intent_recognition.rules import (
    MatchResult,
    confidence_from_match,
    match_keywords,
)
from backend.models.schemas import ExecutionMeta
from backend.services.llm_service import LLMService

_LLM_SYSTEM_PROMPT = (
    "You are a classifier that determines whether a user query is about "
    "e-commerce product selection, operations, or market analysis. "
    "Respond in JSON with keys: is_ecommerce_query (bool), explanation (str)."
)

_FALLBACK_TEMPLATE = (
    'The query does not contain clear e-commerce keywords. '
    'Based on the wording, it appears to be a {label} request.'
)


class IntentRecognitionAgent(BaseAgent):
    """Classify user messages as e-commerce queries or not.

    Fast path: three-level keyword matching (0 LLM calls).
    Slow path: LLM fallback when rules are uncertain (1 LLM call).
    """

    agent_name = "intent_recognition"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        message: str = (input_data.get("message") or "").strip()
        if not message:
            return {
                "is_ecommerce_query": False,
                "confidence": 0.0,
                "matched_keywords": [],
                "explanation": "Empty message.",
            }

        # ── Fast path: keyword matching ──────────────────
        match: MatchResult = match_keywords(message)
        confidence: float = confidence_from_match(match)

        if match.is_ecommerce:
            return {
                "is_ecommerce_query": True,
                "confidence": confidence,
                "matched_keywords": match.all_keywords,
                "explanation": f"Matched {match.total_levels_hit} keyword levels.",
            }

        # ── Slow path: LLM fallback ──────────────────────
        llm_result = await self._llm.chat(
            system_prompt=_LLM_SYSTEM_PROMPT,
            user_message=message,
            fallback={
                "is_ecommerce_query": False,
                "explanation": _FALLBACK_TEMPLATE.format(label="general"),
            },
        )

        is_ecommerce = bool(llm_result.get("is_ecommerce_query", False))
        explanation = llm_result.get("explanation", "")

        # Boost confidence when LLM agrees with partial rule signal
        fallback_confidence = 0.50 if is_ecommerce else 0.30

        return {
            "is_ecommerce_query": is_ecommerce,
            "confidence": fallback_confidence,
            "matched_keywords": match.all_keywords,
            "explanation": explanation,
        }

    async def run(self, agent_input):  # noqa: ANN201
        """Override run to mark *llm_used* correctly."""
        from backend.models.schemas import AgentResult

        start = __import__("time").perf_counter()
        try:
            output = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
            error = None
            # Rules are certain → no LLM used
            if output.get("matched_keywords") and output["confidence"] >= 0.80:
                llm_used = False
                llm_calls = 0
            else:
                llm_used = True
                llm_calls = 1
        except Exception as exc:
            output = {}
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            llm_used = False
            llm_calls = 0

        elapsed_ms = (__import__("time").perf_counter() - start) * 1000
        return AgentResult(
            task_id=agent_input.task_id,
            status=status,
            output_data=output,
            execution_meta=ExecutionMeta(
                execution_time_ms=round(elapsed_ms, 2),
                llm_used=llm_used,
                llm_calls=llm_calls,
            ),
            error=error,
        )
