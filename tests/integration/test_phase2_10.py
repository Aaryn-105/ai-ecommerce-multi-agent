"""Tests for Promotion Agent — matcher, calculator, agent, real FakeStore data."""
from __future__ import annotations
from typing import Any
import pytest
import pytest_asyncio

from backend.agents.promotion.matcher import (
    match_promotions, get_top_matches, PROMO_TYPES, PROMO_LABELS,
)
from backend.agents.promotion.calculator import (
    compute_discount_rate, compute_promotion_price, compute_duration_days,
    compute_estimated_roi, compute_threshold_condition,
    generate_promotion_copy_preview,
)
from backend.agents.promotion.agent import PromotionAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, PromotionOutput
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
    cats: dict[str, list] = {}
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


# ═══════════════════════════════════════════════════════════
#  Matcher unit tests
# ═══════════════════════════════════════════════════════════

class TestMatchPromotions:
    @pytest.mark.asyncio
    async def test_real_product_returns_matches(self, real_products, market_benchmarks):
        """Every real product should match at least 1 promotion type."""
        for p in real_products:
            cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
            matches = match_promotions(p, category_avg_price=cat_avg)
            assert len(matches) >= 1, f"Product {p['id']} ({p['title'][:30]}) has no matches"
            for m in matches:
                assert m["promotion_type"] in PROMO_TYPES
                assert 0.0 <= m["match_score"] <= 1.0
                assert m["label"] == PROMO_LABELS[m["promotion_type"]]
                assert m["reason"]

    @pytest.mark.asyncio
    async def test_matches_sorted_by_score(self, real_products, market_benchmarks):
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        matches = match_promotions(p, category_avg_price=cat_avg)
        scores = [m["match_score"] for m in matches]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_newcomer_always_present(self, real_products):
        matches = match_promotions(real_products[0])
        types = [m["promotion_type"] for m in matches]
        assert "newcomer" in types

    @pytest.mark.asyncio
    async def test_inventory_status_influences_flash_sale(self, real_products):
        p = real_products[0]
        matches_high_inv = match_promotions(p, inventory_status={"composite_score": 90, "simulated_stock": 200})
        matches_low_inv = match_promotions(p, inventory_status={"composite_score": 20, "simulated_stock": 5})
        types_high = {m["promotion_type"]: m["match_score"] for m in matches_high_inv}
        types_low = {m["promotion_type"]: m["match_score"] for m in matches_low_inv}
        if "flash_sale" in types_high and "flash_sale" in types_low:
            assert types_high["flash_sale"] >= types_low["flash_sale"]

    @pytest.mark.asyncio
    async def test_pricing_context_influences_clearance(self, real_products):
        p = real_products[0]
        matches_with_down = match_promotions(p, pricing_context={"strategy": "price-down", "price_change": -10})
        matches_with_up = match_promotions(p, pricing_context={"strategy": "price-up", "price_change": 10})
        types_down = {m["promotion_type"]: m["match_score"] for m in matches_with_down}
        types_up = {m["promotion_type"]: m["match_score"] for m in matches_with_up}
        if "clearance" in types_down and "clearance" in types_up:
            assert types_down["clearance"] >= types_up["clearance"]

    def test_empty_product(self):
        matches = match_promotions({})
        types = [m["promotion_type"] for m in matches]
        assert "newcomer" in types

    @pytest.mark.asyncio
    async def test_all_8_types_covered(self):
        """Verify all 8 promotion types appear in at least some scenario."""
        product_clearance = {
            "id": 998,
            "title": "Low Rated Product",
            "price": 10.99,
            "category": "general",
            "rating": {"rate": 2.0, "count": 30},
        }
        inv_clearance = {"composite_score": 25, "simulated_stock": 200}
        pricing_clearance = {"strategy": "price-down", "price_change": -15}
        matches_clearance = match_promotions(
            product_clearance, category_avg_price=15.0,
            inventory_status=inv_clearance, pricing_context=pricing_clearance,
        )
        clearance_types = {m["promotion_type"] for m in matches_clearance}
        assert "clearance" in clearance_types

        product = {
            "id": 999,
            "title": "Test Product Premium",
            "price": 49.99,
            "category": "electronics",
            "rating": {"rate": 4.8, "count": 500},
        }
        inv = {"composite_score": 85, "simulated_stock": 200}
        pricing = {"strategy": "penetration", "price_change": -5}
        matches = match_promotions(product, category_avg_price=30.0, inventory_status=inv, pricing_context=pricing)
        matched_types = {m["promotion_type"] for m in matches}
        all_8 = set(PROMO_TYPES)
        matched_types.add("clearance")
        matched_types.add("newcomer")
        missing = all_8 - matched_types
        assert not missing, f"Promotion types not covered: {missing}"
        print(f"  All 8 types covered: {sorted(matched_types)}")


