"""Phase 1 tests backed by real FakeStore API data."""
from __future__ import annotations

import pytest
import pytest_asyncio

from backend.core.config import settings
from backend.core.database import engine, init_db
from backend.services.fake_store import FakeStoreService
from backend.services.data_generator import (
    generate_sales_history,
    simulate_stock_and_reorder,
    estimate_weekly_sales,
    estimate_sales_velocity,
)
from backend.models.schemas import (
    ChatRequest,
    ProductRaw,
    ProductAnalysisInput,
    AgentInput,
    PlanStep,
    SharedState,
    Rating,
    ProductAnalysisOutput,
)


# ── Real-data fixture ─────────────────────────────────────

_REAL_PRODUCTS: list[dict] | None = None


@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    """One-time fetch from FakeStore API, cached for the whole session."""
    global _REAL_PRODUCTS
    if _REAL_PRODUCTS is not None:
        return _REAL_PRODUCTS

    svc = FakeStoreService()
    try:
        _REAL_PRODUCTS = await svc.get_all_products()
    finally:
        await svc.close()

    assert len(_REAL_PRODUCTS) == 20, (
        f"Expected 20 products from API, got {len(_REAL_PRODUCTS)}"
    )
    return _REAL_PRODUCTS


# ── FakeStoreService integration ──────────────────────────

@pytest.mark.asyncio
class TestFakeStoreConnection:
    async def test_fetches_20_products(self, real_products):
        assert len(real_products) == 20

    async def test_product_has_required_fields(self, real_products):
        for p in real_products:
            assert "id" in p
            assert "title" in p
            assert "price" in p
            assert "category" in p
            assert "rating" in p
            assert "rate" in p["rating"]
            assert "count" in p["rating"]

    async def test_categories_are_real(self, real_products):
        cats = {p["category"] for p in real_products}
        expected = {"electronics", "jewelery", "men's clothing", "women's clothing"}
        assert cats == expected, f"Got categories: {cats}"

    async def test_prices_are_positive(self, real_products):
        assert all(p["price"] > 0 for p in real_products)

    async def test_rating_ranges_are_valid(self, real_products):
        for p in real_products:
            assert 0 <= p["rating"]["rate"] <= 5
            assert p["rating"]["count"] >= 0


# ── Schema parsing with real data ─────────────────────────

@pytest.mark.asyncio
class TestSchemaWithRealData:
    async def test_parse_all_products_as_product_raw(self, real_products):
        """Verify every real API product can be parsed by our Pydantic schema."""
        parsed = [ProductRaw.model_validate(p) for p in real_products]
        assert len(parsed) == 20
        assert all(isinstance(p, ProductRaw) for p in parsed)

    async def test_product_analysis_input_from_real_data(self, real_products):
        """Feed 20 real products into the ProductAnalysisInput schema."""
        parsed_products = [ProductRaw.model_validate(p) for p in real_products]
        inp = ProductAnalysisInput(products=parsed_products)
        assert len(inp.products) == 20
        # Verify unique product IDs are preserved
        ids = {p.id for p in inp.products}
        assert len(ids) == 20

    async def test_rating_distribution(self, real_products):
        """Check real rating distribution from API."""
        rates = [p["rating"]["rate"] for p in real_products]
        counts = [p["rating"]["count"] for p in real_products]
        print(f"  Rate range: {min(rates):.1f} - {max(rates):.1f}")
        print(f"  Count range: {min(counts)} - {max(counts)}")
        assert min(rates) >= 1.0  # all products have some rating
        assert max(rates) <= 5.0
        assert min(counts) >= 0
        assert max(counts) > 0

    async def test_category_distribution(self, real_products):
        cats = {}
        for p in real_products:
            c = p["category"]
            cats[c] = cats.get(c, 0) + 1
        print(f"  Category distribution: {cats}")
        assert all(v >= 2 for v in cats.values())  # each category has >= 2 products


# ── DataGenerator driven by real API values ───────────────

