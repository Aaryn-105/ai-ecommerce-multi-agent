"""Tests for Pricing \u2014 models and agent, driven by real FakeStore data."""
from __future__ import annotations
from typing import Any
import pytest
import pytest_asyncio
from backend.agents.pricing.models import (
    compute_cost_plus_price, compute_competitor_price, compute_value_price,
    compute_dynamic_factor, classify_strategy, compute_suggested_price)
from backend.agents.pricing.agent import PricingAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, PricingOutput
from backend.services.fake_store import FakeStoreService

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
async def market_benchmarks(real_products) -> dict[str, dict]:
    cats = {}
    for p in real_products:
        cats.setdefault(p["category"], []).append(p)
    benchmarks = {}
    for cat, prods in cats.items():
        prices = [p["price"] for p in prods]
        benchmarks[cat] = {
            "product_count": len(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "price_median": sorted(prices)[len(prices) // 2],
        }
    return benchmarks

@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()

# ── Model unit tests ──

class TestComputeCostPlusPrice:
    def test_default_margin(self):
        assert compute_cost_plus_price(100.0) == 125.0

    def test_custom_margin(self):
        assert compute_cost_plus_price(100.0, 0.5) == 150.0

    def test_zero_price(self):
        assert compute_cost_plus_price(0.0) == 0.0

class TestComputeCompetitorPrice:
    def test_with_avg_price(self):
        b = {"avg_price": 50.0}
        assert compute_competitor_price(b) == 50.0

    def test_with_median(self):
        b = {"price_median": 45.0}
        assert compute_competitor_price(b) == 45.0

    def test_empty_benchmark(self):
        assert compute_competitor_price(None) == 0.0

    def test_empty_dict(self):
        assert compute_competitor_price({}) == 0.0

    @pytest.mark.asyncio
    async def test_from_real_benchmarks(self, market_benchmarks):
        for cat, b in market_benchmarks.items():
            cp = compute_competitor_price(b)
            assert cp > 0
            print(f"  {cat}: competitor_price=${cp:.2f}")

class TestComputeValuePrice:
    def test_no_position_data(self):
        assert compute_value_price(100.0, None) == 100.0

    def test_high_rating_premium(self):
        pos = {"rating": 4.8, "competitive_score": 85,
               "rating_percentile": 0.9, "price_percentile": 0.3}
        vp = compute_value_price(100.0, pos)
        assert vp > 100.0
        print(f"  Value price (high rating): ${vp:.2f}")

    def test_low_rating_discount(self):
        pos = {"rating": 2.0, "competitive_score": 20,
               "rating_percentile": 0.2, "price_percentile": 0.9}
        vp = compute_value_price(100.0, pos)
        assert vp < 100.0
        print(f"  Value price (low rating): ${vp:.2f}")

class TestComputeDynamicFactor:
    def test_no_position(self):
        assert compute_dynamic_factor(None) == 1.0

    def test_advantages_increase_factor(self):
        pos = {"advantages": ["low price", "high rating"],
               "disadvantages": [], "differentiators": ["quality"]}
        factor = compute_dynamic_factor(pos)
        assert factor > 1.0

    def test_disadvantages_decrease(self):
        pos = {"advantages": [], "disadvantages": ["high price", "low rating"],
               "differentiators": []}
        factor = compute_dynamic_factor(pos)
        assert factor < 1.0

class TestClassifyStrategy:
    def test_penetration_big_drop(self):
        result = classify_strategy(80, 100, 90, 50, 3.0)
        assert result["strategy"] == "penetration"

    def test_skimming(self):
        result = classify_strategy(130, 100, 90, 80, 4.5)
        assert result["strategy"] == "skimming"

    def test_follow(self):
        result = classify_strategy(103, 100, 100, 50, 3.0)
        assert result["strategy"] == "follow"

    def test_price_up(self):
        result = classify_strategy(110, 100, 95, 60, 3.5)
        assert result["strategy"] == "price-up"

    def test_price_down(self):
        result = classify_strategy(92, 100, 100, 40, 3.0)
        assert result["strategy"] == "price-down"

class TestComputeSuggestedPrice:
    @pytest.mark.asyncio
    async def test_from_real_data(self, real_products, market_benchmarks):
        p = real_products[0]
        bench = market_benchmarks.get(p["category"], {})
        pos = {"rating": p["rating"]["rate"], "competitive_score": 60,
               "rating_percentile": 0.6, "price_percentile": 0.4,
               "advantages": [], "disadvantages": [], "differentiators": []}
        result = compute_suggested_price(p["price"], bench, pos)
        assert result["suggested_price"] > 0
        assert "strategy" in result
        assert result["factor_breakdown"]["cost_plus"] > 0
        print(f"  {p['title'][:25]}: ${p['price']:.2f} \u2192 ${result['suggested_price']:.2f} "
              f"({result['strategy']}, {result['confidence']})")

    @pytest.mark.asyncio
    async def test_from_real_all_products(self, real_products, market_benchmarks):
        for p in real_products:
            bench = market_benchmarks.get(p["category"], {})
            pos = {"rating": p["rating"]["rate"], "competitive_score": 50,
                   "rating_percentile": 0.5, "price_percentile": 0.5,
                   "advantages": [], "disadvantages": [], "differentiators": []}
            result = compute_suggested_price(p["price"], bench, pos)
            assert result["suggested_price"] >= 0.01

    def test_deterministic(self):
        bench = {"avg_price": 50.0}
        pos = {"rating": 4.0, "competitive_score": 60,
               "rating_percentile": 0.6, "price_percentile": 0.5,
               "advantages": [], "disadvantages": [], "differentiators": []}
        r1 = compute_suggested_price(100.0, bench, pos)
        r2 = compute_suggested_price(100.0, bench, pos)
        assert r1["suggested_price"] == r2["suggested_price"]

    def test_floor_ceiling(self):
        """Very high price should be capped by ceiling."""
        bench = {"avg_price": 50.0}
        pos = {"rating": 4.0, "competitive_score": 60,
               "rating_percentile": 0.6, "price_percentile": 0.5,
               "advantages": [], "disadvantages": [], "differentiators": []}
        result = compute_suggested_price(500.0, bench, pos)
        assert result["suggested_price"] <= 50.0 * 1.8  # ceiling

# ── Agent tests ──

class TestPricingAgent:
    @pytest.mark.asyncio
    async def test_agent_with_real_product(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_001", request_id="req_001",
            input_data={
                "products": real_products[:3],
                "market_benchmarks": market_benchmarks,
            })
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["pricing_results"]) == 3
        assert result.output_data["summary"] != ""

    @pytest.mark.asyncio
    async def test_each_result_has_required_fields(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_fields", request_id="req_fields",
            input_data={
                "products": real_products[:5],
                "market_benchmarks": market_benchmarks,
            })
        result = await agent.run(inp)
        for r in result.output_data["pricing_results"]:
            assert r["product_id"] > 0
            assert r["suggested_price"] > 0
            assert r["current_price"] > 0
            assert r["strategy"] in ("penetration", "skimming", "follow", "price-up", "price-down")
            assert r["confidence"] in ("\u9ad8", "\u4e2d", "\u4f4e")
            assert len(r["reason"]) > 5
            assert r["factor_breakdown"]["cost_plus"] > 0
            print(f"  P{r['product_id']} (${r['current_price']:.2f} \u2192 ${r['suggested_price']:.2f}): "
                  f"{r['strategy']} [{r['confidence']}]")

    @pytest.mark.asyncio
    async def test_strategy_distribution(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_strat", request_id="req_strat",
            input_data={
                "products": real_products,
                "market_benchmarks": market_benchmarks,
            })
        result = await agent.run(inp)
        strats = [r["strategy"] for r in result.output_data["pricing_results"]]
        unique = set(strats)
        print(f"  Strategy distribution: {{s: strats.count(s) for s in unique}}")

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_det", request_id="req_det",
            input_data={
                "products": real_products,
                "market_benchmarks": market_benchmarks,
            })
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)
        v1 = [p["suggested_price"] for p in r1.output_data["pricing_results"]]
        v2 = [p["suggested_price"] for p in r2.output_data["pricing_results"]]
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_empty_products(self):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_empty", request_id="req_empty",
            input_data={"products": []})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["pricing_results"] == []

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_schema", request_id="req_schema",
            input_data={
                "products": [real_products[0]],
                "market_benchmarks": market_benchmarks,
            })
        result = await agent.run(inp)
        r = result.output_data["pricing_results"][0]
        parsed = PricingOutput(
            suggested_price=r["suggested_price"],
            price_change=r["price_change"],
            strategy=r["strategy"],
            confidence=r["confidence"],
            reason=r["reason"],
        )
        assert parsed.suggested_price > 0
        assert parsed.strategy in ("penetration", "skimming", "follow", "price-up", "price-down")

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products, market_benchmarks):
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_meta", request_id="req_meta",
            input_data={
                "products": real_products[:3],
                "market_benchmarks": market_benchmarks,
            })
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(PricingAgent)
        cls = AgentRegistry.get("pricing")
        assert cls is PricingAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products, market_benchmarks):
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep
        AgentRegistry.register(PricingAgent)
        plan = [PlanStep(agent="pricing",
            params={"products": real_products[:3], "market_benchmarks": market_benchmarks},
            depends_on=[])]
        executor = Executor(request_id="exec_pr")
        context = await executor.run(plan)
        assert "pricing" in context
        assert context["pricing"]["status"] == "completed"
        assert len(context["pricing"]["output_data"]["pricing_results"]) == 3

    @pytest.mark.asyncio
    async def test_context_pipeline_from_competitor(self, real_products, market_benchmarks):
        AgentRegistry.register(PricingAgent)
        pos_data = [{
            "product_id": p["id"], "rating": p["rating"]["rate"],
            "competitive_score": 60, "rating_percentile": 0.6,
            "price_percentile": 0.5, "advantages": [], "disadvantages": [], "differentiators": [],
        } for p in real_products[:4]]
        agent = PricingAgent()
        inp = AgentInput(task_id="pr_ctx", request_id="req_ctx",
            input_data={"products": real_products[:4]},
            context={"competitor_analysis": {
                "output_data": {
                    "category_benchmarks": market_benchmarks,
                    "product_positioning": pos_data,
                }}})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["pricing_results"]) == 4
        print(f"  Pipeline: {result.output_data['summary']}")

    @pytest.mark.asyncio
    async def test_margin_parameter(self, real_products, market_benchmarks):
        agent_high_margin = PricingAgent(margin=0.5)
        agent_low_margin = PricingAgent(margin=0.1)
        inp = AgentInput(task_id="pr_margin", request_id="req_margin",
            input_data={
                "products": [real_products[0]],
                "market_benchmarks": market_benchmarks,
            })
        r_high = await agent_high_margin.run(inp)
        r_low = await agent_low_margin.run(inp)
        high_price = r_high.output_data["pricing_results"][0]["suggested_price"]
        low_price = r_low.output_data["pricing_results"][0]["suggested_price"]
        assert high_price >= low_price, "Higher margin should not give lower price"
        print(f"  Margin 50%: ${high_price:.2f}, Margin 10%: ${low_price:.2f}")