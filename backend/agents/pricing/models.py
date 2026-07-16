"""3-factor pricing model with strategy classification.

Factors & weights
-----------------
| Factor           | Weight | Source                          |
|------------------|--------|---------------------------------|
| Cost-plus        |  30 %  | current_price * (1 + margin)    |
| Competitor       |  40 %  | category_avg_price              |
| Value            |  30 %  | rating/price_percentile adj.    |
"""
from __future__ import annotations
import math
from typing import Any

W_COST: float = 0.30
W_COMPETITOR: float = 0.40
W_VALUE: float = 0.30

DEFAULT_MARGIN = 0.25
FLOOR_PCT = 0.7   # floor = market_avg * 0.7
CEILING_PCT = 1.8  # ceiling = market_avg * 1.8


def compute_cost_plus_price(current_price: float, margin: float = DEFAULT_MARGIN) -> float:
    """Cost-plus pricing: assume current price covers cost."""
    return current_price * (1.0 + margin)


def compute_competitor_price(market_benchmark: dict[str, Any] | None) -> float:
    """Competitor-based pricing from category benchmark data."""
    if not market_benchmark:
        return 0.0
    avg_price = market_benchmark.get("avg_price", 0) or market_benchmark.get("price_median", 0)
    return float(avg_price)


def compute_value_price(
    current_price: float,
    competitive_position: dict[str, Any] | None,
) -> float:
    """Value-based pricing adjustment using competitive position.

    Higher rating and competitive score → premium.
    Lower rating or weak position → discount.
    """
    if not competitive_position:
        return current_price

    rating = competitive_position.get("rating", 0)
    competitive_score = competitive_position.get("competitive_score", 50)
    rating_percentile = competitive_position.get("rating_percentile", 0.5)
    price_percentile = competitive_position.get("price_percentile", 0.5)

    # Rating premium: up to +20% for perfect score
    rating_factor = 1.0 + (rating / 5.0 - 0.5) * 0.4

    # Competitive score factor: up to +/-15%
    score_factor = 1.0 + (competitive_score - 50) / 100.0 * 0.3

    # Price position factor: if currently underpriced relative to quality
    position_factor = 1.0
    if rating_percentile > 0.7 and price_percentile < 0.3:
        # High rating but low price → room to increase
        position_factor = 1.10
    elif rating_percentile < 0.3 and price_percentile > 0.7:
        # Low rating but high price → should decrease
        position_factor = 0.90

    return current_price * rating_factor * score_factor * position_factor


def compute_dynamic_factor(
    competitive_position: dict[str, Any] | None,
) -> float:
    """Dynamic adjustment factor based on market dynamics."""
    if not competitive_position:
        return 1.0

    advantages = competitive_position.get("advantages", [])
    disadvantages = competitive_position.get("disadvantages", [])

    factor = 1.0
    if advantages:
        factor += 0.02 * len(advantages)
    if disadvantages:
        factor -= 0.03 * len(disadvantages)

    # Differentiator premium
    diff = competitive_position.get("differentiators", [])
    if diff:
        factor += 0.01 * len(diff)

    return max(0.85, min(1.15, factor))


