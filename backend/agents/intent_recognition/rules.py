"""Three-level keyword matching engine for intent recognition.

Architecture
------------
Level 1 — Core e-commerce action words    (weight: high)
Level 2 — Product / category nouns        (weight: medium)
Level 3 — Domain operation verbs          (weight: medium)

Heuristic
---------
- Matches in ≥2 distinct levels  →  is_ecommerce_query = True
- Matches in 0–1 levels          →  uncertain, caller should invoke LLM fallback
"""

from __future__ import annotations

# ── Keyword lists ────────────────────────────────────────

LEVEL_1_CORE: set[str] = {
    # 核心运营动作
    "选品", "铺货", "上架", "下架",
    "定价", "调价", "降价", "涨价",
    "促销", "打折", "清仓", "秒杀",
    "营销", "推广", "引流", "种草",
    "补货", "采购", "备货", "库存",
    "利润", "毛利", "净利", "营收", "成本",
    "销量", "销售额", "转化率", "复购率",
    "爆款", "热销", "滞销", "长尾",
    "竞争", "竞品", "对标", "差异化",
    "运营", "优化", "诊断",
    # English aliases
    "sku", "roi", "gmv",
}

LEVEL_2_CATEGORY: set[str] = {
    # 电商一级类目
    "电子产品", "电子", "数码", "电脑", "手机", "耳机", "显示器",
    "服装", "男装", "女装", "童装", "内衣", "鞋", "包", "配饰",
    "珠宝", "首饰", "手表", "饰品",
    "食品", "零食", "饮料", "生鲜", "保健品",
    "家居", "家具", "家纺", "厨具", "收纳",
    "运动", "健身", "户外", "骑行",
    "美妆", "护肤", "彩妆", "香水",
    "母婴", "玩具", "文具",
    "宠物", "宠物用品",
    "图书", "教育", "课程",
    # English / mixed
    "electronics", "clothing", "jewelery",
    "fashion", "beauty", "sports",
}

LEVEL_3_ACTION: set[str] = {
    # 分析/查询类操作
    "分析", "对比", "预测", "预估",
    "评估", "评价", "评测", "测评",
    "推荐", "挑选", "选择", "决策",
    "排名", "排行", "排行榜",
    "趋势", "走势", "行情",
    "报告", "建议", "方案",
    "怎么样", "哪个好", "值不值得", "划算吗",
    "值得买", "好不好", "怎么选",
    "看看", "查查", "查一下",
    "比价", "性价比",
}

# ── Matching engine ──────────────────────────────────────

class MatchResult:
    """Holds the outcome of a keyword scan."""

    matches: dict[str, list[str]]  # level_name → matched keywords
    total_levels_hit: int

    def __init__(self) -> None:
        self.matches = {}
        self.total_levels_hit = 0

    @property
    def all_keywords(self) -> list[str]:
        """Flat list of every keyword that matched."""
        kw: list[str] = []
        for lst in self.matches.values():
            kw.extend(lst)
        return kw

    @property
    def is_ecommerce(self) -> bool:
        """Heuristic: ≥2 distinct levels → likely e-commerce query."""
        return self.total_levels_hit >= 2


def match_keywords(message: str) -> MatchResult:
    """Scan *message* (lowercased) against all three keyword levels.

    Returns a :class:`MatchResult` with per-level hits.
    """
    result = MatchResult()
    text = message.lower()

    def _scan(level: set[str], label: str) -> list[str]:
        hits = [kw for kw in level if kw.lower() in text]
        return hits

    for label, level in [
        ("core", LEVEL_1_CORE),
        ("category", LEVEL_2_CATEGORY),
        ("action", LEVEL_3_ACTION),
    ]:
        hits = _scan(level, label)
        if hits:
            result.matches[label] = hits
            result.total_levels_hit += 1

    return result


def confidence_from_match(result: MatchResult) -> float:
    """Map match strength to a confidence score in [0, 1]."""
    if result.total_levels_hit >= 3:
        return 0.95
    if result.total_levels_hit == 2:
        return 0.80
    if result.total_levels_hit == 1:
        return 0.40
    return 0.0
