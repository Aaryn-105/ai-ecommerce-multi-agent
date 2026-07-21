"""DAG executor \u2014 runs plan steps in topological level-order with parallel execution."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, PlanStep

logger = logging.getLogger(__name__)


class Executor:
    """Executes a list of :class:`PlanStep` in topological dependency order.

    Independent agents at the same dependency level run concurrently
    via ``asyncio.gather``.
    """

    def __init__(self, request_id: str = "") -> None:
        self._request_id = request_id

    @staticmethod
    def _compute_levels(plan: list[PlanStep]) -> list[list[PlanStep]]:
        """Group plan steps by dependency depth (0 = no deps, 1 = depends on level 0, ...)."""
        step_by_name: dict[str, PlanStep] = {s.agent: s for s in plan}
        depth: dict[str, int] = {}

        def _depth_of(agent: str, _seen: set[str] | None = None) -> int:
            if agent in depth:
                return depth[agent]
            _seen = _seen or set()
            if agent in _seen:
                return 0
            _seen = _seen | {agent}
            step = step_by_name.get(agent)
            if step is None or not step.depends_on:
                depth[agent] = 0
                return 0
            d = 1 + max(_depth_of(dep, _seen) for dep in step.depends_on)
            depth[agent] = d
            return d

        for step in plan:
            _depth_of(step.agent)

        levels: list[list[PlanStep]] = defaultdict(list)
        for step in plan:
            levels[depth[step.agent]].append(step)
        return [levels[i] for i in sorted(levels.keys())]

    async def _run_step(
        self,
        step: PlanStep,
        shared_context: dict[str, Any],
        task_id: str,
        registered: set[str],
    ) -> tuple[str, dict[str, Any]]:
        """Run a single step. Returns (agent_name, context_entry)."""
        if step.agent not in registered:
            err = f"Unknown agent: {step.agent}"
            logger.warning("Skipping %s", err)
            return step.agent, {
                "task_id": task_id,
                "status": "failed",
                "output_data": {},
                "error": err,
            }

        agent_cls = AgentRegistry.get(step.agent)
        agent = agent_cls()
        inp = AgentInput(
            task_id=task_id,
            request_id=self._request_id,
            input_data=dict(step.params),
            context=dict(shared_context),
            dependencies=list(step.depends_on),
        )

        try:
            result = await agent.run(inp)
            if result.status == "failed":
                logger.warning("Agent %s failed: %s", step.agent, result.error)
            return step.agent, result.model_dump()
        except Exception as exc:
            logger.exception("Agent %s raised: %s", step.agent, exc)
            return step.agent, {
                "task_id": task_id,
                "status": "failed",
                "output_data": {},
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def run(
        self,
        plan: list[PlanStep],
        shared_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute plan steps in topological level order; parallelize within each level."""
        context: dict[str, Any] = dict(shared_context or {})
        registered = set(AgentRegistry.list_agents())
        levels = self._compute_levels(plan)
        task_counter = 0

        for level_idx, level_steps in enumerate(levels):
            coros = []
            for step in level_steps:
                task_counter += 1
                task_id = f"{step.agent}_{task_counter}"
                coros.append(self._run_step(step, context, task_id, registered))

            if len(coros) == 1:
                name, entry = await coros[0]
                context[f"{name}.error"] = entry.get("error")
                context[name] = entry
            else:
                results = await asyncio.gather(*coros, return_exceptions=False)
                for name, entry in results:
                    context[f"{name}.error"] = entry.get("error")
                    context[name] = entry

        return context
