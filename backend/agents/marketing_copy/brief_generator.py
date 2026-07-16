"""Generate marketing brief — extract selling points, set tone, and determine price strategy."""
from __future__ import annotations

from typing import Any


# ── Tone presets ─────────────────────────────────────────

CATEGORY_TONE: dict[str, str] = {
    "electronics": "科技感、专业、理性",
    "men's clothing": "干练、实用、品质",
    "women's clothing": "时尚、优雅、亲和",
    "jewelery": "精致、奢华、情感",
    "unknown": "专业、可信",
}

# ── Price strategy presets ───────────────────────────────

PRICE_STRATEGIES = {
    "premium": "高价定位策略 — 强调品质、稀缺性和品牌价值",
    "competitive": "竞争定价策略 — 强调性价比和与竞品的对比优势",
    "penetration": "渗透定价策略 — 以低价快速占领市场",
    "value": "价值定价策略 — 突出物超所值的购买体验",
}


def determine_tone(category: str, rating: float) -> str:
    """Determine marketing tone based on category and rating."""
    base_tone = CATEGORY_TONE.get(category, CATEGORY_TONE["unknown"])
    if rating >= 4.0:
        base_tone += "、自信"
    elif rating < 3.0:
        base_tone += "、诚恳改进"
    return base_tone


def determine_price_strategy(
    price: float,
    category_avg_price: float | None = None,
    price_label: str | None = None,
) -> str:
    """Select price strategy based on product price and market position."""
    if category_avg_price and price > category_avg_price * 1.2:
        return PRICE_STRATEGIES["premium"]
    if category_avg_price and price < category_avg_price * 0.8:
        return PRICE_STRATEGIES["penetration"]
    if price_label == "高价":
        return PRICE_STRATEGIES["premium"]
    if price_label == "低价":
        return PRICE_STRATEGIES["penetration"]
    return PRICE_STRATEGIES["competitive"]


def extract_selling_points(product: dict[str, Any]) -> list[str]:
    """Extract key selling points from product data."""
    points: list[str] = []
    title = product.get("title", "")
    category = product.get("category", "")
    price = product.get("price", 0)
    rating = product.get("rating", {})
    rate = rating.get("rate", 0)
    count = rating.get("count", 0)
    desc = product.get("description", "")

    # Point 1: Category + rating
    if rate >= 4.0:
        points.append(f"高分{category}商品（{rate}/5），{count}条用户评价")
    elif rate >= 3.0:
        points.append(f"{category}商品，{count}条用户评价")
    else:
        points.append(f"{category}商品，亲民定位")

    # Point 2: Price-based
    if price < 30:
        points.append(f"超值价格仅，入门首选")
    elif price <= 100:
        points.append(f"合理定价，品质之选")
    else:
        points.append(f"高端定位，投资级好物")

    # Point 3: Description length as detail indicator
    if desc and len(desc) > 200:
        points.append("详细规格说明，购买决策信息透明")

    # Point 4: Title-derived keyword
    keywords = [w for w in title.lower().split() if len(w) > 4]
    if keywords:
        top_kw = max(keywords, key=len)
        points.append(f"主打关键词：{top_kw}")

    return points


def build_marketing_brief(product: dict[str, Any], position: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a complete marketing brief for one product.

    Args:
        product:   Product dict (must have id, title, category, price, rating, description).
        position:  Optional competitive positioning data.

    Returns:
        Brief dict with tone, price_strategy, selling_points, core_selling_point.
    """
    category = product.get("category", "unknown")
    price = product.get("price", 0)
    rating = product.get("rating", {})
    rate = rating.get("rate", 0)

    # Use positioning data if available
    price_label = position.get("price_label") if position else None
    cat_avg_price = position.get("category_avg_price") if position else None

    tone = determine_tone(category, rate)
    price_strategy = determine_price_strategy(price, cat_avg_price, price_label)

    selling_points = extract_selling_points(product)

    # Add competitor insights
    advantages = position.get("advantages", []) if position else []
    if advantages:
        selling_points.extend(advantages[:2])

    # Core selling point
    if advantages:
        core = advantages[0]
    else:
        core = f"{category}优选，起"

    return {
        "tone": tone,
        "core_selling_point": core,
        "price_strategy": price_strategy,
        "selling_points": selling_points,
    }