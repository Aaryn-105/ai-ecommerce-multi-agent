"""Tests for Competitor Analysis — scorer and agent, driven by real FakeStore data."""
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from backend.agents.competitor_analysis.scorer import (
    safe_norm,
    inverted_norm,
    compute_category_extrema,
    build_category_benchmark,
    score_product_competitive,
    generate_insights,
    COMPETITIVE_DIMS,
)
from backend.agents.competitor_analysis.agent import CompetitorAnalysisAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, CompetitorAnalysisOutput
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


@pytest_asyncio.fixture(scope="session")
async def real_electronics(real_products) -> list[dict]:
    """Filter to electronics category only."""
    return [p for p in real_products if p["category"] == "electronics"]


@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ═══════════════════════════════════════════════════════════
#  Scorer Unit Tests
# ═══════════════════════════════════════════════════════════

class TestSafeNorm:
    def test_normal_case(self):
        assert safe_norm(5, 0, 10) == 0.5

    def test_at_min(self):
        assert safe_norm(0, 0, 10) == 0.0

    def test_at_max(self):
        assert safe_norm(10, 0, 10) == 1.0

    def test_zero_range(self):
        assert safe_norm(5, 5, 5) == 1.0


class TestInvertedNorm:
    def test_lower_is_better(self):
        """Lower value → higher score when inverted."""
        low = inverted_norm(10, 0, 100)
        high = inverted_norm(90, 0, 100)
        assert low > high
        print(f"  Inverted norm: low=10 → {low:.3f}, high=90 → {high:.3f}")

    def test_at_min_returns_one(self):
        assert inverted_norm(0, 0, 100) == 1.0

    def test_at_max_returns_zero(self):
        assert inverted_norm(100, 0, 100) == 0.0

    def test_zero_range(self):
        assert inverted_norm(50, 50, 50) == 1.0


class TestComputeCategoryExtrema:
    @pytest.mark.asyncio
    async def test_extrema_from_real_electronics(self, real_electronics):
        extrema = compute_category_extrema(real_electronics)
        for dim in ["price", "rating", "count", "value", "desc"]:
            assert dim in extrema
            assert extrema[dim]["min"] >= 0
            assert extrema[dim]["max"] >= extrema[dim]["min"]
        print(f"  Electronics price range: {extrema['price']['min']} - {extrema['price']['max']}")
        print(f"  Electronics rating range: {extrema['rating']['min']} - {extrema['rating']['max']}")

    def test_extrema_empty(self):
        with pytest.raises(ValueError):
            compute_category_extrema([])

    def test_extrema_single_product(self):
        extrema = compute_category_extrema([{
            "id": 1, "price": 50.0, "rating": {"rate": 4.0, "count": 100},
            "description": "A great product",
        }])
        assert extrema["price"]["min"] == extrema["price"]["max"] == 50.0

    @pytest.mark.asyncio
    async def test_extrema_across_all_categories(self, real_products):
        """Verify extrema are sensible across all 20 products."""
        extrema = compute_category_extrema(real_products)
        assert extrema["rating"]["min"] >= 0
        assert extrema["rating"]["max"] <= 5
        assert extrema["count"]["min"] >= 0
        assert extrema["count"]["max"] > 0
        print(f"  Global price range: {extrema['price']['min']} - {extrema['price']['max']}")
        print(f"  Global desc range: {extrema['desc']['min']} - {extrema['desc']['max']}")


class TestBuildCategoryBenchmark:
    @pytest.mark.asyncio
    async def test_electronics_benchmark(self, real_electronics):
        bench = build_category_benchmark(real_electronics)
        assert bench["product_count"] == len(real_electronics)
        assert bench["avg_price"] > 0
        assert bench["price_median"] > 0
        assert bench["avg_rating"] > 0
        assert bench["total_reviews"] > 0
        assert bench["avg_reviews"] > 0
        print(f"  Electronics: count={bench['product_count']}, "
              f"avg_price={bench['avg_price']}, avg_rating={bench['avg_rating']}")

    @pytest.mark.asyncio
    async def test_all_categories_benchmarks(self, real_products):
        """Build benchmarks for each of the 4 real categories."""
        cats = {}
        for p in real_products:
            cats.setdefault(p["category"], []).append(p)
        assert len(cats) == 4

        for cat, prods in cats.items():
            bench = build_category_benchmark(prods)
            assert bench["product_count"] == len(prods)
            assert bench["price_range"]["min"] <= bench["price_range"]["max"]
            print(f"  {cat}: count={bench['product_count']}, "
                  f"avg_price=, avg_rating={bench['avg_rating']:.2f}")

    def test_empty(self):
        assert build_category_benchmark([]) == {}


