"""Generate simulated business data (sales, stock levels, etc.)."""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import Any


def generate_sales_history(
    product_id: int,
    rating_count: int,
    days: int = 90,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Simulate daily sales units based on rating_count as a popularity proxy.

    Base daily volume is derived from *rating_count / 90* with ±30% noise.
    """
    if seed is not None:
        random.seed(seed)

    base_volume = max(1, rating_count // 90)
    today = date.today()
    sales: list[dict[str, Any]] = []

    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        noise = random.uniform(0.7, 1.3)
        units = max(0, round(base_volume * noise))
        sales.append({"date": day.isoformat(), "units": units})

    return sales


def simulate_stock_and_reorder(
    rating_count: int,
) -> dict[str, Any]:
    """Derive simulated current stock and reorder point from popularity."""
    base = max(5, int(rating_count * 0.4))
    stock = max(5, base - random.randint(0, max(1, base // 2)))
    reorder_point = max(15, int(rating_count * 0.5))
    return {
        "simulated_stock": stock,
        "simulated_reorder_point": reorder_point,
    }


def estimate_weekly_sales(rating_count: int) -> float:
    """Rough weekly sales estimate from total review count."""
    return max(0.5, rating_count / 52.0)


def estimate_sales_velocity(
    rating_count: int,
    max_rating_count: int,
) -> float:
    """Relative sales velocity in [0, 1]."""
    if max_rating_count <= 0:
        return 0.0
    return min(1.0, rating_count / max_rating_count)
