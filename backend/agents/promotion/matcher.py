"""8-type promotion rule tree — match products to suitable promotion types.

Rules evaluate product attributes, category benchmarks, and inventory/pricing
context to determine which promotions apply.
"""
from __future__ import annotations
from typing import Any

# ── Promotion type enum ──────────────────────────────────

PROMO_TYPES: list[str] = [
    "flash_sale",
    "clearance",
    "discount",
    "newcomer",
    "new_product",
    "bundle",
    "threshold",
    "member",
]

PROMO_LABELS: dict[str, str] = {
    "flash_sale": "限时秒杀",
    "clearance": "清仓特卖",
    "discount": "通用折扣",
    "newcomer": "新人专享",
    "new_product": "新品首发",
    "bundle": "组合优惠",
    "threshold": "满减优惠",
    "member": "会员专享",
}

PROMO_DESCRIPTIONS: dict[str, str] = {
    "flash_sale": "短时间大力度折扣，营造紧迫感",
    "clearance": "清仓处理，快速回笼资金",
    "discount": "常规促销折扣，提升销量",
    "newcomer": "新人首次购买专属优惠",
    "new_product": "新产品上市推广促销",
    "bundle": "关联商品打包销售",
    "threshold": "满额立减/满额赠礼",
    "member": "会员专属价格与权益",
}


