"""5-dimension Min-Max normalised scoring model for competitive positioning.

Dimensions & weights
--------------------
| Dimension              | Field                     | Weight |
|------------------------|---------------------------|--------|
| Price competitiveness  | price (inverted)          |  20 %  |
| Rating quality         | rating.rate               |  25 %  |
| Popularity             | rating.count              |  20 %  |
| Value for money        | rate / price              |  20 %  |
| Description depth      | len(description)          |  15 %  |

Every dimension is Min-Max normalised across the category group.
When max == min for a dimension, normalised value = 1.0.
"""
from __future__ import annotations

import math
from typing import Any

# ── Weights ──────────────────────────────────────────────

W_PRICE: float = 0.20        # inverted — lower price = higher score
W_RATING: float = 0.25
W_POPULARITY: float = 0.20
W_VALUE: float = 0.20
W_DESCRIPTION: float = 0.15

# ── Thresholds ──────────────────────────────────────────

ADVANTAGE_THRESHOLD: float = 0.70       # norm ≥ 0.7 → strength
DISADVANTAGE_THRESHOLD: float = 0.35    # norm ≤ 0.35 → weakness
DIFFERENTIATOR_PERCENTILE: float = 0.80  # top 20 % → differentiator

# ── Public helpers ───────────────────────────────────────

COMPETITIVE_DIMS = ["price", "rating", "popularity", "value", "description"]
DIM_LABELS: dict[str, str] = {
    "price": "价格竞争力",
    "rating": "评分质量",
    "popularity": "市场热度",
    "value": "性价比",
    "description": "描述详细度",
}
DIM_ADV_LABELS: dict[str, str] = {
    "price": "价格优势明显，低于品类均价",
    "rating": "评分高于品类平均，口碑良好",
    "popularity": "市场热度高，用户关注度领先",
    "value": "性价比突出，物超所值",
    "description": "商品描述详细，信息透明度高",
}
DIM_DISADV_LABELS: dict[str, str] = {
    "price": "价格偏高，竞争力不足",
    "rating": "评分低于品类平均，需关注质量口碑",
    "popularity": "市场热度偏低，曝光度不足",
    "value": "性价比偏低，价格与价值不匹配",
    "description": "商品描述不够详细，影响转化",
}


def safe_norm(value: float, v_min: float, v_max: float) -> float:
    """Min-Max normalise *value* to [0, 1]; return 1.0 when range is zero."""
    if v_max <= v_min:
        return 1.0
    return (value - v_min) / (v_max - v_min)


def inverted_norm(value: float, v_min: float, v_max: float) -> float:
    """Min-Max normalise with inversion (lower = better)."""
    if v_max <= v_min:
        return 1.0
    return (v_max - value) / (v_max - v_min)


