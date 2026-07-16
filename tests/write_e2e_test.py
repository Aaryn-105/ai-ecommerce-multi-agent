# -*- coding: utf-8 -*-
"""Phase 5.6 — System Integration & E2E Test."""
from __future__ import annotations

import math
import time
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.core.database import init_db
from backend.services.fake_store import FakeStoreService
from backend.models.schemas import ChatResponse

FAKE_CATEGORIES = {"electronics", "jewelery", "men's clothing", "women's clothing"}
E2E_QUERIES = [
    "帮我分析电子产品类目的选品机会",
    "女装类目趋势预测和竞品对比",
    "珠宝首饰的定价和促销策略",
    "男士服装的库存管理和营销文案",
]

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
