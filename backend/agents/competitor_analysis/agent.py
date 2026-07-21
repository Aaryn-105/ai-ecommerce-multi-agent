"""Competitor Analysis Agent — benchmark products against category peers.

Uses 5-dimension Min-Max scoring within each category group.
Pure code — zero LLM calls.
"""
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.services.analysis_insight import AnalysisInsightService
from backend.agents.competitor_analysis.scorer import (
    build_category_benchmark,
    compute_category_extrema,
    generate_insights,
    score_product_competitive,
)
from backend.services.llm_service import LLMService


class CompetitorAnalysisAgent(BaseAgent):
    """Analyse competitive positioning within each product category.

    Flow::

        all_products + selected_products
            → Step 1: group by category, compute benchmarks
            → Step 2: score each selected product within its category
            → Step 3: generate insights (advantages / disadvantages / differentiators)
            → Step 4: format output with market summary

    Deterministic benchmarking is preserved; an optional LLM adds evidence-bound insight.
    """

    agent_name = "competitor_analysis"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._insight = AnalysisInsightService(llm_service)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Accept data from input_data or context (orchestrator pipeline)
        all_products: list[dict[str, Any]] = (
            input_data.get("all_products")
            or context.get("all_products")
            or (context.get("product_analysis", {}).get("output_data", {}).get("all_products"))
            or []
        )
        selected_products: list[dict[str, Any]] = (
            input_data.get("selected_products")
            or (context.get("product_analysis", {}).get("output_data", {}).get("selected_products"))
            or input_data.get("products")
            or []
        )

        category_filter = input_data.get("category")
        if category_filter:
            allowed_categories = (
                {category_filter}
                if isinstance(category_filter, str)
                else set(category_filter)
            )
            all_products = [
                product
                for product in all_products
                if product.get("category") in allowed_categories
            ]
            selected_products = [
                product
                for product in selected_products
                if product.get("category") in allowed_categories
            ]

        if not all_products:
            # Fallback: use selected_products as all_products
            all_products = selected_products
            if not all_products:
                return {
                    "category_benchmarks": {},
                    "product_positioning": [],
                    "analysis_scope": {
                        "category": category_filter or "全部商品",
                        "matched_count": 0,
                        "data_source": "FakeStore API",
                    },
                    "market_summary": f"真实数据中未找到{category_filter or '目标'}类目商品，无法进行竞品对比。",
                }

        # ── Step 1: Group by category & compute benchmarks ──
        cat_groups: dict[str, list[dict[str, Any]]] = {}
        for p in all_products:
            cat = p.get("category", "unknown")
            cat_groups.setdefault(cat, []).append(p)

        category_benchmarks: dict[str, dict[str, Any]] = {}
        category_extrema: dict[str, dict[str, dict[str, float]]] = {}
        for cat, prods in cat_groups.items():
            category_benchmarks[cat] = build_category_benchmark(prods)
            category_extrema[cat] = compute_category_extrema(prods)

        # ── Step 2 & 3: Score selected products within their category ──
        product_positioning: list[dict[str, Any]] = []

        for sp in selected_products:
            pid = sp.get("id", 0)
            title = sp.get("title", "Unknown")
            category = sp.get("category", "unknown")
            price = sp.get("price", 0.0)
            rating = sp.get("rating", {}) or {}
            rate_val = rating.get("rate", 0.0)

            if "original_rating" in sp:
                rating = sp.get("original_rating", {})
                rate_val = rating.get("rate", 0.0)

            # Find the full product data in all_products
            full_product = next(
                (p for p in all_products if p.get("id") == pid),
                sp,
            )

            extrema = category_extrema.get(category)
            if not extrema:
                continue

            # Score
            scored = score_product_competitive(full_product, extrema)
            bench = category_benchmarks.get(category, {})
            avg_price = bench.get("avg_price", price)
            avg_rating = bench.get("avg_rating", rate_val)

            # Price label
            price_vs_avg = ((price - avg_price) / max(avg_price, 0.01)) * 100
            if price_vs_avg < -10:
                price_label = "低价"
            elif price_vs_avg > 10:
                price_label = "高价"
            else:
                price_label = "中等"

            # Price percentile
            cat_products = cat_groups.get(category, [])
            cat_prices = sorted([cp["price"] for cp in cat_products])
            if cat_prices and len(cat_prices) > 1:
                rank = sum(1 for cp in cat_prices if cp <= price) - 1
                price_pct = max(0.0, min(1.0, rank / (len(cat_prices) - 1)))
            else:
                price_pct = 0.5

            # Rating percentile
            cat_rates = sorted([cp["rating"]["rate"] for cp in cat_products])
            if cat_rates and len(cat_rates) > 1:
                rank_r = sum(1 for cr in cat_rates if cr <= rate_val) - 1
                rating_pct = max(0.0, min(1.0, rank_r / (len(cat_rates) - 1)))
            else:
                rating_pct = 0.5

            # Insights
            insights = generate_insights(
                scored["dimension_norms"],
                scored["contributions"],
            )

            product_positioning.append({
                "product_id": pid,
                "title": title,
                "category": category,
                "price": price,
                "category_avg_price": round(avg_price, 2),
                "price_label": price_label,
                "price_vs_avg_pct": round(price_vs_avg, 1),
                "rating": rate_val,
                "category_avg_rating": round(avg_rating, 2),
                "competitive_score": scored["competitive_score"],
                "dimension_norms": scored["dimension_norms"],
                "contributions": scored["contributions"],
                "price_percentile": round(price_pct, 3),
                "rating_percentile": round(rating_pct, 3),
                "advantages": insights["advantages"],
                "disadvantages": insights["disadvantages"],
                "differentiators": insights["differentiators"],
            })

        # Sort by competitive score descending
        product_positioning.sort(key=lambda x: -x["competitive_score"])

        # ── Step 4: Market summary ──
        cat_names = list(category_benchmarks.keys())
        total_products = sum(b["product_count"] for b in category_benchmarks.values())
        avg_comp = (
            round(sum(p["competitive_score"] for p in product_positioning) / max(len(product_positioning), 1), 1)
        )
        strong_count = sum(1 for p in product_positioning if p["competitive_score"] >= 70)
        weak_count = sum(1 for p in product_positioning if p["competitive_score"] < 40)

        market_summary = (
            f"分析了{total_products}款商品，涵盖{len(cat_names)}个品类：{'、'.join(cat_names)}。"
            f"重点商品综合竞争力评分均值{avg_comp}分，"
            f"其中竞争力较强（≥70分）{strong_count}款，竞争力偏弱（<40分）{weak_count}款。"
        )

        output = {
            "category_benchmarks": category_benchmarks,
            "product_positioning": product_positioning,
            "analysis_scope": {
                "category": category_filter or "全部商品",
                "matched_count": total_products,
                "data_source": "FakeStore API",
            },
            "market_summary": market_summary,
        }
        query = str(input_data.get("user_query") or context.get("user_query") or "")
        top_position = product_positioning[0] if product_positioning else {}
        insight = await self._insight.generate(
            agent_name=self.agent_name,
            user_query=query,
            evidence={
                "analysis_scope": output["analysis_scope"],
                "category_benchmarks": category_benchmarks,
                "top_positions": product_positioning[:6],
            },
            fallback_insight=(
                f"{top_position.get('title', '重点商品')}的竞争力评分为{top_position.get('competitive_score', 0)}分，"
                f"价格定位为{top_position.get('price_label', '未知')}；建议围绕评分优势建立差异化卖点，"
                "并用竞品价格分位验证用户对溢价的接受度。"
            ),
            fallback_findings=[
                f"本次覆盖{total_products}款商品，重点商品竞争力均值{avg_comp}分。",
                f"竞争力较强商品{strong_count}款，偏弱商品{weak_count}款。",
                f"目标类目基准覆盖：{'、'.join(cat_names) or '暂无'}。",
            ],
            limitations=["竞品基准来自FakeStore公开商品目录，不代表完整市场份额或实时竞品价格。"],
        )
        output.update(insight)
        return output