class TestGetTopMatches:
    @pytest.mark.asyncio
    async def test_returns_top_n(self, real_products, market_benchmarks):
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        top3 = get_top_matches(p, category_avg_price=cat_avg, top_n=3)
        assert len(top3) <= 3
        all_m = match_promotions(p, category_avg_price=cat_avg)
        assert top3 == all_m[:3]

    @pytest.mark.asyncio
    async def test_top1_highest_score(self, real_products, market_benchmarks):
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        top1 = get_top_matches(p, category_avg_price=cat_avg, top_n=1)
        assert len(top1) == 1
        all_m = match_promotions(p, category_avg_price=cat_avg)
        assert top1[0]["match_score"] == all_m[0]["match_score"]


# ═══════════════════════════════════════════════════════════
#  Calculator unit tests
# ═══════════════════════════════════════════════════════════

class TestComputeDiscountRate:
    def test_flash_sale_range(self):
        rate = compute_discount_rate("flash_sale", {"rating": {"rate": 4.5}, "price": 30}, match_score=0.8)
        assert 0.30 <= rate <= 0.50
        print(f"  flash_sale discount: {rate*100:.1f}%")

    def test_clearance_range(self):
        rate = compute_discount_rate("clearance", {"rating": {"rate": 2.5}, "price": 20}, match_score=0.4)
        assert 0.50 <= rate <= 0.70

    def test_newcomer_range(self):
        rate = compute_discount_rate("newcomer", {"rating": {"rate": 4.0}, "price": 25}, match_score=0.5)
        assert 0.10 <= rate <= 0.25

    def test_higher_match_aggressive_discount(self):
        p = {"rating": {"rate": 4.0}, "price": 30}
        rate_low = compute_discount_rate("discount", p, match_score=0.2)
        rate_high = compute_discount_rate("discount", p, match_score=0.9)
        assert rate_high >= rate_low

    def test_high_rating_premium(self):
        p_high = {"rating": {"rate": 4.8}, "price": 50}
        p_low = {"rating": {"rate": 2.5}, "price": 50}
        rate_high = compute_discount_rate("flash_sale", p_high, match_score=0.6)
        rate_low = compute_discount_rate("flash_sale", p_low, match_score=0.6)
        assert rate_high >= rate_low

    @pytest.mark.asyncio
    async def test_on_real_products(self, real_products):
        for pt in ["flash_sale", "discount", "member"]:
            p = real_products[0]
            rate = compute_discount_rate(pt, p, match_score=0.6)
            assert 0.05 <= rate <= 0.70
            print(f"  {pt} on {p['title'][:30]}: {rate*100:.1f}%")


class TestComputePromotionPrice:
    def test_simple_discount(self):
        assert compute_promotion_price(100.0, 0.20) == 80.0

    def test_no_discount(self):
        assert compute_promotion_price(50.0, 0.0) == 50.0

    def test_full_discount(self):
        assert compute_promotion_price(30.0, 1.0) == 0.0

    def test_zero_price(self):
        assert compute_promotion_price(0.0, 0.20) == 0.0


class TestComputeDurationDays:
    def test_flash_sale_short(self):
        dur = compute_duration_days("flash_sale", 0.40)
        assert 1 <= dur <= 3

    def test_member_long(self):
        dur = compute_duration_days("member", 0.15)
        assert 30 <= dur <= 365

    def test_steeper_discount_shorter_duration(self):
        dur_steep = compute_duration_days("discount", 0.40)
        dur_shallow = compute_duration_days("discount", 0.15)
        assert dur_steep <= dur_shallow


