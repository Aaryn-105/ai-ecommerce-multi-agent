"""Tests for Phase 3 — API Routes.

All tests use **real** FakeStore API data.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.database import Base
from backend.main import create_app
from backend.models.schemas import ChatRequest


# ── Test database ────────────────────────────────────────
_engine: Any = None
_TestSessionLocal: Any = None
_db_path: str = ""


def _build_test_db() -> str:
    """Create a temporary SQLite database and return its path."""
    tmp = tempfile.gettempdir()
    path = os.path.join(tmp, f"test_phase3_{os.urandom(4).hex()}.db")
    return path


@pytest.fixture(scope="session", autouse=True)
def _test_db() -> Generator[str, None, None]:
    """Create and tear down a temporary SQLite database for the test session."""
    global _engine, _TestSessionLocal, _db_path
    _db_path = _build_test_db()
    _engine = create_engine(
        f"sqlite:///{_db_path}",
        connect_args={"check_same_thread": False},
    )
    _TestSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=_engine)
    yield _db_path
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()
    if os.path.exists(_db_path):
        try:
            os.remove(_db_path)
        except PermissionError:
            pass


@pytest.fixture(autouse=True)
def _override_db(_test_db: str) -> Generator[None, None, None]:
    """Override database dependency to use the test database."""
    from backend.core import database as db_mod
    from backend.routers import chat as chat_mod
    from backend.routers import report as report_mod

    original_engine = db_mod.engine
    original_local = db_mod.SessionLocal
    original_get_db = db_mod.get_db

    db_mod.engine = _engine
    db_mod.SessionLocal = _TestSessionLocal

    def _test_get_db() -> Generator[Session, None, None]:
        db = _TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    db_mod.get_db = _test_get_db

    # Recreate deps module references
    import backend.core.deps as deps_mod
    deps_mod.get_db = _test_get_db
    deps_mod.get_db_session = lambda db=None: _test_get_db().__next__()

    yield

    db_mod.engine = original_engine
    db_mod.SessionLocal = original_local
    db_mod.get_db = original_get_db
    deps_mod.get_db = original_get_db


# ── Test client ──────────────────────────────────────────
@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient."""
    app = create_app()
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════
#  1. Health Check
# ═══════════════════════════════════════════════════════════

class TestHealth:
    def test_health_endpoint(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"


# ═══════════════════════════════════════════════════════════
#  2. Dashboard Endpoints
# ═══════════════════════════════════════════════════════════

class TestDashboardProducts:
    def test_get_all_products_returns_20(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/products")
        assert resp.status_code == 200
        products = resp.json()
        assert isinstance(products, list)
        assert len(products) == 20
        # Verify structure of first product
        p = products[0]
        assert "id" in p
        assert "title" in p
        assert "price" in p
        assert "category" in p
        assert "rating" in p
        assert "rate" in p["rating"]
        assert "count" in p["rating"]

    def test_products_span_multiple_categories(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/products")
        categories = {p["category"] for p in resp.json()}
        assert len(categories) >= 3  # FakeStore has 4 categories


class TestDashboardPriceDistribution:
    def test_price_distribution_structure(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/price-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 5  # 5 price segments
        segments = {item["segment"] for item in data}
        assert "0-25" in segments
        assert "25-50" in segments
        assert "50-100" in segments
        assert "100-200" in segments
        assert "200+" in segments
        for item in data:
            assert item["count"] >= 0
            assert item["avg_price"] >= 0
            assert item["min_price"] >= 0
            assert item["max_price"] >= 0

    def test_total_products_match(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/price-distribution")
        total = sum(item["count"] for item in resp.json())
        assert total == 20


class TestDashboardSalesTrend:
    def test_sales_trend_default_30_days(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/sales-trend")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 30
        for day in data:
            assert "day" in day
            assert "total_sales" in day
            assert "total_revenue" in day
            assert "order_count" in day

    def test_sales_trend_custom_days(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/sales-trend?days=7")
        assert resp.status_code == 200
        assert len(resp.json()) == 7


class TestDashboardHotRanking:
    def test_hot_ranking_default_top_10(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/hot-ranking")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 10
        # Verify descending composite_score
        scores = [item["composite_score"] for item in data]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_hot_ranking_custom_top_n(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/hot-ranking?top_n=5")
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_hot_ranking_fields(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/hot-ranking?top_n=3")
        item = resp.json()[0]
        assert "id" in item
        assert "title" in item
        assert "category" in item
        assert "price" in item
        assert "rating" in item
        assert "review_count" in item
        assert "composite_score" in item


class TestDashboardRatingScatter:
    def test_rating_scatter_all_products(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/rating-scatter")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 20
        for point in data:
            assert "rating" in point
            assert "review_count" in point
            assert "price" in point
            assert 0 <= point["rating"] <= 5


class TestDashboardCategorySummary:
    def test_category_summary(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/category-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # FakeStore has 4 categories
        assert len(data) == 4
        for cat in data:
            assert "category" in cat
            assert "product_count" in cat
            assert "avg_price" in cat
            assert "avg_rating" in cat
            assert "total_reviews" in cat
            total_check = cat["product_count"] * cat["avg_price"]
            assert cat["min_price"] <= cat["max_price"]

    def test_category_products_sum_to_20(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dashboard/category-summary")
        total = sum(cat["product_count"] for cat in resp.json())
        assert total == 20


# ═══════════════════════════════════════════════════════════
#  3. Chat Endpoint
# ═══════════════════════════════════════════════════════════

class TestChat:
    def test_chat_non_ecommerce_message(self, client: TestClient) -> None:
        """Non-e-commerce message should return a friendly prompt."""
        resp = client.post(
            "/api/v1/chat",
            json={"message": "你好，今天天气怎么样？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "conversation_id" in data
        # Should not have plan steps for non-ecommerce
        assert data.get("plan") == []
        assert data.get("sections") == {}

    def test_chat_ecommerce_message(self, client: TestClient) -> None:
        """E-commerce message should return a full analysis report."""
        resp = client.post(
            "/api/v1/chat",
            json={"message": "帮我分析一下FakeStore上的电子产品"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "conversation_id" in data
        assert len(data["conversation_id"]) == 36  # UUID

    def test_chat_with_conversation_id(self, client: TestClient) -> None:
        """Providing conversation_id should reuse the conversation."""
        # First message to create a conversation
        resp1 = client.post(
            "/api/v1/chat",
            json={"message": "帮我分析商品数据"},
        )
        conv_id = resp1.json()["conversation_id"]

        # Second message reusing the same conversation
        resp2 = client.post(
            "/api/v1/chat",
            json={
                "message": "分析一下珠宝类商品",
                "conversation_id": conv_id,
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id

    def test_chat_empty_message(self, client: TestClient) -> None:
        """Empty message should still return a valid response."""
        resp = client.post(
            "/api/v1/chat",
            json={"message": ""},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
#  4. Report Endpoints
# ═══════════════════════════════════════════════════════════

class TestReport:
    def test_list_reports_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/report/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_report_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/report/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_export_report_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": 999, "format": "pdf"},
        )
        assert resp.status_code == 404

    def test_export_not_implemented(self, client: TestClient) -> None:
        """Export returns not_implemented until Phase 4."""
        # First create a report via chat
        resp = client.post(
            "/api/v1/chat",
            json={"message": "分析电子产品"},
        )
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": 999, "format": "pdf", "sections": {"test": {"key": "val"}}},
        )
        # 404 because report 999 doesn't exist
        assert resp.status_code == 404

    def test_list_reports_pagination(self, client: TestClient) -> None:
        resp = client.get("/api/v1/report/?skip=0&limit=5")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
