"""Phase 5.3 — Dashboard API tests with real FakeStore data."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.core.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    app = create_app()
    return TestClient(app)


class TestDashboardAPI:

    def test_products_endpoint(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/products")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 20
        assert "id" in data[0] and "title" in data[0] and "price" in data[0]

    def test_price_distribution(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/price-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert sum(s["count"] for s in data) == 20  # total = 20 products

    def test_sales_trend(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/sales-trend?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 30
        assert all("day" in d and "total_sales" in d for d in data)

    def test_sales_trend_custom(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/sales-trend?days=7")
        assert resp.status_code == 200
        assert len(resp.json()) == 7

    def test_hot_ranking(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/hot-ranking?top_n=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10
        # Verify descending order
        scores = [d["composite_score"] for d in data]
        assert all(scores[i] >= scores[i+1] for i in range(len(scores)-1))

    def test_rating_scatter(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/rating-scatter")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 20
        assert all(0 <= d["rating"] <= 5 for d in data)

    def test_category_summary(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/category-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4  # 4 FakeStore categories
        assert sum(c["product_count"] for c in data) == 20
        print(f"  Categories: {[c['category'] for c in data]}")

    def test_all_endpoints_healthy(self, client: TestClient):
        """Hit all 6 dashboard endpoints and verify 200."""
        endpoints = [
            "/api/v1/dashboard/products",
            "/api/v1/dashboard/price-distribution",
            "/api/v1/dashboard/sales-trend",
            "/api/v1/dashboard/hot-ranking",
            "/api/v1/dashboard/rating-scatter",
            "/api/v1/dashboard/category-summary",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 200, f"Failed on {ep}"
        print(f"  All {len(endpoints)} endpoints OK")