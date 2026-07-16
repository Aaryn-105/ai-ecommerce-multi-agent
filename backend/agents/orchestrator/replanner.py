"""Replanning logic — invoked when one or more steps fail."""
from __future__ import annotations

from typing import Any

from backend.models.schemas import PlanStep
from backend.services.llm_service import LLMService


class Replanner:
    """Attempts to recover from step failures.

    Strategy (in order):
    1. LLM analyses the error and suggests replacement steps.
    2. Rule-based fallback: drop failed step and all its dependents.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    async def replan(
        self,
        query: str,
        original_plan: list[PlanStep],
        context: dict[str, Any],
    ) -> list[PlanStep]:
        """Return a revised list of PlanSteps, or an empty list if no recovery is possible."""
        # Collect failed steps
        failed_agents = [
            agent for agent in original_plan
            if isinstance(context.get(agent.agent), dict)
            and context[agent.agent].get("status") == "failed"
        ]
        if not failed_agents:
            return []

        # ── Try LLM replan ──────────────────────────────
        prompt = (
            f"The following agents failed: {[f.agent for f in failed_agents]}. "
            f"Original plan: {[s.agent for s in original_plan]}. "
            "Suggest replacement steps or removal. "
            "Respond as a JSON array of step objects (agent, params, depends_on, description)."
        )
        llm_result = await self._llm.chat(
            system_prompt="You are a replanning agent for an e-commerce system.",
            user_message=prompt,
            fallback=None,
        )
        if isinstance(llm_result, list) and len(llm_result) > 0:
            try:
                return [PlanStep.model_validate(s) for s in llm_result]
            except Exception:
                pass

        # ── Rule fallback: drop failed and dependents ────
        return self._drop_failed_and_dependents(original_plan, failed_agents)

    @staticmethod
    def _drop_failed_and_dependents(
        plan: list[PlanStep],
        failed_agents: list[PlanStep],
    ) -> list[PlanStep]:
        """Remove failed steps and any step that transitively depends on them."""
        failed_names = {f.agent for f in failed_agents}
        removed = set(failed_names)
        # Find all transitive dependents
        changed = True
        while changed:
            changed = False
            for step in plan:
                if step.agent in removed:
                    continue
                if any(dep in removed for dep in step.depends_on):
                    removed.add(step.agent)
                    changed = True

        return [s for s in plan if s.agent not in removed]
