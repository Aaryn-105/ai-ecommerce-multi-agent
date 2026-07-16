"""4-dimension Min-Max normalised scoring model for product selection.

Dimensions & weights
--------------------
| Dimension         | Field                     | Weight |
|-------------------|---------------------------|--------|
| Rating quality    | rating.rate               |  30 %  |
| Popularity        | rating.count              |  30 %  |
| Value for money   | rate / price              |  25 %  |
| Description depth | len(description)          |  15 %  |

Every dimension is Min-Max normalised across the product set.
When max == min for a dimension, normalised value = 1.0.
"""

from __future__ import annotations

import math
from typing import Any

# ── Weights ──────────────────────────────────────────────

WEIGHT_RATING: float = 0.30
WEIGHT_POPULARITY: float = 0.30
WEIGHT_VALUE: float = 0.25
WEIGHT_DESCRIPTION: float = 0.15

# ── Public helpers ───────────────────────────────────────

def safe_norm(value: float, v_min: float, v_max: float) -> float:
    """Min-Max normalise *value* to [0, 1]; return 1.0 when range is zero."""
    if v_max <= v_min:
        return 1.0
    return (value - v_min) / (v_max - v_min)


def compute_global_extrema(products: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Compute min/max for each dimension across all products.

    Returns::

        {
            "rate":   {"min": …, "max": …},
            "count":  {"min": …, "max": …},
            "value":  {"min": …, "max": …},    # rate / price
            "desc":   {"min": …, "max": …},    # description length
        }
    """
    rates = [p["rating"]["rate"] for p in products]
    counts = [p["rating"]["count"] for p in products]
    values = [p["rating"]["rate"] / max(p["price"], 0.01) for p in products]
    descs = [len(p.get("description") or "") for p in products]

    return {
        "rate":  {"min": min(rates), "max": max(rates)},
        "count": {"min": min(counts), "max": max(counts)},
        "value": {"min": min(values), "max": max(values)},
        "desc":  {"min": min(descs), "max": max(descs)},
    }


def score_product(
    product: dict[str, Any],
    extrema: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Compute 4-dimension scores and contributions for one product.

    Returns::

        {
            "final_score": float,        # 0–100
            "dimensions": { … },
            "contributions": { … },
        }
    """
    rate = product["rating"]["rate"]
    count = product["rating"]["count"]
    price = max(product["price"], 0.01)
    desc_len = len(product.get("description") or "")
    value = rate / price

    # Normalised values [0, 1]
    n_rate = safe_norm(rate, extrema["rate"]["min"], extrema["rate"]["max"])
    n_count = safe_norm(count, extrema["count"]["min"], extrema["count"]["max"])
    n_value = safe_norm(value, extrema["value"]["min"], extrema["value"]["max"])
    n_desc = safe_norm(desc_len, extrema["desc"]["min"], extrema["desc"]["max"])

    # Weighted contributions (raw, before x100)
    c_rate = n_rate * WEIGHT_RATING * 100
    c_count = n_count * WEIGHT_POPULARITY * 100
    c_value = n_value * WEIGHT_VALUE * 100
    c_desc = n_desc * WEIGHT_DESCRIPTION * 100

    final_score = round(c_rate + c_count + c_value + c_desc, 2)

    return {
        "final_score": final_score,
        "dimensions": {
            "rating": round(n_rate, 3),
            "popularity": round(n_count, 3),
            "value": round(n_value, 3),
            "description": round(n_desc, 3),
        },
        "contributions": {
            "rating": round(c_rate, 2),
            "popularity": round(c_count, 2),
            "value": round(c_value, 2),
            "description": round(c_desc, 2),
        },
    }


def generate_selection_reason(
    contributions: dict[str, float],
    dimensions: dict[str, float],
) -> str:
    """Rule-based reason string based on contribution breakdown."""
    parts: list[str] = []
    sorted_dims = sorted(contributions.items(), key=lambda x: -x[1])
    top_dim, top_val = sorted_dims[0]

    dim_labels = {
        "rating": "高评分",
        "popularity": "高热度",
        "value": "高性价比",
        "description": "描述详细",
    }

    if top_val >= 15:
        parts.append(dim_labels.get(top_dim, top_dim))

    if top_val >= 20:
        parts.append("核心优势突出")
    elif top_val >= 12:
        parts.append("综合表现良好")

    # Check for balanced performance
    all_above_10 = all(v >= 10 for v in contributions.values())
    if all_above_10 and len(contributions) >= 3:
        parts.append("各维度均衡")

    # Check for weakness
    low_dims = [k for k, v in contributions.items() if v < 5]
    if low_dims and parts:
        pass  # Still selected despite weakness

    if not parts:
        parts.append("综合评分达标")

    return "，".join(parts)


def price_segment(price: float) -> str:
    """Classify price into a segment label."""
    if price < 30:
        return "低价(<30)"
    if price <= 100:
        return "中价(30-100)"
    return "高价(>100)"
