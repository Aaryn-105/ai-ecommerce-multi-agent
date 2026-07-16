"""Promotion calculator — compute discount rates, durations, ROI estimates.

Each promotion type has a default discount range. The calculator adjusts
based on product attributes, market context, and inventory status.
"""
from __future__ import annotations
import math
from typing import Any

# ── Default discount ranges per promotion type ───────────
# (min_discount, max_discount) as decimal fractions (0.0 - 1.0)
DEFAULT_DISCOUNT_RANGES: dict[str, tuple[float, float]] = {
    "flash_sale":   (0.30, 0.50),
    "clearance":    (0.50, 0.70),
    "discount":     (0.10, 0.30),
    "newcomer":     (0.10, 0.25),
    "new_product":  (0.10, 0.20),
    "bundle":       (0.15, 0.30),
    "threshold":    (0.05, 0.15),
    "member":       (0.10, 0.25),
}

# ── Default duration ranges in days ──────────────────────
DEFAULT_DURATION_RANGES: dict[str, tuple[int, int]] = {
    "flash_sale":   (1, 3),
    "clearance":    (7, 30),
    "discount":     (3, 14),
    "newcomer":     (30, 90),
    "new_product":  (7, 30),
    "bundle":       (7, 21),
    "threshold":    (3, 14),
    "member":       (30, 365),
}

# ── ROI estimation parameters ────────────────────────────
# Estimated sales lift multiplier per discount type
SALES_LIFT_FACTOR: dict[str, float] = {
    "flash_sale":   3.0,
    "clearance":    2.0,
    "discount":     1.8,
    "newcomer":     1.5,
    "new_product":  2.5,
    "bundle":       2.0,
    "threshold":    1.6,
    "member":       1.3,
}

# Price elasticity: how much demand increases per 1% price drop
PRICE_ELASTICITY: float = 1.5


def compute_discount_rate(
    promotion_type: str,
    product: dict[str, Any],
    match_score: float = 0.5,
) -> float:
    """Compute an appropriate discount rate for the promotion.

    Uses the default range for the type, then adjusts by match_score
    (higher score → more aggressive discount) and product attributes.
    """
    min_d, max_d = DEFAULT_DISCOUNT_RANGES.get(promotion_type, (0.10, 0.30))
    rating_obj = product.get("rating", {}) or {}
    rating = rating_obj.get("rate", 0)
    price = max(product.get("price", 0), 0.01)

    # Base: interpolate between min and max using match_score
    base_rate = min_d + (max_d - min_d) * match_score

    # Adjustments
    adjustments = 0.0

    # Higher rating → can take more aggressive discount
    if rating >= 4.5:
        adjustments += 0.03
    elif rating >= 4.0:
        adjustments += 0.02
    elif rating < 3.0:
        adjustments -= 0.03  # Less discount for low-rated products

    # Higher price → can support larger absolute discount
    if price >= 50:
        adjustments += 0.03
    elif price >= 20:
        adjustments += 0.01

    final_rate = base_rate + adjustments
    return round(max(min_d, min(max_d, final_rate)), 3)


def compute_promotion_price(
    original_price: float,
    discount_rate: float,
) -> float:
    """Compute promotion price after discount."""
    return round(original_price * (1.0 - discount_rate), 2)


def compute_duration_days(
    promotion_type: str,
    discount_rate: float = 0.0,
) -> int:
    """Compute recommended duration in days."""
    min_dur, max_dur = DEFAULT_DURATION_RANGES.get(promotion_type, (3, 14))
    # Steeper discount → shorter duration (urgency)
    if discount_rate >= 0.40:
        duration = min_dur
    elif discount_rate >= 0.25:
        duration = round((min_dur + max_dur) / 2)
    else:
        duration = max_dur
    return max(min_dur, min(max_dur, duration))


def compute_estimated_roi(
    original_price: float,
    promotion_price: float,
    discount_rate: float,
    promotion_type: str,
    rating_count: int,
) -> float:
    """Estimate ROI (as a multiplier) for the promotion.

    Uses price elasticity to estimate volume lift, then computes
    incremental revenue vs. no-promotion baseline.
    """
    price_drop_pct = 1.0 - (promotion_price / max(original_price, 0.01))

    # Volume lift using price elasticity
    volume_lift = 1.0 + PRICE_ELASTICITY * price_drop_pct

    # Additional lift from promotion type
    type_lift = SALES_LIFT_FACTOR.get(promotion_type, 1.5)
    total_lift = volume_lift * type_lift

    # Baseline units proxy (derived from rating_count)
    base_units = max(1, rating_count / 90.0)

    # Revenue with promotion
    promo_revenue = promotion_price * (base_units * total_lift)

    # Revenue without promotion (baseline)
    baseline_revenue = original_price * base_units

    # ROI = (incremental revenue - discount cost) / baseline_revenue
    discount_cost = (original_price - promotion_price) * (base_units * total_lift)
    incremental = promo_revenue - baseline_revenue
    roi = (incremental - discount_cost * 0.3) / max(baseline_revenue, 0.01)

    return round(roi, 3)


def compute_threshold_condition(
    promotion_type: str,
    original_price: float,
) -> str:
    """Generate a human-readable condition string."""
    conditions: dict[str, str] = {
        "flash_sale": f"限时抢购，售完即止",
        "clearance": f"清仓特价，库存有限",
        "discount": f"不限量，全场通用",
        "newcomer": f"新人首次购买专享",
        "new_product": f"新品首发优惠",
        "bundle": f"与同品类商品组合购买更优惠",
        "threshold": f"满{max(99, round(original_price * 5, -1)):.0f}元可用",
        "member": f"会员专享价，登录可见",
    }
    return conditions.get(promotion_type, "")


def generate_promotion_copy_preview(
    promotion_type: str,
    product_title: str,
    discount_rate: float,
    promotion_price: float,
    campaign_name: str = "",
) -> str:
    """Generate a short promotion copy preview."""
    discount_pct = round(discount_rate * 100)
    if not campaign_name:
        campaign_name = PROMO_CAMPAIGN_NAMES.get(promotion_type, "促销活动")
    return (
        f"【{campaign_name}】{product_title[:40]}，"
        f"限时直降{discount_pct}%，仅需¥{promotion_price:.2f}！"
    )


PROMO_CAMPAIGN_NAMES: dict[str, str] = {
    "flash_sale": "限时秒杀",
    "clearance": "清仓特卖",
    "discount": "嗨购折扣",
    "newcomer": "新人专享",
    "new_product": "新品首发",
    "bundle": "组合优惠",
    "threshold": "满减狂欢",
    "member": "会员特惠",
}