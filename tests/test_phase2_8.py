"""Tests for Inventory \u2014 scoring models and agent, driven by real FakeStore data."""
from __future__ import annotations
from typing import Any
import pytest
import pytest_asyncio
from backend.agents.inventory.models import (
    compute_sales_velocity, compute_stock_health, compute_urgency,
    compute_turnover_rate, compute_eoq, compute_safety_stock, score_inventory)
from backend.agents.inventory.agent import InventoryAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, InventoryOutput
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

@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()

# ── Model unit tests ──

class TestComputeSalesVelocity:
    def test_max_count_returns_one(self):
        assert compute_sales_velocity(100, 100) == 1.0

    def test_zero_count_returns_zero(self):
        assert compute_sales_velocity(0, 100) == 0.0

    def test_half_count(self):
        assert compute_sales_velocity(50, 100) == 0.5

    def test_zero_max(self):
        assert compute_sales_velocity(100, 0) == 0.0

    @pytest.mark.asyncio
    async def test_from_real_data(self, real_products):
        counts = [p["rating"]["count"] for p in real_products]
        max_c = max(counts)
        for p in real_products[:3]:
            v = compute_sales_velocity(p["rating"]["count"], max_c)
            assert 0 <= v <= 1
            print(f"  {p['title'][:20]}: velocity={v:.3f}")

class TestComputeStockHealth:
    def test_full_stock(self):
        assert compute_stock_health(300, 100) == 1.0  # 3x reorder → capped at 1

    def test_at_reorder_point(self):
        h = compute_stock_health(100, 100)
        assert 0.3 < h < 0.35  # 100/100 = 1.0 / 3 = 0.333

    def test_zero_stock(self):
        assert compute_stock_health(0, 100) == 0.0

    def test_zero_reorder(self):
        assert compute_stock_health(50, 0) == 1.0

class TestComputeUrgency:
    def test_critical_stock(self):
        assert compute_urgency(0, 100) == 1.0

    def test_safe_stock(self):
        assert compute_urgency(200, 100) == 0.0  # 2x reorder → safe

    def test_mid_stock(self):
        u = compute_urgency(50, 100)
        assert 0 < u < 1

    def test_zero_reorder(self):
        assert compute_urgency(0, 0) == 0.0

class TestComputeTurnoverRate:
    def test_same_as_sales_velocity(self):
        assert compute_turnover_rate(100, 200) == compute_sales_velocity(100, 200)

class TestComputeEOQ:
    def test_basic_eoq(self):
        eoq = compute_eoq(1000, 10.0)
        assert eoq > 0
        print(f"  EOQ for D=1000, P=$10: {eoq}")

    def test_zero_demand(self):
        assert compute_eoq(0, 10.0) == 1

    def test_zero_price(self):
        assert compute_eoq(1000, 0) == 1

    def test_high_demand(self):
        eoq = compute_eoq(10000, 5.0)
        assert eoq > 10

class TestComputeSafetyStock:
    def test_basic(self):
        ss = compute_safety_stock(50, 20, lead_time=7)
        assert ss > 0
        print(f"  Safety stock: {ss}")

    def test_no_variability(self):
        assert compute_safety_stock(20, 20, lead_time=7) == 0

    def test_zero_lead_time(self):
        assert compute_safety_stock(50, 20, lead_time=0) == 0

class TestScoreInventory:
    @pytest.mark.asyncio
    async def test_real_products_have_all_scores(self, real_products):
        max_count = max(p["rating"]["count"] for p in real_products)
        for p in real_products[:5]:
            result = score_inventory(p, max_count)
            assert result["product_id"] == p["id"]
            assert 0 <= result["sales_velocity_score"] <= 1
            assert 0 <= result["stock_health_score"] <= 1
            assert 0 <= result["replenishment_urgency_score"] <= 1
            assert 0 <= result["turnover_rate_score"] <= 1
            assert 0 <= result["composite_score"] <= 100
            assert result["eoq"] > 0
            assert result["suggested_reorder_qty"] > 0
            assert result["priority"] in (1, 2, 3, 4, 5)
            print(f"  P{p['id']} ({p['title'][:20]}): score={result['composite_score']:.1f}, "
                  f"action={result['suggested_action']}")

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products):
        max_count = max(p["rating"]["count"] for p in real_products)
        r1 = [score_inventory(p, max_count)["composite_score"] for p in real_products]
        r2 = [score_inventory(p, max_count)["composite_score"] for p in real_products]
        assert r1 == r2

