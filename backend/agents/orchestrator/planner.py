"""Plan generation: LLM-first, rule-based fallback."""
from __future__ import annotations

from typing import Any

from backend.models.schemas import PlanStep
from backend.services.llm_service import LLMService

# ── Default DAG plan (fallback) ──────────────────────────
# Covers the standard e-commerce analysis pipeline.

_DEFAULT_PLAN: list[dict[str, Any]] = [
    {
        "agent": "product_analysis",
        "params": {},
        "depends_on": [],
        "description": "Fetch all products from FakeStore, score and rank by 4 dimensions",
    },
    {
        "agent": "trend_forecast",
        "params": {"days": 30, "window": 7},
        "depends_on": ["product_analysis"],
        "description": "Forecast 7/30-day sales trend for top products",
    },
    {
        "agent": "competitor_analysis",
        "params": {},
        "depends_on": ["product_analysis"],
        "description": "Benchmark selected products against category competitors",
    },
    {
        "agent": "marketing_copy",
        "params": {},
        "depends_on": ["product_analysis", "competitor_analysis"],
        "description": "Generate taglines, bullets, descriptions and social copy",
    },
    {
        "agent": "inventory",
        "params": {},
        "depends_on": ["product_analysis"],
        "description": "Assess stock health and compute replenishment suggestions",
    },
    {
        "agent": "pricing",
        "params": {},
        "depends_on": ["product_analysis", "competitor_analysis"],
        "description": "Calculate suggested price via 3-factor model and strategy label",
    },
    {
        "agent": "promotion",
        "params": {},
        "depends_on": ["pricing", "marketing_copy", "inventory"],
        "description": "Design promotion type, calculate discounts, and recommend best plan",
    },
]

_LLM_SYSTEM_PROMPT = (
    "You are a planning agent for an e-commerce multi-agent system. "
    "Given a user query, produce a JSON list of steps to execute. "
    "Each step must have: agent (str), params (dict), depends_on (list of str), description (str). "
    "Available agents: product_analysis, trend_forecast, competitor_analysis, "
    "marketing_copy, inventory, pricing, promotion. "
    "Respond with a JSON array only, no extra text."
)


class Planner:
    """Generates a list of :class:`PlanStep` from a user query.

    Uses LLM first; falls back to a static default DAG when the LLM
    is unavailable or returns invalid output.
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    async def plan(self, query: str) -> list[PlanStep]:
        """Produce a plan. Returns the default DAG on LLM failure."""
        # ── Attempt LLM plan ─────────────────────────────
        llm_result = await self._llm.chat(
            system_prompt=_LLM_SYSTEM_PROMPT,
            user_message=query,
            fallback=None,
        )

        if isinstance(llm_result, list) and len(llm_result) > 0:
            try:
                return [PlanStep.model_validate(s) for s in llm_result]
            except Exception:
                pass

        # ── Fallback: default DAG ────────────────────────
        return self.default_plan()

    @staticmethod
    def default_plan() -> list[PlanStep]:
        """Return the canonical 7-step DAG plan."""
        return [PlanStep.model_validate(s) for s in _DEFAULT_PLAN]

    @staticmethod
    def topological_dag(plan: list[PlanStep]) -> list[PlanStep]:
        """Topological sort so that all dependencies come before dependents.

        Raises :class:`ValueError` if a cycle is detected.
        """
        step_map: dict[str, PlanStep] = {s.agent: s for s in plan}
        visited: set[str] = set()
        sorted_steps: list[PlanStep] = []

        def _dfs(agent: str, path: set[str]) -> None:
            if agent in path:
                cycle = " → ".join(path | {agent})
                raise ValueError(f"Dependency cycle detected: {cycle}")
            if agent in visited:
                return
            step = step_map.get(agent)
            if step is None:
                return
            path.add(agent)
            for dep in step.depends_on:
                _dfs(dep, path)
            path.remove(agent)
            visited.add(agent)
            sorted_steps.append(step)

        for s in plan:
            _dfs(s.agent, set())

        return sorted_steps
