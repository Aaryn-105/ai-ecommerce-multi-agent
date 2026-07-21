"""Tests for Product Analysis — scorer and agent, driven by real FakeStore data."""
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from backend.agents.product_analysis.scorer import (
    safe_norm,
    compute_global_extrema,
    score_product,
    generate_selection_reason,
    price_segment,
)
from backend.agents.product_analysis.agent import ProductAnalysisAgent
from backend.agents.registry import AgentRegistry
from backend.agents.base import BaseAgent
from backend.models.schemas import AgentInput, ProductAnalysisOutput
from backend.services.fake_store import FakeStoreService


# ═══════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════

_REAL_PRODUCTS: list[dict] | None = None


@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    global _REAL_PRODUCTS
    if _REAL_PRODUCTS is not None:
        return _REAL_PRODUCTS
    svc = FakeStoreService()
    try:
        _REAL_PRODUCTS = await svc.get_all_products()
    finally:
        await svc.close()
    assert len(_REAL_PRODUCTS) == 20
    return _REAL_PRODUCTS


@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ═══════════════════════════════════════════════════════════
#  Scorer unit tests
# ═══════════════════════════════════════════════════════════

class TestSafeNorm:
    def test_normal_case(self):
        assert safe_norm(5, 0, 10) == 0.5

    def test_at_min(self):
        assert safe_norm(0, 0, 10) == 0.0

    def test_at_max(self):
        assert safe_norm(10, 0, 10) == 1.0

    def test_zero_range_returns_one(self):
        assert safe_norm(5, 5, 5) == 1.0

    def test_negative_values(self):
        assert safe_norm(-5, -10, 0) == 0.5


class TestComputeExtrema:
    @pytest.mark.asyncio
    async def test_extrema_from_real_products(self, real_products):
        extrema = compute_global_extrema(real_products)
        assert "rate" in extrema
        assert "count" in extrema
        assert "value" in extrema
        assert "desc" in extrema
        # Verify real ranges
        assert 0 < extrema["rate"]["min"] <= extrema["rate"]["max"] <= 5
        assert extrema["count"]["min"] >= 0
        assert extrema["count"]["max"] > 0
        assert extrema["value"]["min"] >= 0
        assert extrema["desc"]["min"] > 0
        print(f"  Rate range: {extrema['rate']['min']} - {extrema['rate']['max']}")
        print(f"  Count range: {extrema['count']['min']} - {extrema['count']['max']}")
        print(f"  Desc length range: {extrema['desc']['min']} - {extrema['desc']['max']}")

    def test_extrema_empty_products(self):
        with pytest.raises(ValueError):
            compute_global_extrema([])

    def test_extrema_single_product(self):
        extrema = compute_global_extrema([{
            "id": 1, "price": 10.0, "rating": {"rate": 4.0, "count": 100},
            "description": "abc",
        }])
        assert extrema["rate"]["min"] == extrema["rate"]["max"] == 4.0


class TestScoreProduct:
    @pytest.mark.asyncio
    async def test_score_real_products(self, real_products):
        extrema = compute_global_extrema(real_products)
        for p in real_products[:5]:
            result = score_product(p, extrema)
            assert 0 <= result["final_score"] <= 100
            assert result["dimensions"]["rating"] >= 0
            assert result["dimensions"]["rating"] <= 1
            assert result["contributions"]["rating"] >= 0
            assert "rating" in result["contributions"]
            assert "popularity" in result["contributions"]
            assert "value" in result["contributions"]
            assert "description" in result["contributions"]
            print(f"  Product {p['id']} ({p['title'][:30]}...): score={result['final_score']:.1f}")

    @pytest.mark.asyncio
    async def test_scores_are_deterministic(self, real_products):
        """Same input must produce identical scores."""
        extrema = compute_global_extrema(real_products)
        results_a = [score_product(p, extrema)["final_score"] for p in real_products]
        results_b = [score_product(p, extrema)["final_score"] for p in real_products]
        assert results_a == results_b

    @pytest.mark.asyncio
    async def test_top_product_has_highest_score(self, real_products):
        extrema = compute_global_extrema(real_products)
        scores = [score_product(p, extrema)["final_score"] for p in real_products]
        assert max(scores) >= min(scores)


class TestSelectionReason:
    @pytest.mark.asyncio
    async def test_generate_reason_from_real_data(self, real_products):
        extrema = compute_global_extrema(real_products)
        for p in real_products[:3]:
            scores = score_product(p, extrema)
            reason = generate_selection_reason(scores["contributions"], scores["dimensions"])
            assert isinstance(reason, str)
            assert len(reason) > 0
            print(f"  Product {p['id']}: {reason}")


