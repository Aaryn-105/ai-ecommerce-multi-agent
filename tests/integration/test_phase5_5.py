# -*- coding: utf-8 -*-
"""Phase 5.5 — Product Browser API tests with real FakeStore data."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.core.database import init_db

FAKE_CATEGORIES = {"electronics", "jewelery", "men's clothing", "women's clothing"}


@pytest.fixture(scope="module")
def client():
    init_db()
    app = create_app()
    return TestClient(app)


class TestProductAPI:

    def test_fetch_all_products(self, client: TestClient):
        resp = client.get("/api/v1/dashboard/products")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 20
        print(f"  Fetched {len(data)} products")

    def test_product_schema(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        p = data[0]
        assert "id" in p and isinstance(p["id"], int)
        assert "title" in p and isinstance(p["title"], str) and len(p["title"]) > 0
        assert "price" in p and isinstance(p["price"], (int, float)) and p["price"] > 0
        assert "description" in p and isinstance(p["description"], str)
        assert "category" in p and isinstance(p["category"], str)
        assert "image" in p and p["image"].startswith("http")
        assert "rating" in p and isinstance(p["rating"], dict)
        assert "rate" in p["rating"] and "count" in p["rating"]

    def test_all_4_categories_present(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        cats = {p["category"] for p in data}
        assert cats == FAKE_CATEGORIES

    def test_category_distribution(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        from collections import Counter
        dist = Counter(p["category"] for p in data)
        print(f"  Category distribution: {dict(dist)}")
        for cat, count in dist.items():
            assert count >= 2, f"Category {cat} has only {count} products"

    def test_product_prices_range(self, client: TestClient):
        prices = [p["price"] for p in client.get("/api/v1/dashboard/products").json()]
        assert all(1 <= pr <= 1000 for pr in prices)
        avg = sum(prices) / len(prices)
        print(f"  Price range: ${min(prices):.2f} ~ ${max(prices):.2f}, avg: ${avg:.2f}")

    def test_rating_range(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        for p in data:
            assert 0 <= p["rating"]["rate"] <= 5
            assert p["rating"]["count"] >= 0

    def test_images_are_urls(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        for p in data:
            assert p["image"].startswith("https://"), f"Bad image URL"

    def test_prices_have_2_decimal_precision(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        for p in data:
            pr = p["price"]
            formatted = format(pr, ".2f")
            assert float(formatted) == pr, f"Price {pr} lacks 2-decimal precision"

    def test_electronics_products_avg_price(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        elec = [p for p in data if p["category"] == "electronics"]
        assert len(elec) > 0
        avg = sum(p["price"] for p in elec) / len(elec)
        assert 50 <= avg <= 1000, f"Electronics avg price ${avg:.2f} seems off"

    def test_avg_price_by_category(self, client: TestClient):
        data = client.get("/api/v1/dashboard/products").json()
        from collections import defaultdict
        cat_prices = defaultdict(list)
        for p in data:
            cat_prices[p["category"]].append(p["price"])
        avgs = {cat: sum(pr)/len(pr) for cat, pr in cat_prices.items()}
        for cat, avg in sorted(avgs.items(), key=lambda x: x[1], reverse=True):
            print(f"    {cat}: ${avg:.2f}")
        for cat, avg in avgs.items():
            assert 10 <= avg <= 1000, f"{cat} avg ${avg:.2f} out of range"
