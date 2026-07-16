"""OrchestratorAgent — Plan-and-Execute with replan loop."""
from __future__ import annotations

import time
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.orchestrator.executor import Executor
from backend.agents.orchestrator.planner import Planner
from backend.agents.orchestrator.replanner import Replanner
from backend.models.schemas import ExecutionMeta


class OrchestratorAgent(BaseAgent):
    """Coordinates multi-agent e-commerce analysis.

    Flow::

        Plan → Execute → (if any step failed) → Replan → Execute → Assemble Report
    """

    agent_name = "orchestrator"

    def __init__(
        self,
        planner: Planner | None = None,
        executor: Executor | None = None,
        replanner: Replanner | None = None,
    ) -> None:
        self._planner = planner or Planner()
        self._executor = executor or Executor()
        self._replanner = replanner or Replanner()

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        query: str = (input_data.get("message") or input_data.get("query") or "").strip()
        if not query:
            return {"error": "Empty query.", "plan_steps": [], "final_report": None}

        request_id = input_data.get("request_id", "orchestrator_req")
        max_attempts = 2
        attempt = 0
        shared_context: dict[str, Any] = dict(context or {})

        # ── Plan ─────────────────────────────────────────
        plan_steps = await self._planner.plan(query)

        while attempt < max_attempts:
            attempt += 1

            # ── Execute ──────────────────────────────────
            shared_context = await self._executor.run(plan_steps, shared_context)

            # ── Check for failures ───────────────────────
            failed = [
                agent
                for agent in (s.agent for s in plan_steps)
                if isinstance(shared_context.get(agent), dict)
                and shared_context[agent].get("status") == "failed"
            ]
            if not failed:
                break

            # ── Replan ───────────────────────────────────
            if attempt < max_attempts:
                plan_steps = await self._replanner.replan(query, plan_steps, shared_context)
                if not plan_steps:
                    break

        # ── Assemble report ──────────────────────────────
        sections = {}
        for step in plan_steps if not failed else []:
            data = shared_context.get(step.agent, {})
            if isinstance(data, dict) and "output_data" in data:
                sections[step.agent] = data["output_data"]

        final_report = {
            "summary": f"Executed {len(sections)} agents across {attempt} attempt(s).",
            "sections": sections,
            "total_agents_run": len(sections),
            "attempts": attempt,
            "failed_agents": failed if attempt >= max_attempts else [],
        }

        return {
            "plan_steps": [s.model_dump() for s in plan_steps],
            "context": shared_context,
            "final_report": final_report,
        }

    async def run(self, agent_input):  # noqa: ANN201
        """Override run for accurate timing."""
        from backend.models.schemas import AgentResult

        start = time.perf_counter()
        try:
            output = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
            error = None
        except Exception as exc:
            output = {}
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = (time.perf_counter() - start) * 1000
        return AgentResult(
            task_id=agent_input.task_id,
            status=status,
            output_data=output,
            execution_meta=ExecutionMeta(
                execution_time_ms=round(elapsed_ms, 2),
                llm_used=False,
                llm_calls=0,
            ),
            error=error,
        )
