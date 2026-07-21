"""Plan generation: uses deterministic rule-based DAG (no LLM for planning)."""
from __future__ import annotations

from typing import Any

from backend.models.schemas import PlanStep

# ── Default DAG plan ─────────────────────────────────────
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

# Two-level mapping: alias_key -> (matching_keywords_tuple, fakestore_category)
# matching_keywords are used to detect user intent from the query.
# fakestore_category is what we send to the product analysis agent's filter.
_CATEGORY_ALIASES: dict[str, tuple[tuple[str, ...], str]] = {
    "electronics": (("电子产品", "电子", "数码", "electronics"), "electronics"),
    "backpack": (("背包", "backpack", "backpacks"), "men's clothing"),
    "jewelery": (("玩偶", "饰品", "珐瑙", "jewelry", "jewelery"), "jewelery"),
    "women's clothing": (("女装", "女士服装", "women's clothing", "dresses", "skirts"), "women's clothing"),
    "men's clothing": (("男装", "男士服装", "men's clothing", "shirts", "jackets"), "men's clothing"),
}


def _alias_to_fakestore(alias_key: str) -> str:
    """Return the FakeStore category that an alias_key maps to."""
    if alias_key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[alias_key][1]
    return alias_key




def _contains_any(query: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in query.lower() for keyword in keywords)


def extract_category(query: str) -> str | list[str] | None:
    """Extract a FakeStore category filter from a natural-language query.

    Returns the FakeStore category name (e.g. "men's clothing", "electronics")
    so the product analysis agent's filter works correctly.
    """
    normalized = query.lower()
    if "服装" in normalized and "女装" not in normalized and "男装" not in normalized:
        return ["men's clothing", "women's clothing"]
    for alias_key, (aliases, fakestore_cat) in _CATEGORY_ALIASES.items():
        if _contains_any(normalized, aliases):
            return fakestore_cat
    return None


def _dynamic_intents(query: str) -> set[str]:
    normalized = query.lower()
    intents: set[str] = set()
    if _contains_any(normalized, ("选品", "商品推荐", "推荐商品", "选品机会", "acquisition", "拉新")):
        intents.add("selection")
    if _contains_any(normalized, ("趋势", "趋势预测", "销售趋势", "销量趋势", "forecast", "trend")):
        intents.add("trend")
    if _contains_any(normalized, ("竞品", "竞争对比", "竞品分析", "对比", "competitor")):
        intents.add("competitor")
    if _contains_any(normalized, ("营销文案", "推广文案", "广告语", "文案", "marketing copy")):
        intents.add("marketing")
    elif "营销" in normalized and "趋势" not in normalized:
        intents.add("marketing")
    if _contains_any(normalized, ("库存", "补货", "备货", "inventory")):
        intents.add("inventory")
    if _contains_any(normalized, ("定价", "价格策略", "调价", "pricing")):
        intents.add("pricing")
    if _contains_any(normalized, ("促销", "打折", "优惠", "秒杀", "promotion")):
        intents.add("promotion")
    return intents


class Planner:
    """Generates a list of :class:`PlanStep` from a user query.

    Uses a deterministic rule-based DAG plan (no LLM call) to ensure
    consistent 7-agent pipeline execution.
    """

    async def plan(self, query: str) -> list[PlanStep]:
        """Produce a task-specific DAG while preserving the full default plan fallback."""
        intents = _dynamic_intents(query)
        if not intents:
            return self.default_plan()

        category = extract_category(query)
        steps: list[PlanStep] = []
        added: set[str] = set()

        def add_step(
            agent: str,
            description: str,
            depends_on: list[str] | None = None,
            report: bool = True,
        ) -> None:
            if agent in added:
                return
            params: dict[str, Any] = {}
            if category is not None:
                params["category"] = category
            steps.append(
                PlanStep(
                    agent=agent,
                    params=params,
                    depends_on=depends_on or [],
                    description=description,
                    report=report,
                )
            )
            added.add(agent)

        def ensure_product_support() -> None:
            add_step("product_analysis", "按目标类目筛选并评分真实商品", report=False)

        if "selection" in intents:
            add_step("product_analysis", "按目标类目进行目标驱动选品", report=True)
            add_step("trend_forecast", "对候选商品进行销量趋势预测", ["product_analysis"])
        if "trend" in intents:
            ensure_product_support()
            add_step("trend_forecast", "对目标类目进行时间序列趋势预测", ["product_analysis"])
        if "competitor" in intents:
            ensure_product_support()
            add_step("competitor_analysis", "对目标类目进行竞品基准与竞争力对比", ["product_analysis"])
        if "marketing" in intents:
            ensure_product_support()
            add_step("marketing_copy", "基于目标类目商品生成营销文案与卖点", ["product_analysis"])
        if "inventory" in intents:
            ensure_product_support()
            add_step("inventory", "评估目标类目库存健康度与补货需求", ["product_analysis"])
        if "pricing" in intents:
            ensure_product_support()
            add_step("competitor_analysis", "提供目标类目价格与竞品基准", ["product_analysis"], report=False)
            add_step("pricing", "基于竞品和商品表现制定定价策略", ["product_analysis", "competitor_analysis"])
        if "promotion" in intents:
            ensure_product_support()
            add_step("competitor_analysis", "提供目标类目促销基准", ["product_analysis"], report=False)
            add_step("marketing_copy", "为促销方案提供商品卖点文案", ["product_analysis"], report=False)
            add_step("inventory", "为促销方案提供库存约束", ["product_analysis"], report=False)
            add_step("pricing", "为促销方案提供价格基线", ["product_analysis", "competitor_analysis"], report=False)
            add_step("promotion", "匹配促销类型并给出促销方案", ["pricing", "marketing_copy", "inventory"])

        return steps or self.default_plan()

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
                cycle = " \u2192 ".join(path | {agent})
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