class TestPriceSegment:
    def test_low(self):
        assert price_segment(15.0) == "低价(<30)"

    def test_medium(self):
        assert price_segment(50.0) == "中价(30-100)"

    def test_high(self):
        assert price_segment(150.0) == "高价(>100)"


# ═══════════════════════════════════════════════════════════
#  Agent integration tests
# ═══════════════════════════════════════════════════════════

class TestProductAnalysisAgent:
    @pytest.mark.asyncio
    async def test_agent_with_real_products(self, real_products):
        """Full pipeline: feed 20 real products, expect top 6 selected."""
        agent = ProductAnalysisAgent(top_n=6)
        inp = AgentInput(
            task_id="pa_001",
            request_id="req_pa_001",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        output = result.output_data
        assert len(output["selected_products"]) == 6
        assert output["statistics"]["total_analyzed"] == 20
        assert output["statistics"]["selected_count"] == 6
        assert output["summary"] != ""
        print(f"  Summary: {output['summary']}")

    @pytest.mark.asyncio
    async def test_top_product_is_reasonable(self, real_products):
        """The highest-scored product should have a plausible score."""
        agent = ProductAnalysisAgent(top_n=1)
        inp = AgentInput(
            task_id="pa_002",
            request_id="req_pa_002",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        top = result.output_data["selected_products"][0]
        assert top["final_score"] > 0
        assert top["final_score"] <= 100
        assert top["id"] in {p["id"] for p in real_products}
        assert top["selection_reason"] != ""

    @pytest.mark.asyncio
    async def test_empty_products(self):
        agent = ProductAnalysisAgent()
        inp = AgentInput(task_id="pa_empty", request_id="req_empty", input_data={"products": []})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["selected_products"] == []

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products):
        agent = ProductAnalysisAgent()
        inp = AgentInput(task_id="pa_schema", request_id="req_schema", input_data={"products": real_products})
        result = await agent.run(inp)
        parsed = ProductAnalysisOutput.model_validate(result.output_data)
        assert len(parsed.selected_products) == 6
        assert parsed.statistics.total_analyzed == 20

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products):
        agent = ProductAnalysisAgent()
        inp = AgentInput(task_id="pa_meta", request_id="req_meta", input_data={"products": real_products})
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_category_distribution_reflects_reality(self, real_products):
        agent = ProductAnalysisAgent(top_n=20)  # Select all
        inp = AgentInput(task_id="pa_cat", request_id="req_cat", input_data={"products": real_products})
        result = await agent.run(inp)
        cat_dist = result.output_data["statistics"]["category_distribution"]
        total = sum(cat_dist.values())
        assert total == 20
        # All 4 real categories should have products
        assert len(cat_dist) == 4
        print(f"  Category distribution: {cat_dist}")

    @pytest.mark.asyncio
    async def test_price_segment_distribution(self, real_products):
        agent = ProductAnalysisAgent(top_n=20)
        inp = AgentInput(task_id="pa_price", request_id="req_price", input_data={"products": real_products})
        result = await agent.run(inp)
        price_dist = result.output_data["statistics"]["price_segment_breakdown"]
        assert sum(price_dist.values()) == 20
        print(f"  Price segment distribution: {price_dist}")

    @pytest.mark.asyncio
    async def test_sorting_order_descending(self, real_products):
        agent = ProductAnalysisAgent(top_n=20)
        inp = AgentInput(task_id="pa_sort", request_id="req_sort", input_data={"products": real_products})
        result = await agent.run(inp)
        scores = [p["final_score"] for p in result.output_data["selected_products"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(ProductAnalysisAgent)
        cls = AgentRegistry.get("product_analysis")
        assert cls is ProductAnalysisAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products):
        """Verify the agent works when called via the Executor (orchestrator flow)."""
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep

        AgentRegistry.register(ProductAnalysisAgent)
        plan = [
            PlanStep(agent="product_analysis", params={"products": real_products}, depends_on=[]),
        ]
        executor = Executor(request_id="exec_pa")
        context = await executor.run(plan)
        assert "product_analysis" in context
        assert context["product_analysis"]["status"] == "completed"
        output = context["product_analysis"]["output_data"]
        assert len(output["selected_products"]) == 6

    @pytest.mark.asyncio
    async def test_different_top_n_values(self, real_products):
        for n in [1, 3, 10, 20]:
            agent = ProductAnalysisAgent(top_n=n)
            inp = AgentInput(task_id=f"pa_top{n}", request_id=f"req_top{n}", input_data={"products": real_products})
            result = await agent.run(inp)
            expected = min(n, 20)
            assert len(result.output_data["selected_products"]) == expected, f"Failed for top_n={n}"