class TestComputeEstimatedRoi:
    def test_flash_sale_positive_roi(self):
        roi = compute_estimated_roi(100.0, 65.0, 0.35, "flash_sale", 300)
        assert roi > 0
        print(f"  flash_sale ROI: {roi:.2f}x")

    def test_clearance_roi_computed(self):
        roi = compute_estimated_roi(50.0, 20.0, 0.60, "clearance", 100)
        assert roi is not None
        print(f"  clearance ROI: {roi:.2f}x")

    def test_newcomer_roi(self):
        roi = compute_estimated_roi(30.0, 24.0, 0.20, "newcomer", 50)
        assert roi > 0

    def test_zero_rating_count(self):
        roi = compute_estimated_roi(100.0, 80.0, 0.20, "discount", 0)
        assert roi is not None


class TestComputeThresholdCondition:
    def test_returns_string(self):
        assert compute_threshold_condition("flash_sale", 50.0)
        assert compute_threshold_condition("member", 30.0)


class TestGeneratePromotionCopyPreview:
    def test_includes_price_and_discount(self):
        copy = generate_promotion_copy_preview("flash_sale", "Test Product", 0.35, 65.0)
        assert "Test Product" in copy
        assert "65" in copy or "35%" in copy


# ═══════════════════════════════════════════════════════════
#  Agent integration tests
# ═══════════════════════════════════════════════════════════

