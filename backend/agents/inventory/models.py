"""4-dimension scoring model for inventory replenishment analysis.

Dimensions & weights
--------------------
| Dimension             | Source                     | Weight |
|-----------------------|----------------------------|--------|
| Sales velocity        | rating.count (normalised)  |  30 %  |
| Stock health          | stock / reorder_point      |  25 %  |
| Replenishment urgency | (reorder - stock) / reorder|  25 %  |
| Turnover rate         | rating_count / max_count   |  20 %  |

Also provides EOQ (Economic Order Quantity) and safety stock calculations.
"""
from __future__ import annotations
import math
from typing import Any

W_VELOCITY: float = 0.30
W_HEALTH: float = 0.25
W_URGENCY: float = 0.25
W_TURNOVER: float = 0.20

LEAD_TIME_DAYS = 7
ORDERING_COST = 5.0
HOLDING_COST_PCT = 0.15
SERVICE_LEVEL_Z = 1.65  # 95 % service level


def safe_norm(value: float, v_min: float, v_max: float) -> float:
    """Min-Max normalise to [0, 1]; return 1.0 when range is zero."""
    if v_max <= v_min:
        return 1.0
    return (value - v_min) / (v_max - v_min)


def inverted_norm(value: float, v_min: float, v_max: float) -> float:
    """Inverted Min-Max (lower = better)."""
    if v_max <= v_min:
        return 1.0
    return (v_max - value) / (v_max - v_min)


def compute_sales_velocity(rating_count: int, max_count: int) -> float:
    """Normalised sales velocity [0, 1] based on rating count."""
    if max_count <= 0:
        return 0.0
    return min(1.0, rating_count / max_count)


def compute_stock_health(stock: int, reorder_point: int) -> float:
    """Stock health score [0, 1].

    Health = how far above reorder point.
    1.0 = stock >= 3x reorder point (overstocked)
    0.0 = stock <= 0
    """
    if reorder_point <= 0:
        return 1.0
    ratio = stock / reorder_point
    return min(1.0, max(0.0, ratio / 3.0))


def compute_urgency(stock: int, reorder_point: int) -> float:
    """Replenishment urgency [0, 1].

    Urgency = how close to stockout.
    1.0 = stock <= 0 (critical)
    0.0 = stock >= reorder_point * 2 (safe)
    """
    if reorder_point <= 0:
        return 0.0
    if stock <= 0:
        return 1.0
    if stock >= reorder_point * 2:
        return 0.0
    return max(0.0, 1.0 - (stock / (reorder_point * 2)))


def compute_turnover_rate(rating_count: int, max_count: int) -> float:
    """Turnover rate [0, 1]."""
    return compute_sales_velocity(rating_count, max_count)


def compute_eoq(demand_rate: float, unit_price: float) -> int:
    """Economic Order Quantity using basic EOQ formula.

    EOQ = sqrt(2 * D * S / (H * P))

    Args:
        demand_rate: Annual demand estimate (units).
        unit_price:  Unit cost of the product.

    Returns:
        EOQ rounded to nearest integer, at least 1.
    """
    if unit_price <= 0 or demand_rate <= 0:
        return 1
    numerator = 2.0 * demand_rate * ORDERING_COST
    denominator = HOLDING_COST_PCT * unit_price
    if denominator <= 0:
        return 1
    eoq = math.sqrt(numerator / denominator)
    return max(1, round(eoq))


def compute_safety_stock(
    max_daily_demand: float,
    avg_daily_demand: float,
    lead_time: int = LEAD_TIME_DAYS,
) -> int:
    """Safety stock using basic variability formula.

    SS = Z * sigma_d * sqrt(LT)

    Where sigma_d is approximated as (max - avg).
    """
    if max_daily_demand <= avg_daily_demand or lead_time <= 0:
        return 0
    sigma_d = max_daily_demand - avg_daily_demand
    ss = SERVICE_LEVEL_Z * sigma_d * math.sqrt(lead_time)
    return max(0, round(ss))


def score_inventory(
    product: dict[str, Any],
    max_rating_count: int,
    sim_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute 4-dimension inventory scores for one product.

    Args:
        product: Product dict (id, title, price, rating, etc.)
        max_rating_count: Max rating.count across all products.
        sim_data: Optional pre-computed simulated data.

    Returns:
        Scored result dict with dimensions, contributions, composite_score,
        eoq, safety_stock, suggested_reorder_qty, suggested_action.
    """
    pid = product.get("id", 0)
    title = product.get("title", "Unknown")
    price = max(product.get("price", 0.01), 0.01)
    rating = product.get("rating", {}) or {}
    rating_count = rating.get("count", 0)
    rating_rate = rating.get("rate", 0)

    # Use simulated data or generate (deterministic via product_id seed)
    if sim_data is None:
        import random as _r
        _state = _r.getstate()
        _r.seed(pid)
        from backend.services.data_generator import simulate_stock_and_reorder
        sim_data = simulate_stock_and_reorder(rating_count)
        _r.setstate(_state)

    stock = sim_data.get("simulated_stock", 50)
    reorder_point = sim_data.get("simulated_reorder_point", 20)

    # Dimension scores
    velocity = compute_sales_velocity(rating_count, max_rating_count)
    health = compute_stock_health(stock, reorder_point)
    urgency = compute_urgency(stock, reorder_point)
    turnover = compute_turnover_rate(rating_count, max_rating_count)

    # Weighted composite
    c_velocity = velocity * W_VELOCITY * 100
    c_health = health * W_HEALTH * 100
    c_urgency = urgency * W_URGENCY * 100
    c_turnover = turnover * W_TURNOVER * 100
    composite = round(c_velocity + c_health + c_urgency + c_turnover, 2)

    # Estimating demand
    avg_daily = max(0.5, rating_count / 365.0)
    max_daily = avg_daily * 2.5

    eoq = compute_eoq(rating_count, price)
    safety_stock = compute_safety_stock(max_daily, avg_daily)
    suggested_reorder = max(eoq, safety_stock + max(0, reorder_point - stock))

    # Action determination
    if stock <= 0:
        action = "\u7d27\u6025\u8865\u8d27"
        priority = 1
    elif stock <= reorder_point * 0.5:
        action = "\u5efa\u8bae\u7acb\u5373\u8865\u8d27"
        priority = 2
    elif stock <= reorder_point:
        action = "\u89c2\u5bdf\u8865\u8d27"
        priority = 3
    elif stock >= reorder_point * 3:
        action = "\u5e93\u5b58\u5145\u8db3\uff0c\u6682\u65e0\u9700\u6c42"
        priority = 5
    else:
        action = "\u5e93\u5b58\u6b63\u5e38"
        priority = 4

    return {
        "product_id": pid,
        "title": title,
        "price": price,
        "rating_count": rating_count,
        "sales_velocity_score": round(velocity, 3),
        "stock_health_score": round(health, 3),
        "replenishment_urgency_score": round(urgency, 3),
        "turnover_rate_score": round(turnover, 3),
        "contributions": {
            "velocity": round(c_velocity, 2),
            "health": round(c_health, 2),
            "urgency": round(c_urgency, 2),
            "turnover": round(c_turnover, 2),
        },
        "composite_score": composite,
        "simulated_stock": stock,
        "simulated_reorder_point": reorder_point,
        "eoq": eoq,
        "safety_stock": safety_stock,
        "suggested_reorder_qty": suggested_reorder,
        "suggested_action": action,
        "priority": priority,
    }