"""DAG executor — runs plan steps in topological order via AgentRegistry."""
from __future__ import annotations

import asyncio
from typing import Any

from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, PlanStep


class Executor:
    """Executes a list of :class:`PlanStep` respecting dependency order.

    Usage::

        executor = Executor(request_id="req_001")
        context = await executor.run(plan_steps, shared_context)
        # context["product_analysis"] -> AgentResult (dict)
    """

    def __init__(self, request_id: str = "") -> None:
        self._request_id = request_id

    async def run(
        self,
        plan: list[PlanStep],
        shared_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute plan steps in topological order.

        Args:
            plan: Ordered list of PlanStep (already topologically sorted).
            shared_context: Initial context injected into every agent.

        Returns:
            context dict keyed by agent name → AgentResult raw data.
        """
        context: dict[str, Any] = dict(shared_context or {})
        task_counter = 0

        for step in plan:
            agent_cls = AgentRegistry.get(step.agent)
            agent = agent_cls()
            task_counter += 1
            task_id = f"{step.agent}_{task_counter}"

            # Build input_data from step.params merged with current context
            inp = AgentInput(
                task_id=task_id,
                request_id=self._request_id,
                input_data=dict(step.params),
                context=dict(context),
                dependencies=list(step.depends_on),
            )

            try:
                result = await agent.run(inp)
                if result.status == "failed":
                    context[f"{step.agent}.error"] = result.error
                    context[step.agent] = result.model_dump()
                else:
                    context[step.agent] = result.model_dump()
            except Exception as exc:
                context[f"{step.agent}.error"] = f"{type(exc).__name__}: {exc}"
                context[step.agent] = {
                    "task_id": task_id,
                    "status": "failed",
                    "output_data": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }

        return context