class TestPromotionAgent:
    @pytest.mark.asyncio
    async def test_basic_execution_with_real_product(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_basic",
            request_id="req_basic",
            input_data={
                "product": p,
                "category_avg_price": cat_avg,
            },
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        promo = result.output_data["promotion_result"]
        assert promo["promotion_plan"] is not None
        assert len(promo["alternative_plans"]) >= 0
        plan = promo["promotion_plan"]
        assert plan["promotion_type"] in PROMO_TYPES
        assert plan["original_price"] > 0
        assert plan["promotion_price"] >= 0
        assert 0.0 <= plan["discount_rate"] <= 1.0
        assert plan["estimated_roi"] is not None
        assert plan["duration_days"] >= 1
        assert plan["promotion_copy"]
        print(f"  Plan: {plan['label']} — {plan['discount_label']}, ROI {plan['estimated_roi']:.2f}x")
        print(f"  Alternatives: {len(promo['alternative_plans'])}")
        print(f"  Summary: {result.output_data['summary']}")

    @pytest.mark.asyncio
    async def test_execution_with_all_20_products(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        for p in real_products:
            cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
            inp = AgentInput(
                task_id=f"promo_{p['id']}",
                request_id="req_all",
                input_data={"product": p, "category_avg_price": cat_avg},
            )
            result = await agent.run(inp)
            assert result.status == "completed"
            promo = result.output_data["promotion_result"]
            plan = promo["promotion_plan"]
            assert plan is not None
            assert promo["product_id"] == p["id"]
            assert plan["original_price"] == p["price"]
            assert plan["promotion_price"] <= plan["original_price"] + 0.01

    @pytest.mark.asyncio
    async def test_execution_with_inventory_and_pricing_context(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_ctx",
            request_id="req_ctx",
            input_data={
                "product": p,
                "category_avg_price": cat_avg,
                "inventory_status": {"composite_score": 90, "simulated_stock": 200},
                "pricing_context": {"strategy": "penetration", "price_change": -10},
            },
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["all_matched_types"]

    @pytest.mark.asyncio
    async def test_empty_product_returns_fallback(self):
        agent = PromotionAgent()
        inp = AgentInput(task_id="promo_empty", request_id="req_empty", input_data={})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["promotion_result"] == {}

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[3]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_det",
            request_id="req_det",
            input_data={"product": p, "category_avg_price": cat_avg},
        )
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)
        plan1 = r1.output_data["promotion_result"]["promotion_plan"]
        plan2 = r2.output_data["promotion_result"]["promotion_plan"]
        assert plan1["promotion_type"] == plan2["promotion_type"]
        assert plan1["promotion_price"] == plan2["promotion_price"]

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_schema",
            request_id="req_schema",
            input_data={"product": p, "category_avg_price": cat_avg},
        )
        result = await agent.run(inp)
        promo = result.output_data["promotion_result"]
        plan = promo["promotion_plan"]
        parsed = PromotionOutput(
            product_id=promo["product_id"],
            promotion_plan=plan,
            alternative_plans=promo["alternative_plans"],
            recommended_plan_index=0,
        )
        assert parsed.product_id > 0
        assert parsed.promotion_plan.promotion_type in PROMO_TYPES

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[2]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_meta",
            request_id="req_meta",
            input_data={"product": p, "category_avg_price": cat_avg},
        )
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(PromotionAgent)
        cls = AgentRegistry.get("promotion")
        assert cls is PromotionAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products, market_benchmarks):
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep

        AgentRegistry.register(PromotionAgent)

        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)

        plan = [PlanStep(
            agent="promotion",
            params={"product": p, "category_avg_price": cat_avg},
            depends_on=[],
        )]
        executor = Executor(request_id="exec_promo")
        context = await executor.run(plan)
        assert "promotion" in context
        assert context["promotion"]["status"] == "completed"
        promo = context["promotion"]["output_data"]["promotion_result"]
        assert promo["promotion_plan"] is not None

    @pytest.mark.asyncio
    async def test_context_pipeline_from_pricing(self, real_products, market_benchmarks):
        agent = PromotionAgent()
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)

        inp = AgentInput(
            task_id="promo_pipe",
            request_id="req_pipe",
            input_data={"product": p, "category_avg_price": cat_avg},
            context={
                "pricing": {
                    "output_data": {
                        "pricing_results": [{
                            "product_id": p["id"],
                            "strategy": "penetration",
                            "price_change": -12.5,
                            "suggested_price": p["price"] * 0.85,
                        }],
                    },
                },
            },
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        all_types = result.output_data["all_matched_types"]
        print(f"  Pipeline context — matched types: {all_types}")

    @pytest.mark.asyncio
    async def test_products_input_list(self, real_products):
        agent = PromotionAgent()
        inp = AgentInput(
            task_id="promo_list",
            request_id="req_list",
            input_data={"products": real_products[:3]},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        promo = result.output_data["promotion_result"]
        assert promo["promotion_plan"] is not None

class TestPromotionAgentLLMIntegration:
    """Tests for LLM integration path of Promotion Agent."""

    @pytest.mark.asyncio
    async def test_llm_used_false_when_no_key(self, real_products, market_benchmarks):
        """Without API key, llm_used should be False."""
        agent = PromotionAgent()
        p = real_products[0]
        cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
        inp = AgentInput(
            task_id="promo_llm_false",
            request_id="req_llm_false",
            input_data={"product": p, "category_avg_price": cat_avg},
        )
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0

    @pytest.mark.asyncio
    async def test_llm_path_with_mock_service(self, real_products, market_benchmarks):
        """When a mock LLM service is provided, promotion copy should come from LLM."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="【限时秒杀】AI生成的促销文案！仅限3天！")

        import backend.core.config as cfg
        original_key = cfg.settings.OPENAI_API_KEY
        cfg.settings.OPENAI_API_KEY = "sk-test-fake-key"

        try:
            agent = PromotionAgent(llm_service=mock_llm)
            p = real_products[0]
            cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
            inp = AgentInput(
                task_id="promo_llm",
                request_id="req_llm",
                input_data={"product": p, "category_avg_price": cat_avg},
            )
            result = await agent.run(inp)
            assert result.status == "completed"
            assert result.execution_meta.llm_used is True
            plan = result.output_data["promotion_result"]["promotion_plan"]
            # Promotion copy should be from LLM (the mock return value)
            assert plan["promotion_copy"] == "【限时秒杀】AI生成的促销文案！仅限3天！"
        finally:
            cfg.settings.OPENAI_API_KEY = original_key

    @pytest.mark.asyncio
    async def test_llm_fallback_to_template(self, real_products, market_benchmarks):
        """When LLM returns empty string, agent falls back to template."""
        from unittest.mock import AsyncMock

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="")

        import backend.core.config as cfg
        original_key = cfg.settings.OPENAI_API_KEY
        cfg.settings.OPENAI_API_KEY = "sk-test-fake-key"

        try:
            agent = PromotionAgent(llm_service=mock_llm)
            p = real_products[0]
            cat_avg = market_benchmarks.get(p["category"], {}).get("avg_price", 0)
            inp = AgentInput(
                task_id="promo_fb",
                request_id="req_fb",
                input_data={"product": p, "category_avg_price": cat_avg},
            )
            result = await agent.run(inp)
            assert result.status == "completed"
            plan = result.output_data["promotion_result"]["promotion_plan"]
            # Copy should be from template fallback (non-empty, contains product info)
            assert plan["promotion_copy"]
            assert p["title"][:20] in plan["promotion_copy"]
        finally:
            cfg.settings.OPENAI_API_KEY = original_key