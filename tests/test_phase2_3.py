"""Tests for Orchestrator — Planner, Executor, Replanner, Agent — with real FakeStore data."""
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from backend.agents.orchestrator.planner import Planner
from backend.agents.orchestrator.executor import Executor
from backend.agents.orchestrator.replanner import Replanner
from backend.agents.orchestrator.agent import OrchestratorAgent
from backend.agents.base import BaseAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import PlanStep, AgentInput
from backend.services.fake_store import FakeStoreService


# ═══════════════════════════════════════════════════════════
#  Test agents that process real FakeStore data
# ═══════════════════════════════════════════════════════════

class _RealProductCounter(BaseAgent):
    """Counts products fetched from the real API."""
    agent_name = "product_analysis"

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        svc = FakeStoreService()
        try:
            products = await svc.get_all_products()
        finally:
            await svc.close()
        return {
            "total_products": len(products),
            "categories": list({p["category"] for p in products}),
            "avg_price": round(sum(p["price"] for p in products) / len(products), 2),
            # Output data for downstream agents
            "selected_product_ids": [p["id"] for p in products],
            "all_products": products,
        }


class _RealPriceAnalyzer(BaseAgent):
    """Depends on product_analysis — computes price stats from real data."""
    agent_name = "pricing"

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Read upstream data from context
        upstream = context.get("product_analysis", {})
        output = upstream.get("output_data", {}) if isinstance(upstream, dict) else {}
        products = output.get("all_products", [])

        if not products:
            return {"error": "No products from upstream", "suggested_price": 0}

        prices = [p["price"] for p in products]
        return {
            "suggested_price": round(sum(prices) / len(prices), 2),
            "price_min": min(prices),
            "price_max": max(prices),
            "strategy": "follow_pricing",
        }


class _RealCategorySummarizer(BaseAgent):
    """Depends on product_analysis — summarize category distribution."""
    agent_name = "competitor_analysis"

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        upstream = context.get("product_analysis", {})
        output = upstream.get("output_data", {}) if isinstance(upstream, dict) else {}
        products = output.get("all_products", [])

        cats: dict[str, int] = {}
        for p in products:
            c = p["category"]
            cats[c] = cats.get(c, 0) + 1
        return {"category_counts": cats, "total_categories": len(cats)}


class _AlwaysFails(BaseAgent):
    """Agent that always fails — for replan tests."""
    agent_name = "always_fails"

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        msg = input_data.get("message", "intentional failure")
        raise RuntimeError(msg)



class _StubTrendForecast(BaseAgent):
    agent_name = "trend_forecast"
    async def execute(self, input_data, context):
        return {"forecast_7d": [10]*7, "forecast_30d": [10]*30, "summary": "Stable trend"}

class _StubMarketingCopy(BaseAgent):
    agent_name = "marketing_copy"
    async def execute(self, input_data, context):
        return {"copies": [{"product_id": 1, "tagline": "Great product!"}]}

class _StubInventory(BaseAgent):
    agent_name = "inventory"
    async def execute(self, input_data, context):
        return {"replenishment_plans": [], "overall_summary": {"urgent_count": 0}}

class _StubPromotion(BaseAgent):
    agent_name = "promotion"
    async def execute(self, input_data, context):
        return {"promotion_plan": {"promotion_type": "discount"}, "recommended_plan_index": 0}


# ═══════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    svc = FakeStoreService()
    try:
        return await svc.get_all_products()
    finally:
        await svc.close()


@pytest.fixture(autouse=True)
def _reg_cleanup():
    """Clean registry before and after each test."""
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ═══════════════════════════════════════════════════════════
#  Planner tests
# ═══════════════════════════════════════════════════════════

