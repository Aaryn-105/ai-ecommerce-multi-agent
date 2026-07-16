"""Async HTTP client for the FakeStore API."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from backend.core.config import settings


class FakeStoreService:
    """Thin wrapper around https://fakestoreapi.com endpoints."""

    BASE_URL: str = settings.FAKESTORE_API_BASE
    _client: httpx.AsyncClient | None = None

    # ── Client lifecycle ──────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=httpx.Timeout(5.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Public methods ───────────────────────────────────

    async def get_all_products(self) -> list[dict[str, Any]]:
        """GET /products — return all 20 products."""
        client = await self._get_client()
        for attempt in range(3):
            try:
                resp = await client.get("/products")
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))
        return []  # unreachable

    async def get_product(self, product_id: int) -> dict[str, Any]:
        """GET /products/{id}."""
        client = await self._get_client()
        resp = await client.get(f"/products/{product_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_categories(self) -> list[str]:
        """GET /products/categories."""
        client = await self._get_client()
        resp = await client.get("/products/categories")
        resp.raise_for_status()
        return resp.json()