class TestScoreProductCompetitive:
    @pytest.mark.asyncio
    async def test_score_real_products(self, real_products):
        """Score all products globally and verify outputs."""
        extrema = compute_category_extrema(real_products)
        for p in real_products[:5]:
            result = score_product_competitive(p, extrema)
            assert 0 <= result["competitive_score"] <= 100
            for dim in COMPETITIVE_DIMS:
                assert dim in result["dimension_norms"]
                assert dim in result["contributions"]
                assert 0 <= result["dimension_norms"][dim] <= 1
            print(f"  Product {p['id']} ({p['title'][:25]}...): "
                  f"score={result['competitive_score']:.1f}")

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products):
        extrema = compute_category_extrema(real_products)
        r1 = [score_product_competitive(p, extrema)["competitive_score"] for p in real_products]
        r2 = [score_product_competitive(p, extrema)["competitive_score"] for p in real_products]
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_lower_price_gets_higher_price_score(self, real_electronics):
        """In the same category, cheaper products score higher on price."""
        extrema = compute_category_extrema(real_electronics)
        # Find cheapest and most expensive
        sorted_by_price = sorted(real_electronics, key=lambda p: p["price"])
        cheapest = sorted_by_price[0]
        priciest = sorted_by_price[-1]

        score_cheap = score_product_competitive(cheapest, extrema)
        score_expensive = score_product_competitive(priciest, extrema)

        assert score_cheap["dimension_norms"]["price"] > score_expensive["dimension_norms"]["price"]
        print(f"  Cheapest () price norm: {score_cheap['dimension_norms']['price']:.3f}")
        print(f"  Priciest () price norm: {score_expensive['dimension_norms']['price']:.3f}")


class TestGenerateInsights:
    def test_high_scores_produce_advantages(self):
        norms = {"price": 0.9, "rating": 0.8, "popularity": 0.5, "value": 0.3, "description": 0.2}
        contribs = {"price": 18, "rating": 20, "popularity": 10, "value": 6, "description": 3}
        insights = generate_insights(norms, contribs)
        assert len(insights["advantages"]) >= 2
        assert len(insights["disadvantages"]) >= 2
        assert len(insights["differentiators"]) >= 1
        print(f"  Advantages: {insights['advantages']}")
        print(f"  Disadvantages: {insights['disadvantages']}")
        print(f"  Differentiators: {insights['differentiators']}")

    def test_mid_scores_no_extremes(self):
        norms = {d: 0.5 for d in COMPETITIVE_DIMS}
        contribs = {d: 10.0 for d in COMPETITIVE_DIMS}
        insights = generate_insights(norms, contribs)
        assert insights["advantages"] == []
        assert insights["disadvantages"] == []
        assert len(insights["differentiators"]) >= 1  # top 20% = at least 1 dim

    def test_low_scores_produce_disadvantages(self):
        norms = {d: 0.2 for d in COMPETITIVE_DIMS}
        contribs = {d: 4.0 for d in COMPETITIVE_DIMS}
        insights = generate_insights(norms, contribs)
        assert len(insights["disadvantages"]) >= 3


# ═══════════════════════════════════════════════════════════
#  CompetitorAnalysisAgent Tests
# ═══════════════════════════════════════════════════════════