def compute_category_extrema(
    products: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Compute min/max for each competitive dimension across a category group.

    Returns::

        {
            "price":  {"min": …, "max": …},
            "rating": {"min": …, "max": …},
            "count":  {"min": …, "max": …},
            "value":  {"min": …, "max": …},    # rate / price
            "desc":   {"min": …, "max": …},    # description length
        }
    """
    prices = [p["price"] for p in products]
    rates = [p["rating"]["rate"] for p in products]
    counts = [p["rating"]["count"] for p in products]
    values = [p["rating"]["rate"] / max(p["price"], 0.01) for p in products]
    descs = [len(p.get("description") or "") for p in products]

    return {
        "price":  {"min": min(prices), "max": max(prices)},
        "rating": {"min": min(rates), "max": max(rates)},
        "count":  {"min": min(counts), "max": max(counts)},
        "value":  {"min": min(values), "max": max(values)},
        "desc":   {"min": min(descs), "max": max(descs)},
    }


def build_category_benchmark(
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate benchmark statistics for one category."""
    if not products:
        return {}

    prices = [p["price"] for p in products]
    rates = [p["rating"]["rate"] for p in products]
    counts = [p["rating"]["count"] for p in products]
    sorted_prices = sorted(prices)
    n = len(sorted_prices)

    # Median price
    if n % 2 == 1:
        median = sorted_prices[n // 2]
    else:
        median = (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2.0

    return {
        "product_count": n,
        "avg_price": round(sum(prices) / n, 2),
        "price_range": {"min": min(prices), "max": max(prices)},
        "price_median": round(median, 2),
        "avg_rating": round(sum(rates) / n, 2),
        "rating_range": {"min": min(rates), "max": max(rates)},
        "total_reviews": sum(counts),
        "avg_reviews": round(sum(counts) / n, 1),
    }


def score_product_competitive(
    product: dict[str, Any],
    extrema: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Compute 5-dimension competitive scores for one product within its category.

    Returns::

        {
            "competitive_score": float,     # 0–100
            "dimension_norms": { … },       # raw normalised [0, 1]
            "contributions": { … },         # weighted ×100
        }
    """
    price = max(product["price"], 0.01)
    rate = product["rating"]["rate"]
    count = product["rating"]["count"]
    desc_len = len(product.get("description") or "")
    value = rate / price

    # Normalised values [0, 1]
    n_price = inverted_norm(price, extrema["price"]["min"], extrema["price"]["max"])
    n_rating = safe_norm(rate, extrema["rating"]["min"], extrema["rating"]["max"])
    n_count = safe_norm(count, extrema["count"]["min"], extrema["count"]["max"])
    n_value = safe_norm(value, extrema["value"]["min"], extrema["value"]["max"])
    n_desc = safe_norm(desc_len, extrema["desc"]["min"], extrema["desc"]["max"])

    # Weighted contributions
    c_price = n_price * W_PRICE * 100
    c_rating = n_rating * W_RATING * 100
    c_count = n_count * W_POPULARITY * 100
    c_value = n_value * W_VALUE * 100
    c_desc = n_desc * W_DESCRIPTION * 100

    competitive_score = round(c_price + c_rating + c_count + c_value + c_desc, 2)

    return {
        "competitive_score": competitive_score,
        "dimension_norms": {
            "price": round(n_price, 3),
            "rating": round(n_rating, 3),
            "popularity": round(n_count, 3),
            "value": round(n_value, 3),
            "description": round(n_desc, 3),
        },
        "contributions": {
            "price": round(c_price, 2),
            "rating": round(c_rating, 2),
            "popularity": round(c_count, 2),
            "value": round(c_value, 2),
            "description": round(c_desc, 2),
        },
    }


def generate_insights(
    norms: dict[str, float],
    contributions: dict[str, float],
) -> dict[str, list[str]]:
    """Generate advantage / disadvantage / differentiator lists.

    - **Advantage**: norm ≥ ADVANTAGE_THRESHOLD
    - **Disadvantage**: norm ≤ DISADVANTAGE_THRESHOLD
    - **Differentiator**: contribution ranks in top 20 % of dimensions
    """
    advantages: list[str] = []
    disadvantages: list[str] = []
    differentiators: list[str] = []

    for dim in COMPETITIVE_DIMS:
        norm_val = norms.get(dim, 0.0)
        if norm_val >= ADVANTAGE_THRESHOLD:
            advantages.append(DIM_ADV_LABELS.get(dim, dim))
        if norm_val <= DISADVANTAGE_THRESHOLD:
            disadvantages.append(DIM_DISADV_LABELS.get(dim, dim))

    # Differentiators: top 20 % contributions
    sorted_dims = sorted(contributions.items(), key=lambda x: -x[1])
    top_n = max(1, round(len(sorted_dims) * DIFFERENTIATOR_PERCENTILE))
    top_dims = {d[0] for d in sorted_dims[:top_n]}
    for dim in COMPETITIVE_DIMS:
        if dim in top_dims:
            label = DIM_LABELS.get(dim, dim)
            differentiators.append(f"{label}为其核心竞争优势")

    return {
        "advantages": advantages,
        "disadvantages": disadvantages,
        "differentiators": differentiators,
    }