class TestPlanner:
    def test_default_plan_has_seven_steps(self):
        plan = Planner.default_plan()
        assert len(plan) == 7
        agents = [s.agent for s in plan]
        assert agents == [
            "product_analysis",
            "trend_forecast",
            "competitor_analysis",
            "marketing_copy",
            "inventory",
            "pricing",
            "promotion",
        ]

    def test_default_plan_steps_have_required_fields(self):
        for step in Planner.default_plan():
            assert step.agent
            assert isinstance(step.params, dict)
            assert isinstance(step.depends_on, list)
            assert step.description

    def test_topological_sort_produces_valid_order(self):
        plan = Planner.default_plan()
        sorted_steps = Planner.topological_dag(plan)
        # All 7 steps present
        assert len(sorted_steps) == 7
        # promotion must come after pricing, marketing_copy, inventory
        promo_idx = next(i for i, s in enumerate(sorted_steps) if s.agent == "promotion")
        pricing_idx = next(i for i, s in enumerate(sorted_steps) if s.agent == "pricing")
        marketing_idx = next(i for i, s in enumerate(sorted_steps) if s.agent == "marketing_copy")
        inventory_idx = next(i for i, s in enumerate(sorted_steps) if s.agent == "inventory")
        assert promo_idx > pricing_idx
        assert promo_idx > marketing_idx
        assert promo_idx > inventory_idx

    def test_topological_sort_detects_cycle(self):
        cyclic = [
            PlanStep(agent="a", params={}, depends_on=["b"]),
            PlanStep(agent="b", params={}, depends_on=["c"]),
            PlanStep(agent="c", params={}, depends_on=["a"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            Planner.topological_dag(cyclic)

    def test_no_dependency_steps(self):
        steps = [
            PlanStep(agent="a", depends_on=[]),
            PlanStep(agent="b", depends_on=[]),
        ]
        result = Planner.topological_dag(steps)
        assert len(result) == 2

    def test_llm_fallback_returns_default_plan(self):
        """When LLM is unavailable, plan() returns the default DAG."""
        planner = Planner()
        import asyncio
        plan = asyncio.run(planner.plan("analyze electronics"))
        assert len(plan) == 7  # falls back to default


# ═══════════════════════════════════════════════════════════
#  Executor tests
# ═══════════════════════════════════════════════════════════

class TestExecutor:
    @pytest.mark.asyncio
    async def test_execute_single_agent_with_real_data(self):
        """Register product_analysis counter and run with real API data."""
        AgentRegistry.register(_RealProductCounter)
        plan = [PlanStep(agent="product_analysis", params={}, depends_on=[])]
        executor = Executor(request_id="exec_001")
        context = await executor.run(plan)
        assert "product_analysis" in context
        output = context["product_analysis"]["output_data"]
        assert output["total_products"] == 20
        assert len(output["categories"]) == 4
        assert output["avg_price"] > 0
        print(f"  Real avg price: ${output['avg_price']}")

    @pytest.mark.asyncio
    async def test_execute_two_step_dag_with_real_data(self):
        """product_analysis → pricing, using real data."""
        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_RealPriceAnalyzer)
        plan = [
            PlanStep(agent="product_analysis", params={}, depends_on=[]),
            PlanStep(agent="pricing", params={}, depends_on=["product_analysis"]),
        ]
        executor = Executor(request_id="exec_002")
        context = await executor.run(plan)

        # product_analysis output
        assert "product_analysis" in context
        output_pa = context["product_analysis"]["output_data"]
        assert output_pa["total_products"] == 20

        # pricing output (depends on product_analysis context)
        assert "pricing" in context
        output_pr = context["pricing"]["output_data"]
        assert output_pr["suggested_price"] > 0
        assert output_pr["price_min"] < output_pr["price_max"]
        print(f"  Suggested price: ${output_pr['suggested_price']} (range: ${output_pr['price_min']} - ${output_pr['price_max']})")

    @pytest.mark.asyncio
    async def test_execute_three_step_chain(self):
        """product_analysis → pricing + competitor_analysis (parallel deps)."""
        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_RealPriceAnalyzer)
        AgentRegistry.register(_RealCategorySummarizer)
        plan = [
            PlanStep(agent="product_analysis", params={}, depends_on=[]),
            PlanStep(agent="pricing", params={}, depends_on=["product_analysis"]),
            PlanStep(agent="competitor_analysis", params={}, depends_on=["product_analysis"]),
        ]
        executor = Executor(request_id="exec_003")
        context = await executor.run(plan)

        assert context["pricing"]["status"] == "completed"
        assert context["competitor_analysis"]["status"] == "completed"
        cat_counts = context["competitor_analysis"]["output_data"]["category_counts"]
        assert len(cat_counts) == 4
        print(f"  Category counts: {cat_counts}")

    @pytest.mark.asyncio
    async def test_failed_step_does_not_crash_executor(self):
        AgentRegistry.register(_AlwaysFails)
        plan = [PlanStep(agent="always_fails", params={}, depends_on=[])]
        executor = Executor(request_id="exec_fail")
        context = await executor.run(plan)
        assert "always_fails" in context
        assert context["always_fails"]["status"] == "failed"
        assert "RuntimeError" in (context["always_fails"].get("error") or "")


# ═══════════════════════════════════════════════════════════
#  Replanner tests
# ═══════════════════════════════════════════════════════════

class TestReplanner:
    def test_drop_failed_and_dependents(self):
        plan = [
            PlanStep(agent="a", depends_on=[]),
            PlanStep(agent="b", depends_on=["a"]),
            PlanStep(agent="c", depends_on=["b"]),
        ]
        failed = [plan[0]]  # "a" fails
        result = Replanner._drop_failed_and_dependents(plan, failed)
        assert len(result) == 0  # all dependents removed

    def test_drop_leaf_failure(self):
        plan = [
            PlanStep(agent="a", depends_on=[]),
            PlanStep(agent="b", depends_on=["a"]),
        ]
        failed = [plan[1]]  # "b" fails
        result = Replanner._drop_failed_and_dependents(plan, failed)
        assert len(result) == 1
        assert result[0].agent == "a"

    def test_drop_middle_failure(self):
        plan = [
            PlanStep(agent="root", depends_on=[]),
            PlanStep(agent="middle", depends_on=["root"]),
            PlanStep(agent="leaf", depends_on=["middle"]),
            PlanStep(agent="other", depends_on=["root"]),
        ]
        failed = [plan[1]]  # "middle" fails
        result = Replanner._drop_failed_and_dependents(plan, failed)
        agents = {s.agent for s in result}
        assert "root" in agents
        assert "middle" not in agents
        assert "leaf" not in agents
        assert "other" in agents

    def test_no_failure_returns_empty(self):
        planner = Replanner()
        import asyncio
        result = asyncio.run(planner.replan("test query", [], {}))
        assert result == []


# ═══════════════════════════════════════════════════════════
#  OrchestratorAgent — full integration with real data
# ═══════════════════════════════════════════════════════════

class TestOrchestratorAgent:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_data(self):
        """Register 3 real-data agents and run the orchestrator end-to-end."""
        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_RealPriceAnalyzer)
        AgentRegistry.register(_RealCategorySummarizer)
        AgentRegistry.register(_StubTrendForecast)
        AgentRegistry.register(_StubMarketingCopy)
        AgentRegistry.register(_StubInventory)
        AgentRegistry.register(_StubPromotion)

        agent = OrchestratorAgent()
        inp = AgentInput(
            task_id="orch_001",
            request_id="req_orch_001",
            input_data={"message": "analyze all products from FakeStore API"},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        report = result.output_data["final_report"]
        assert report["total_agents_run"] == 7
        assert "product_analysis" in report["sections"]
        assert "pricing" in report["sections"]
        assert "competitor_analysis" in report["sections"]
        print(f"  Report summary: {report['summary']}")
        print(f"  Agents executed: {report['total_agents_run']} in {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_orchestrator_with_empty_query(self):
        agent = OrchestratorAgent()
        inp = AgentInput(
            task_id="orch_empty",
            request_id="req_empty",
            input_data={"message": ""},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data.get("final_report") is None

    @pytest.mark.asyncio
    async def test_orchestrator_execution_meta(self):
        AgentRegistry.register(_RealProductCounter)
        agent = OrchestratorAgent()
        inp = AgentInput(
            task_id="orch_meta",
            request_id="req_meta",
            input_data={"message": "analyze products"},
        )
        result = await agent.run(inp)
        assert result.execution_meta.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_orchestrator_handles_agent_failure_gracefully(self):
        """When AlwaysFails is included, orchestrator should still complete."""
        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_AlwaysFails)
        # Override default plan: only use these two
        from backend.agents.orchestrator.planner import Planner
        class _CustomPlanner(Planner):
            async def plan(self, query):
                return [
                    PlanStep(agent="product_analysis", params={}, depends_on=[]),
                    PlanStep(agent="always_fails", params={}, depends_on=["product_analysis"]),
                ]
        agent = OrchestratorAgent(planner=_CustomPlanner())
        inp = AgentInput(
            task_id="orch_fail",
            request_id="req_fail",
            input_data={"message": "test failure handling"},
        )
        result = await agent.run(inp)
        assert result.status == "completed"  # orchestrator itself doesn't crash


# ═══════════════════════════════════════════════════════════
#  LangGraph workflow (smoke test)
# ═══════════════════════════════════════════════════════════

class TestLangGraphWorkflow:
    @pytest.mark.asyncio
    async def test_workflow_builds_and_runs(self):
        """Verify the LangGraph graph compiles and can be invoked with real data."""
        from backend.agents.orchestrator.workflow import build_workflow, WorkflowState

        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_RealPriceAnalyzer)
        AgentRegistry.register(_RealCategorySummarizer)
        AgentRegistry.register(_StubTrendForecast)
        AgentRegistry.register(_StubMarketingCopy)
        AgentRegistry.register(_StubInventory)
        AgentRegistry.register(_StubPromotion)

        graph = build_workflow()
        state: WorkflowState = {
            "query": "analyze products",
            "request_id": "lg_001",
            "plan_steps": [],
            "context": {},
            "attempt": 0,
            "max_attempts": 2,
        }
        result = await graph.ainvoke(state)
        assert "context" in result
        assert "product_analysis" in result["context"]
        assert result["context"]["product_analysis"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_workflow_handles_failure_via_replan(self):
        """When AlwaysFails is in the plan, the graph should route through replan."""
        from backend.agents.orchestrator.workflow import build_workflow, WorkflowState
        from backend.models.schemas import PlanStep

        AgentRegistry.register(_RealProductCounter)
        AgentRegistry.register(_AlwaysFails)

        graph = build_workflow()

        # Manually inject a plan that includes AlwaysFails
        plan_dicts = [
            PlanStep(agent="product_analysis", params={}, depends_on=[]).model_dump(),
            PlanStep(agent="always_fails", params={}, depends_on=["product_analysis"]).model_dump(),
        ]
        state: WorkflowState = {
            "query": "test",
            "request_id": "lg_fail",
            "plan_steps": plan_dicts,
            "context": {},
            "attempt": 0,
            "max_attempts": 2,
        }
        result = await graph.ainvoke(state)
        # Should have attempted replan and produced a context with results
        assert "context" in result
        assert "product_analysis" in result["context"]