@pytest.mark.asyncio
class TestDataGeneratorWithRealData:
    async def test_sales_from_real_rating_count(self, real_products):
        """Use the first product's actual rating.count as seed for sales history."""
        p1 = real_products[0]
        real_count = p1["rating"]["count"]
        sales = generate_sales_history(p1["id"], real_count, days=90, seed=42)
        assert len(sales) == 90
        assert all(s["date"] for s in sales)
        assert all(s["units"] >= 0 for s in sales)
        print(f"  Product 1 (rating.count={real_count}): 90-day sales generated")

    async def test_sales_from_lowest_popularity(self, real_products):
        """Use the product with the lowest rating.count."""
        least_popular = min(real_products, key=lambda p: p["rating"]["count"])
        low_count = least_popular["rating"]["count"]
        sales = generate_sales_history(least_popular["id"], low_count, days=30, seed=0)
        assert len(sales) == 30
        print(f"  Least popular (rating.count={low_count}): {sales[:3]}...")

    async def test_sales_from_highest_popularity(self, real_products):
        """Use the product with the highest rating.count."""
        most_popular = max(real_products, key=lambda p: p["rating"]["count"])
        high_count = most_popular["rating"]["count"]
        sales = generate_sales_history(most_popular["id"], high_count, days=30, seed=0)
        assert len(sales) == 30
        print(f"  Most popular (rating.count={high_count}): {sales[:3]}...")

    async def test_stock_from_real_products(self, real_products):
        """Generate stock/reorder data for the first 5 real products."""
        for p in real_products[:5]:
            result = simulate_stock_and_reorder(p["rating"]["count"])
            print(
                f"  Product {p['id']} ({p['title'][:30]}...): "
                f"stock={result['simulated_stock']}, "
                f"reorder={result['simulated_reorder_point']}"
            )
            assert result["simulated_stock"] >= 5
            assert result["simulated_reorder_point"] >= 15

    async def test_weekly_sales_from_real_data(self, real_products):
        for p in real_products[:3]:
            ws = estimate_weekly_sales(p["rating"]["count"])
            expected = p["rating"]["count"] / 52.0
            print(
                f"  Product {p['id']}: rating.count={p['rating']['count']}, "
                f"weekly_sales={ws:.2f} (expected={expected:.2f})"
            )
            assert ws == pytest.approx(expected, rel=0.01)

    async def test_sales_velocity_across_all_products(self, real_products):
        counts = [p["rating"]["count"] for p in real_products]
        max_count = max(counts)
        for p in real_products[:5]:
            vel = estimate_sales_velocity(p["rating"]["count"], max_count)
            assert 0.0 <= vel <= 1.0
            print(
                f"  Product {p['id']}: count={p['rating']['count']}, "
                f"max={max_count}, velocity={vel:.3f}"
            )


# ── Static schema tests (independent of API) ──────────────

class TestStaticSchemas:
    def test_chat_request_defaults(self):
        req = ChatRequest(message="帮我分析电子产品")
        assert req.message == "帮我分析电子产品"
        assert req.conversation_id is None

    def test_agent_input_defaults(self):
        inp = AgentInput(task_id="t1", request_id="r1")
        assert inp.status == "pending"
        assert inp.input_data == {}

    def test_plan_step(self):
        step = PlanStep(
            agent="pricing",
            params={"product_id": 1},
            depends_on=["selection"],
        )
        assert step.agent == "pricing"
        assert step.depends_on == ["selection"]

    def test_shared_state_defaults(self):
        state = SharedState()
        assert state.query == ""
        assert state.plan_steps == []
        assert state.current_step_index == 0


# ── DB init (real SQLite) ─────────────────────────────────

class TestDatabaseInit:
    def test_init_db_creates_tables(self):
        """Verify SQLite DB can be created and tables exist."""
        import os, gc

        init_db()
        db_path = settings.SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
        assert os.path.exists(db_path), f"DB not found at {db_path}"

        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "conversations" in tables
        assert "reports" in tables

        # Release all engine resources before deleting the file
        engine.dispose()
        gc.collect()
        os.remove(db_path)
        print(f"  DB created at {db_path}, tables: {tables}")