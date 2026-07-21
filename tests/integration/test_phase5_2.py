"""Phase 5.2 - Chat Interface end-to-end test with real FakeStore API data."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.core.database import init_db
from backend.services.fake_store import FakeStoreService
from backend.models.schemas import ChatResponse


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


@pytest_asyncio.fixture
async def test_app():
    init_db()
    return create_app()


@pytest.mark.asyncio
class TestChatAPIWithRealData:

    async def test_ecommerce_query_returns_full_response(self, test_app, real_products):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"message": "帮我分析电子产品类目的选品机会，包括趋势预测和竞品对比"}
            resp = await client.post("/api/v1/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["conversation_id"] is not None
        reply = data["reply"]
        assert len(reply) > 50
        print(f"  Reply: {reply[:300]}...")

    async def test_chat_response_has_plan_and_sections(self, test_app, real_products):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", json={"message": "选品分析"})
        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "sections" in data
        sections = data.get("sections") or {}
        print(f"  Agents executed: {list(sections.keys())}")

    async def test_non_ecommerce_query_returns_helpful_reply(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", json={"message": "今天天气怎么样"})
        assert resp.status_code == 200
        data = resp.json()
        reply = data["reply"]
        assert len(reply) > 30
        print(f"  Non-ecommerce reply: {reply[:200]}...")

    async def test_conversation_id_persists(self, test_app, real_products):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post("/api/v1/chat", json={"message": "电子产品选品分析"})
            assert resp1.status_code == 200
            conv_id = resp1.json()["conversation_id"]
            resp2 = await client.post("/api/v1/chat", json={"message": "再分析一下女装类目", "conversation_id": conv_id})
            assert resp2.status_code == 200
            assert resp2.json()["conversation_id"] == conv_id
            print(f"  Same conversation: {conv_id}")

    async def test_chat_response_schema_valid(self, test_app, real_products):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", json={"message": "电子产品分析预测"})
        assert resp.status_code == 200
        parsed = ChatResponse.model_validate(resp.json())
        assert parsed.reply is not None
        assert parsed.conversation_id is not None
        print(f"  Schema valid, reply len: {len(parsed.reply)}")

    async def test_concurrent_sessions_independent(self, test_app, real_products):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post("/api/v1/chat", json={"message": "电子产品选品"})
            resp2 = await client.post("/api/v1/chat", json={"message": "女装趋势预测"})
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert resp1.json()["conversation_id"] != resp2.json()["conversation_id"]
            print(f"  Sessions: {resp1.json()['conversation_id']} != {resp2.json()['conversation_id']}")

    async def test_health_endpoint(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print(f"  Health: {data}")
