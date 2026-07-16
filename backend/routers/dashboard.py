"""Dashboard router — GET endpoints for chart data."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services.data_generator import generate_sales_history
from backend.services.fake_store import FakeStoreService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/products")
async def get_all_products() -> list[dict[str, Any]]:
    """Fetch all products from FakeStore API."""
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()
    return products


@router.get("/price-distribution")
async def get_price_distribution() -> list[dict[str, Any]]:
    """Aggregate products by price segments.

    Returns buckets::
        [{"segment": "0-25", "count": N, "products": [...]}, ...]
    """
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()

    buckets: dict[str, list[dict[str, Any]]] = {}
    for p in products:
        price = p.get("price", 0)
        if price <= 25:
            key = "0-25"
        elif price <= 50:
            key = "25-50"
        elif price <= 100:
            key = "50-100"
        elif price <= 200:
            key = "100-200"
        else:
            key = "200+"
        buckets.setdefault(key, []).append(p)

    segment_order = ["0-25", "25-50", "50-100", "100-200", "200+"]
    return [
        {
            "segment": seg,
            "count": len(buckets.get(seg, [])),
            "min_price": min((p["price"] for p in buckets.get(seg, [])), default=0),
            "max_price": max((p["price"] for p in buckets.get(seg, [])), default=0),
            "avg_price": (
                sum(p["price"] for p in buckets.get(seg, [])) / len(buckets.get(seg, []))
                if buckets.get(seg)
                else 0
            ),
        }
        for seg in segment_order
    ]


@router.get("/sales-trend")
async def get_sales_trend(days: int = 30) -> list[dict[str, Any]]:
    """Generate simulated daily sales trend data.

    Returns a list of daily snapshots::
        [{"day": 1, "total_sales": ..., "total_revenue": ..., "order_count": ...}, ...]
    """
    # Generate sales for a representative set of products
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()

    # Use top 5 products by rating
    top_products = sorted(products, key=lambda p: p.get("rating", {}).get("rate", 0), reverse=True)[:5]

    daily_trend: list[dict[str, Any]] = []
    for day in range(1, days + 1):
        day_sales = 0.0
        day_revenue = 0.0
        day_orders = 0
        for p in top_products:
            history = generate_sales_history(p["id"], (p.get("rating") or {}).get("count", 0), days=days)
            if day - 1 < len(history):
                record = history[day - 1]
                day_sales += record.get("sales", 0)
                day_revenue += record.get("revenue", 0)
                day_orders += record.get("order_count", 0)
        daily_trend.append({
            "day": day,
            "total_sales": round(day_sales, 0),
            "total_revenue": round(day_revenue, 2),
            "order_count": day_orders,
        })

    return daily_trend


@router.get("/hot-ranking")
async def get_hot_ranking(top_n: int = 10) -> list[dict[str, Any]]:
    """Rank products by composite score (rating * log(review_count + 1))."""
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()

    import math

    scored = []
    for p in products:
        rating = p.get("rating", {}) or {}
        rate = rating.get("rate", 0)
        count = rating.get("count", 0)
        composite = rate * math.log(count + 1)
        scored.append({
            "id": p["id"],
            "title": p["title"],
            "category": p["category"],
            "price": p["price"],
            "rating": rate,
            "review_count": count,
            "composite_score": round(composite, 4),
            "image": p.get("image", ""),
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored[:top_n]


@router.get("/rating-scatter")
async def get_rating_scatter() -> list[dict[str, Any]]:
    """Return rating vs review-count scatter data for all products.

    Each point::
        {"id": ..., "title": ..., "category": ..., "price": ...,
         "rating": ..., "review_count": ..., "image": ...}
    """
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()

    return [
        {
            "id": p["id"],
            "title": p["title"],
            "category": p["category"],
            "price": p["price"],
            "rating": (p.get("rating") or {}).get("rate", 0),
            "review_count": (p.get("rating") or {}).get("count", 0),
            "image": p.get("image", ""),
        }
        for p in products
    ]


@router.get("/category-summary")
async def get_category_summary() -> list[dict[str, Any]]:
    """Aggregate products by category with summary stats."""
    svc = FakeStoreService()
    try:
        products = await svc.get_all_products()
    finally:
        await svc.close()

    categories: dict[str, list[dict]] = {}
    for p in products:
        cat = p.get("category", "unknown")
        categories.setdefault(cat, []).append(p)

    return [
        {
            "category": cat,
            "product_count": len(items),
            "avg_price": round(sum(i["price"] for i in items) / len(items), 2),
            "min_price": min(i["price"] for i in items),
            "max_price": max(i["price"] for i in items),
            "avg_rating": round(
                sum((i.get("rating") or {}).get("rate", 0) for i in items) / len(items), 2
            ),
            "total_reviews": sum((i.get("rating") or {}).get("count", 0) for i in items),
        }
        for cat, items in sorted(categories.items())
    ]