def match_promotions(
    product: dict[str, Any],
    category_avg_price: float = 0.0,
    inventory_status: dict[str, Any] | None = None,
    pricing_context: dict[str, Any] | None = None,
    marketing_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Evaluate all 8 promotion types against a product.

    Returns a list of match dicts sorted by match_score descending:
        [
            {
                "promotion_type": str,
                "label": str,
                "match_score": float,         # 0.0 - 1.0
                "reason": str,
            },
            ...
        ]
    """
    price = max(product.get("price", 0), 0.01)
    rating_obj = product.get("rating", {}) or {}
    rating = rating_obj.get("rate", 0)
    rating_count = rating_obj.get("count", 0)
    category = product.get("category", "unknown")
    title = product.get("title", "").lower()

    inv = inventory_status or {}
    inv_score = inv.get("composite_score", 50)
    stock = inv.get("simulated_stock", 50)

    pricing = pricing_context or {}
    price_change = pricing.get("price_change", 0)
    pricing_strategy = pricing.get("strategy", "")

    marketing = marketing_context or {}

    matches: list[dict[str, Any]] = []

    # ── 1. Flash Sale ────────────────────────────────────
    score = 0.0
    reasons: list[str] = []
    if rating >= 4.0:
        score += 0.35
        reasons.append("高评分")
    if rating_count > 200:
        score += 0.20
        reasons.append("高人气")
    if price < category_avg_price * 1.2 if category_avg_price > 0 else True:
        score += 0.15
        reasons.append("价格适中")
    if inv_score > 60:
        score += 0.15
        reasons.append("库存充足")
    if pricing_strategy in ("penetration", "price-down", ""):
        score += 0.15
        reasons.append("定价策略支持")
    if score >= 0.4:
        matches.append({
            "promotion_type": "flash_sale",
            "label": PROMO_LABELS["flash_sale"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 2. Clearance ─────────────────────────────────────
    score = 0.0
    reasons = []
    if inv_score < 30 or (inv_score < 50 and stock > 80):
        score += 0.30
        reasons.append("库存积压")
    if rating < 3.5:
        score += 0.20
        reasons.append("评分偏低")
    if rating_count < 200:
        score += 0.15
        reasons.append("销量不佳")
    if pricing_strategy == "price-down":
        score += 0.15
        reasons.append("降价策略")
    if stock > 100:
        score += 0.10
        reasons.append("库存量大")
    if rating < 2.5:
        score += 0.10
        reasons.append("评分很低")
    if score >= 0.35:
        matches.append({
            "promotion_type": "clearance",
            "label": PROMO_LABELS["clearance"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 3. Discount ──────────────────────────────────────
    score = 0.0
    reasons = []
    if 3.0 <= rating <= 4.5:
        score += 0.30
        reasons.append("评分适中")
    if 100 <= rating_count <= 500:
        score += 0.20
        reasons.append("中等销量")
    if price >= 10:
        score += 0.15
        reasons.append("价格适宜促销")
    if inv_score >= 40:
        score += 0.15
        reasons.append("库存健康")
    if pricing_strategy in ("follow", "price-up", ""):
        score += 0.20
        reasons.append("定价策略支持")
    if score >= 0.4:
        matches.append({
            "promotion_type": "discount",
            "label": PROMO_LABELS["discount"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 4. Newcomer ──────────────────────────────────────
    # Universal promotion type — always applicable with base score
    score = 0.5
    reasons = ["新人专享通用策略"]
    if rating_count < 200:
        score += 0.15
        reasons.append("新客吸引")
    if price >= 20:
        score += 0.10
        reasons.append("高客单价适合新人优惠")
    matches.append({
        "promotion_type": "newcomer",
        "label": PROMO_LABELS["newcomer"],
        "match_score": round(min(1.0, score), 2),
        "reason": "；".join(reasons),
    })

    # ── 5. New Product ───────────────────────────────────
    score = 0.0
    reasons = []
    if rating_count < 50:
        score += 0.35
        reasons.append("新品上市")
    if rating_count < 100:
        score += 0.15
        reasons.append("销量有待提升")
    if inv_score > 50:
        score += 0.20
        reasons.append("库存支持新品推广")
    if price >= 5:
        score += 0.15
        reasons.append("价格适合推广")
    if score >= 0.35:
        matches.append({
            "promotion_type": "new_product",
            "label": PROMO_LABELS["new_product"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 6. Bundle ────────────────────────────────────────
    score = 0.0
    reasons = []
    bundle_categories = ["electronics", "jewelery", "clothing"]
    if any(c in category.lower() for c in bundle_categories):
        score += 0.30
        reasons.append("适合捆绑销售的品类")
    if rating >= 3.5:
        score += 0.15
        reasons.append("评分良好")
    if price >= 15:
        score += 0.20
        reasons.append("价格适合捆绑")
    if inv_score >= 50:
        score += 0.15
        reasons.append("库存充足支持捆绑")
    if score >= 0.35:
        matches.append({
            "promotion_type": "bundle",
            "label": PROMO_LABELS["bundle"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 7. Threshold ─────────────────────────────────────
    score = 0.0
    reasons = []
    if price >= 20:
        score += 0.35
        reasons.append("高客单价")
    if rating >= 3.5:
        score += 0.15
        reasons.append("评分良好")
    if inv_score >= 50:
        score += 0.20
        reasons.append("库存充足")
    if category_avg_price > 0 and price >= category_avg_price:
        score += 0.15
        reasons.append("高于品类均价")
    if score >= 0.35:
        matches.append({
            "promotion_type": "threshold",
            "label": PROMO_LABELS["threshold"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # ── 8. Member ────────────────────────────────────────
    score = 0.0
    reasons = []
    if rating >= 4.0:
        score += 0.30
        reasons.append("高评分适合会员特供")
    if rating_count > 150:
        score += 0.20
        reasons.append("受欢迎商品")
    if price >= 15:
        score += 0.20
        reasons.append("价格适合会员权益")
    if inv_score >= 50:
        score += 0.15
        reasons.append("库存充足")
    if score >= 0.35:
        matches.append({
            "promotion_type": "member",
            "label": PROMO_LABELS["member"],
            "match_score": round(min(1.0, score), 2),
            "reason": "；".join(reasons) if reasons else "综合匹配",
        })

    # Sort by match_score descending
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return matches


def get_top_matches(
    product: dict[str, Any],
    category_avg_price: float = 0.0,
    inventory_status: dict[str, Any] | None = None,
    pricing_context: dict[str, Any] | None = None,
    marketing_context: dict[str, Any] | None = None,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Return top-N matched promotion types."""
    all_matches = match_promotions(
        product, category_avg_price, inventory_status,
        pricing_context, marketing_context,
    )
    return all_matches[:top_n]