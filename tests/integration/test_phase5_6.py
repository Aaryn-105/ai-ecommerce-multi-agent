# -*- coding: utf-8 -*-
"""Phase 5.6 - System Integration E2E Tests."""
from __future__ import annotations
import math, time, os, asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import pytest, pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.core.database import init_db
from backend.services.fake_store import FakeStoreService
from backend.models.schemas import ChatResponse

FAKE_CATS = {"electronics","jewelery","men's clothing","women's clothing"}
E2E_Q = ["电子产品选品","女装趋势预测","珠宝定价策略","男装库存管理"]
_RP = None

@pytest_asyncio.fixture(scope="session")
async def real_products():
    global _RP
    if _RP: return _RP
    svc = FakeStoreService()
    try: _RP = await svc.get_all_products()
    finally: await svc.close()
    assert len(_RP) == 20
    return _RP

@pytest_asyncio.fixture
async def app():
    init_db(); return create_app()
class TestViteProxy:
    def test_vite_proxy_config(self, app):
        assert os.path.exists("frontend/vite.config.ts")
        c = open("frontend/vite.config.ts", encoding="utf-8").read()
        assert "/api" in c and "localhost:8000" in c
    def test_cors(self, app):
        with TestClient(app) as cl:
            r = cl.options("/api/v1/chat", headers={"Origin":"http://localhost:5173","Access-Control-Request-Method":"POST"})
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin")

@pytest.mark.asyncio
class TestChatPipeline:
    async def test_ecommerce_triggers_orch(self, app, real_products):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.post("/api/v1/chat", json={"message": E2E_Q[0]})
        assert r.status_code == 200
        d = r.json()
        assert len(d["reply"]) > 50
        assert d.get("conversation_id")
        assert "plan" in d
    async def test_pipeline_executes(self, app, real_products):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.post("/api/v1/chat", json={"message": E2E_Q[0]})
        d = r.json()
        reply = d.get("reply", "")
        assert len(reply) > 50
        assert d.get("plan") is not None
    async def test_non_ecommerce_returns_early(self, app):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            for q in ["今天天气怎么样", "帮我写一首诗", "你好"]:
                r = await c.post("/api/v1/chat", json={"message": q})
                assert r.status_code == 200
                assert len(r.json()["reply"]) > 20
    async def test_schema_valid(self, app, real_products):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.post("/api/v1/chat", json={"message": "电子产品分析"})
        p = ChatResponse.model_validate(r.json())
        assert p.reply and p.conversation_id
class TestDataConsistency:
    def test_20_products(self, app):
        with TestClient(app) as c:
            assert len(c.get("/api/v1/dashboard/products").json()) == 20
    def test_4_categories(self, app):
        with TestClient(app) as c:
            cats = {p["category"] for p in c.get("/api/v1/dashboard/products").json()}
        assert cats == FAKE_CATS
    def test_id_consistency(self, app):
        with TestClient(app) as c:
            p = c.get("/api/v1/dashboard/products").json()
            h = c.get("/api/v1/dashboard/hot-ranking?top_n=20").json()
            s = c.get("/api/v1/dashboard/rating-scatter").json()
        assert {x["id"] for x in p} == {x["id"] for x in h} == {x["id"] for x in s}
    def test_price_dist_sum(self, app):
        with TestClient(app) as c:
            d = c.get("/api/v1/dashboard/price-distribution").json()
        assert sum(s["count"] for s in d) == 20
    def test_hot_ranking_score(self, app):
        with TestClient(app) as c:
            h = c.get("/api/v1/dashboard/hot-ranking?top_n=20").json()
        for item in h:
            exp = round(item["rating"] * math.log(item["review_count"] + 1), 4)
            assert item["composite_score"] == exp
        scores = [x["composite_score"] for x in h]
        assert scores == sorted(scores, reverse=True)
    def test_sales_trend(self, app):
        with TestClient(app) as c:
            for days in [7, 30]:
                t = c.get("/api/v1/dashboard/sales-trend", params={"days": days}).json()
                assert len(t) == days
                for p in t:
                    for k in ["day", "total_sales", "total_revenue", "order_count"]:
                        assert k in p

@pytest.mark.asyncio
class TestConversation:
    async def test_id_persists(self, app, real_products):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r1 = await c.post("/api/v1/chat", json={"message": "电子产品选品分析"})
            cid = r1.json()["conversation_id"]
            r2 = await c.post("/api/v1/chat", json={"message": "再分析女装", "conversation_id": cid})
            assert r2.json()["conversation_id"] == cid
    async def test_independent_sessions(self, app, real_products):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r1, r2 = await asyncio.gather(
                c.post("/api/v1/chat", json={"message": "电子产品"}),
                c.post("/api/v1/chat", json={"message": "女装趋势"}),
            )
            assert r1.json()["conversation_id"] != r2.json()["conversation_id"]

@pytest.mark.asyncio
class TestErrorHandling:
    async def test_missing_field(self, app):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.post("/api/v1/chat", json={})
        assert r.status_code == 422
    async def test_invalid_conv_id(self, app):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.post("/api/v1/chat", json={"message": "测试", "conversation_id": "nonexistent"})
        assert r.status_code == 200
        assert r.json()["conversation_id"]
    async def test_health(self, app):
        t = ASGITransport(app=app)
        async with AsyncClient(transport=t, base_url="http://test") as c:
            r = await c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "version": "1.0.0"}
class TestDataIntegrity:
    def test_unique_ids(self, app):
        with TestClient(app) as c:
            ids = [p["id"] for p in c.get("/api/v1/dashboard/products").json()]
        assert len(ids) == len(set(ids))
    def test_positive_prices(self, app):
        with TestClient(app) as c:
            for p in c.get("/api/v1/dashboard/products").json():
                assert p["price"] > 0
    def test_valid_ratings(self, app):
        with TestClient(app) as c:
            for p in c.get("/api/v1/dashboard/products").json():
                r = p.get("rating", {})
                assert 0 <= r.get("rate", 0) <= 5
                assert r.get("count", 0) >= 0
    def test_valid_images(self, app):
        with TestClient(app) as c:
            for p in c.get("/api/v1/dashboard/products").json():
                assert p.get("image", "").startswith("https://")
    def test_concurrent_requests(self, app):
        def send(q):
            return TestClient(app).post("/api/v1/chat", json={"message": q}).json()["conversation_id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(send, E2E_Q))
        assert len(set(ids)) == len(E2E_Q)

class TestPerformance:
    def test_health_fast(self, app):
        start = time.perf_counter()
        TestClient(app).get("/health")
        assert (time.perf_counter() - start) * 1000 < 500
    def test_products_fast(self, app):
        start = time.perf_counter()
        TestClient(app).get("/api/v1/dashboard/products")
        assert (time.perf_counter() - start) * 1000 < 5000
    def test_chat_timeout(self, app):
        start = time.perf_counter()
        r = TestClient(app).post("/api/v1/chat", json={"message": "电子产品选品分析"})
        assert r.status_code == 200
