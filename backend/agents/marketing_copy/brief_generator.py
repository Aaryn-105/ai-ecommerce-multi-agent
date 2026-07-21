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


def _extract_distinctive_keywords(title: str, description: str, max_kw: int = 6) -> list[str]:
    """从商品标题/描述中提取能体现商品特色的关键词。"""
    import re
    text = f"{title} {description or ''}".lower()
    # 常见停用词
    stop = {
        "the","a","an","and","or","but","of","for","to","in","on","at","by","with",
        "is","are","was","were","be","been","being","have","has","had","do","does",
        "did","will","would","should","can","could","may","might","must",
        "this","that","these","those","i","you","he","she","it","we","they",
        "as","if","than","then","so","such","no","not","only","very","more","most",
        "from","your","our","their","its","his","her","about","into","over","after",
        "before","up","down","out","off","just","also","any","all","some","one","two",
        "new","good","great","perfect","best","high","low","small","large","big",
        "适合","这件","我们","您","的","了","是","在","和","与","或","也","就","都",
    }
    tokens = re.findall(r"[a-zA-Z\u4e00-\u9fff]+", text)
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        if tok in stop or len(tok) < 2:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        keywords.append(tok)
        if len(keywords) >= max_kw:
            break
    return keywords


def _build_core_selling_point(product: dict[str, Any]) -> str:
    """基于商品真实数据构建差异化核心卖点（不再使用占位符）。"""
    title = (product.get("title") or "").strip()
    description = (product.get("description") or "").strip()
    rating_obj = product.get("rating") or {}
    rate = rating_obj.get("rate", 0)
    count = rating_obj.get("count", 0)

    # 1) 从 description 抓取第一条关键事实
    if description:
        first_sentence = description.replace("\n", " ").split(".")[0].strip()
        if first_sentence and len(first_sentence) >= 8:
            if len(first_sentence) > 80:
                first_sentence = first_sentence[:80].rstrip() + "…"
            return first_sentence

    # 2) 退而求其次，用标题 + 评分
    if rate and count:
        return f"{title}：评分 {rate}/5，基于{count}条真实用户评价"
    if title:
        return title
    return "优质商品"


def extract_selling_points(product: dict[str, Any]) -> list[str]:
    """从商品真实数据提取可验证的卖点。"""
    points: list[str] = []
    title = (product.get("title") or "").strip()
    category = (product.get("category") or "").strip()
    price = product.get("price", 0)
    rating = product.get("rating") or {}
    rate = rating.get("rate", 0)
    count = rating.get("count", 0)
    description = (product.get("description") or "").strip()

    # Point 1: 用户评分事实
    if rate and count:
        if rate >= 4.5:
            points.append(f"{rate}/5高分商品，已有{count}位用户验证口碑")
        elif rate >= 4.0:
            points.append(f"评分 {rate}/5，{count}条评价好评为主")
        elif rate >= 3.0:
            points.append(f"评分 {rate}/5，仍有提升空间")
        else:
            points.append(f"评分 {rate}/5，定位亲民")
    elif rate:
        points.append(f"评分 {rate}/5")

    # Point 2: 价格事实
    if price:
        if price < 30:
            points.append(f"售价仅 ${price:.2f}，入门门槛低")
        elif price <= 100:
            points.append(f"定价 ${price:.2f}，处于主流消费区间")
        else:
            points.append(f"定价 ${price:.2f}，定位偏中高端")

    # Point 3: 描述中的差异化事实
    if description and len(description) > 50:
        # 提取描述中最长的可读短语作为差异化信息
        kws = _extract_distinctive_keywords(title, description, max_kw=4)
        if kws:
            points.append("产品关键词：" + "、".join(kws[:4]))

    # Point 4: 类目说明
    if category:
        points.append(f"所属类目：{category}")

    # Point 5: 标题关键词
    if title:
        words = [w for w in title.split() if len(w) >= 3][:3]
        if words:
            points.append("标题强调：" + " ".join(words))

    return points[:5]


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

    # Add competitor insights if available
    advantages = position.get("advantages", []) if position else []
    if advantages:
        selling_points = list(advantages[:2]) + selling_points
        selling_points = selling_points[:5]

    # Core selling point — NEVER use placeholder text
    core = _build_core_selling_point(product)
    if advantages:
        # Prefer first concrete advantage if it is non-trivial
        first_adv = advantages[0]
        if first_adv and len(first_adv) >= 6 and "建议" not in first_adv[:4]:
            core = f"{first_adv}（{core[:60]}）"

    return {
        "tone": tone,
        "core_selling_point": core,
        "price_strategy": price_strategy,
        "selling_points": selling_points,
    }