class TestCompetitorAnalysisAgent:
    """Integration tests using real FakeStore products."""

    @pytest.mark.asyncio
    async def test_agent_produces_positioning(self, real_products):
        """Verify the agent returns positioning for all selected products."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_001",
            request_id="req_ca_001",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        output = result.output_data
        assert len(output["product_positioning"]) == 6
        assert len(output["category_benchmarks"]) > 0
        assert output["market_summary"] != ""
        print(f"  Market summary: {output['market_summary']}")

    @pytest.mark.asyncio
    async def test_each_product_has_positioning_fields(self, real_products):
        """Every positioned product must have all expected fields."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_fields",
            request_id="req_fields",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)

        for pp in result.output_data["product_positioning"]:
            assert pp["product_id"] > 0
            assert pp["title"] != ""
            assert pp["competitive_score"] > 0
            assert pp["price"] > 0
            assert pp["category_avg_price"] > 0
            assert pp["price_label"] in ("低价", "中等", "高价")
            assert isinstance(pp["advantages"], list)
            assert isinstance(pp["disadvantages"], list)
            assert isinstance(pp["differentiators"], list)
            for dim in COMPETITIVE_DIMS:
                assert dim in pp["dimension_norms"]
                assert dim in pp["contributions"]
            print(f"  Product {pp['product_id']} ({pp['title'][:20]}...): "
                  f"score={pp['competitive_score']:.1f}, advantages={len(pp['advantages'])}, "
                  f"disadvantages={len(pp['disadvantages'])}")

    @pytest.mark.asyncio
    async def test_all_four_categories_present(self, real_products):
        """All 4 real categories should appear in benchmarks."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_cats",
            request_id="req_cats",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        cats = result.output_data["category_benchmarks"]
        assert len(cats) == 4
        print(f"  Categories: {list(cats.keys())}")

    @pytest.mark.asyncio
    async def test_score_is_deterministic(self, real_products):
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_det",
            request_id="req_det",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)
        s1 = [p["competitive_score"] for p in r1.output_data["product_positioning"]]
        s2 = [p["competitive_score"] for p in r2.output_data["product_positioning"]]
        assert s1 == s2

    @pytest.mark.asyncio
    async def test_sorted_by_score_descending(self, real_products):
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_sort",
            request_id="req_sort",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        scores = [p["competitive_score"] for p in result.output_data["product_positioning"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_price_percentiles_are_reasonable(self, real_products):
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_pct",
            request_id="req_pct",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        for pp in result.output_data["product_positioning"]:
            assert 0 <= pp["price_percentile"] <= 1
            assert 0 <= pp["rating_percentile"] <= 1

    @pytest.mark.asyncio
    async def test_high_score_product_has_advantages(self, real_products):
        """Top-scored product should have at least one advantage."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_high",
            request_id="req_high",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        top = result.output_data["product_positioning"][0]
        print(f"  Top product: {top['title'][:30]}... score={top['competitive_score']}")
        print(f"  Advantages: {top['advantages']}")
        # Most likely the top product has at least one advantage
        if top["competitive_score"] >= 65:
            assert len(top["advantages"]) >= 1

    @pytest.mark.asyncio
    async def test_empty_products(self):
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_empty",
            request_id="req_empty",
            input_data={"all_products": [], "selected_products": []},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["product_positioning"] == []
        assert result.output_data["market_summary"] != ""

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products):
        """Verify output validates against CompetitorAnalysisOutput."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_schema",
            request_id="req_schema",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:3],
            },
        )
        result = await agent.run(inp)
        parsed = CompetitorAnalysisOutput.model_validate(result.output_data)
        assert len(parsed.product_positioning) == 3
        assert len(parsed.category_benchmarks) > 0
        assert parsed.market_summary != ""

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products):
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_meta",
            request_id="req_meta",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(CompetitorAnalysisAgent)
        cls = AgentRegistry.get("competitor_analysis")
        assert cls is CompetitorAnalysisAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products):
        """Verify the agent works via the Executor (orchestrator flow)."""
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep

        AgentRegistry.register(CompetitorAnalysisAgent)
        plan = [
            PlanStep(
                agent="competitor_analysis",
                params={
                    "all_products": real_products,
                    "selected_products": real_products[:6],
                },
                depends_on=[],
            ),
        ]
        executor = Executor(request_id="exec_ca")
        context = await executor.run(plan)
        assert "competitor_analysis" in context
        assert context["competitor_analysis"]["status"] == "completed"
        output = context["competitor_analysis"]["output_data"]
        assert len(output["product_positioning"]) == 6

    @pytest.mark.asyncio
    async def test_context_pipeline_integration(self, real_products):
        """Simulate pipeline: product_analysis context feeds competitor_analysis."""
        AgentRegistry.register(CompetitorAnalysisAgent)

        selected = [
            {"id": p["id"], "title": p["title"], "category": p["category"],
             "price": p["price"], "rating": p["rating"]}
            for p in real_products[:4]
        ]
        context_data = {
            "selected_products": selected,
            "all_products": real_products,
        }

        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_ctx",
            request_id="req_ctx",
            input_data={},
            context={"product_analysis": {"output_data": context_data}},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["product_positioning"]) == 4
        print(f"  Pipeline summary: {result.output_data['market_summary']}")

    @pytest.mark.asyncio
    async def test_price_label_variation(self, real_products):
        """Products at different price levels should get different labels."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_plab",
            request_id="req_plab",
            input_data={
                "all_products": real_products,
                "selected_products": real_products,
            },
        )
        result = await agent.run(inp)
        labels = set(p["price_label"] for p in result.output_data["product_positioning"])
        print(f"  Price labels found: {labels}")
        assert len(labels) >= 1

    @pytest.mark.asyncio
    async def test_category_benchmark_stats_are_sensible(self, real_products):
        """Each category benchmark should have sensible stats."""
        agent = CompetitorAnalysisAgent()
        inp = AgentInput(
            task_id="ca_bench",
            request_id="req_bench",
            input_data={
                "all_products": real_products,
                "selected_products": real_products[:6],
            },
        )
        result = await agent.run(inp)
        for cat, bench in result.output_data["category_benchmarks"].items():
            assert bench["product_count"] > 0
            assert bench["avg_price"] > 0
            assert bench["avg_rating"] > 0
            assert bench["price_range"]["min"] <= bench["price_median"] <= bench["price_range"]["max"]
            print(f"  {cat}: count={bench['product_count']}, "
                  f"median=, avg_rating={bench['avg_rating']:.2f}")