# ── Agent tests ──

class TestInventoryAgent:
    @pytest.mark.asyncio
    async def test_agent_with_real_products(self, real_products):
        agent = InventoryAgent(top_n=20)
        inp = AgentInput(task_id="inv_001", request_id="req_001",
            input_data={"products": real_products})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["replenishment_plans"]) == 20
        assert result.output_data["overall_summary"]["total_order_value"] > 0

    @pytest.mark.asyncio
    async def test_each_plan_has_required_fields(self, real_products):
        agent = InventoryAgent(top_n=20)
        inp = AgentInput(task_id="inv_fields", request_id="req_fields",
            input_data={"products": real_products})
        result = await agent.run(inp)
        for plan in result.output_data["replenishment_plans"]:
            assert plan["product_id"] > 0
            assert plan["title"] != ""
            assert plan["suggested_reorder_qty"] > 0
            assert plan["suggested_action"] != ""
            assert 1 <= plan["priority"] <= 5
            assert 0 <= plan["composite_score"] <= 100

    @pytest.mark.asyncio
    async def test_urgency_distribution(self, real_products):
        agent = InventoryAgent(top_n=20)
        inp = AgentInput(task_id="inv_urg", request_id="req_urg",
            input_data={"products": real_products})
        result = await agent.run(inp)
        s = result.output_data["overall_summary"]
        total = s["urgent_count"] + s["normal_count"] + s["no_action_count"]
        assert total == 20
        print(f"  Urgent={s['urgent_count']}, Normal={s['normal_count']}, "
              f"NoAction={s['no_action_count']}, Value=${s['total_order_value']:.2f}")

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products):
        agent = InventoryAgent(top_n=20)
        inp = AgentInput(task_id="inv_det", request_id="req_det",
            input_data={"products": real_products})
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)
        s1 = [p["composite_score"] for p in r1.output_data["replenishment_plans"]]
        s2 = [p["composite_score"] for p in r2.output_data["replenishment_plans"]]
        assert s1 == s2

    @pytest.mark.asyncio
    async def test_top_n_filtering(self, real_products):
        for n in [5, 10, 20]:
            agent = InventoryAgent(top_n=n)
            inp = AgentInput(task_id=f"inv_top{n}", request_id=f"req_top{n}",
                input_data={"products": real_products})
            result = await agent.run(inp)
            assert len(result.output_data["replenishment_plans"]) == n

    @pytest.mark.asyncio
    async def test_empty_products(self):
        agent = InventoryAgent()
        inp = AgentInput(task_id="inv_empty", request_id="req_empty",
            input_data={"products": []})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["replenishment_plans"] == []

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products):
        agent = InventoryAgent(top_n=5)
        inp = AgentInput(task_id="inv_schema", request_id="req_schema",
            input_data={"products": real_products})
        result = await agent.run(inp)
        parsed = InventoryOutput.model_validate(result.output_data)
        assert len(parsed.replenishment_plans) == 5
        assert parsed.overall_summary.total_order_value > 0

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products):
        agent = InventoryAgent(top_n=5)
        inp = AgentInput(task_id="inv_meta", request_id="req_meta",
            input_data={"products": real_products})
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(InventoryAgent)
        cls = AgentRegistry.get("inventory")
        assert cls is InventoryAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products):
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep
        AgentRegistry.register(InventoryAgent)
        plan = [PlanStep(agent="inventory", params={"products": real_products}, depends_on=[])]
        executor = Executor(request_id="exec_inv")
        context = await executor.run(plan)
        assert "inventory" in context
        assert context["inventory"]["status"] == "completed"
        assert len(context["inventory"]["output_data"]["replenishment_plans"]) == 20

    @pytest.mark.asyncio
    async def test_context_pipeline_from_product_analysis(self, real_products):
        """Simulate pipeline: product_analysis -> inventory."""
        AgentRegistry.register(InventoryAgent)
        selected = [{"id": p["id"], "title": p["title"], "category": p["category"],
                     "price": p["price"], "rating": p["rating"]}
                    for p in real_products[:6]]
        agent = InventoryAgent(top_n=6)
        inp = AgentInput(task_id="inv_ctx", request_id="req_ctx",
            input_data={},
            context={"product_analysis": {"output_data": {"selected_products": selected}}})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["replenishment_plans"]) == 6
        print(f"  Pipeline summary: {result.output_data.get('summary', '')}")