def classify_strategy(
    suggested_price: float,
    current_price: float,
    market_avg_price: float,
    competitive_score: float,
    rating: float,
) -> dict[str, str]:
    """Classify pricing strategy and confidence.

    Returns:
        {"strategy": str, "confidence": str, "reason": str}
    """
    price_change_pct = ((suggested_price - current_price) / max(current_price, 0.01)) * 100

    if price_change_pct <= -10:
        strategy = "penetration"
        reason = f"\u4e0e\u5f53\u524d\u4ef7\u683c${current_price:.2f}\u76f8\u6bd4\u964d\u4ef7{abs(price_change_pct):.0f}%\uff0c\u91c7\u7528\u6e17\u900f\u5b9a\u4ef7\u7b56\u7565\u4ee5\u5feb\u901f\u5360\u9886\u5e02\u573a"
    elif price_change_pct >= 15 and rating >= 4.0:
        strategy = "skimming"
        reason = f"\u9ad8\u8bc4\u5206({rating}/5)\u652f\u6491\u6d3b\u52a8\u5b9a\u4ef7\uff0c\u5efa\u8bae\u6da8\u4ef7{price_change_pct:.0f}%\uff0c\u91c7\u7528\u6d3b\u52a8\u5b9a\u4ef7\u7b56\u7565"
    elif price_change_pct >= 5:
        strategy = "price-up"
        reason = f"\u5efa\u8bae\u5c0f\u5e45\u4e0a\u8c03\u4ef7\u683c{price_change_pct:.0f}%\uff0c\u4ee5\u63d0\u5347\u5229\u6da6\u7387"
    elif price_change_pct <= -5:
        strategy = "price-down"
        reason = f"\u5efa\u8bae\u9002\u5f53\u964d\u4ef7{abs(price_change_pct):.0f}%\uff0c\u63d0\u5347\u7ade\u4e89\u529b"
    else:
        strategy = "follow"
        reason = f"\u5f53\u524d\u4ef7\u683c\u57fa\u672c\u5408\u7406\uff0c\u5efa\u8bae\u8ddf\u968f\u5e02\u573a\u5b9a\u4ef7"

    # Confidence
    if market_avg_price > 0 and competitive_score > 0:
        confidence = "\u9ad8" if rating >= 4.0 else "\u4e2d"
    elif market_avg_price > 0:
        confidence = "\u4e2d"
    else:
        confidence = "\u4f4e"

    return {"strategy": strategy, "confidence": confidence, "reason": reason}


def compute_suggested_price(
    current_price: float,
    market_benchmark: dict[str, Any] | None = None,
    competitive_position: dict[str, Any] | None = None,
    margin: float = DEFAULT_MARGIN,
) -> dict[str, Any]:
    """Compute suggested price using 3-factor weighted model.

    Args:
        current_price: Current selling price.
        market_benchmark: Category benchmark dict (avg_price, price_median, etc.)
        competitive_position: Product positioning dict (rating, competitive_score, etc.)
        margin: Desired profit margin.

    Returns:
        Dict with suggested_price, price_change, strategy, confidence, reason,
        and factor_breakdown.
    """
    # Factor 1: Cost-plus
    cost_plus = compute_cost_plus_price(current_price, margin)

    # Factor 2: Competitor
    competitor = compute_competitor_price(market_benchmark)

    # Factor 3: Value
    value_based = compute_value_price(current_price, competitive_position)

    # Dynamic adjustment
    dynamic = compute_dynamic_factor(competitive_position)

    # Weighted combination
    if competitor > 0 and market_benchmark:
        # All three factors available
        suggested = (cost_plus * W_COST + competitor * W_COMPETITOR + value_based * W_VALUE) * dynamic
    elif competitor > 0:
        suggested = (cost_plus * 0.4 + competitor * 0.6) * dynamic
    else:
        # Only cost-plus and value
        suggested = (cost_plus * 0.5 + value_based * 0.5) * dynamic

    # Floor / ceiling based on market
    if market_benchmark:
        avg_price = market_benchmark.get("avg_price", 0)
        if avg_price > 0:
            floor = avg_price * FLOOR_PCT
            ceiling = avg_price * CEILING_PCT
            suggested = max(floor, min(ceiling, suggested))

    suggested_price = round(max(suggested, 0.01), 2)
    price_change = round(suggested_price - current_price, 2)

    # Classify strategy
    rating = (competitive_position or {}).get("rating", 0)
    comp_score = (competitive_position or {}).get("competitive_score", 0)
    avg_price = (market_benchmark or {}).get("avg_price", 0)

    strategy_info = classify_strategy(
        suggested_price, current_price, avg_price,
        competitive_score=comp_score, rating=rating,
    )

    return {
        "suggested_price": suggested_price,
        "price_change": price_change,
        "strategy": strategy_info["strategy"],
        "confidence": strategy_info["confidence"],
        "reason": strategy_info["reason"],
        "factor_breakdown": {
            "cost_plus": round(cost_plus, 2),
            "competitor": round(competitor, 2) if competitor > 0 else None,
            "value_based": round(value_based, 2),
            "dynamic_factor": round(dynamic, 3),
        },
    }