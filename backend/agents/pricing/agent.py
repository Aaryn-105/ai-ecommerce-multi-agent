"""Pricing Agent \u2014 compute optimal prices using 3-factor model.

Reads product, market benchmark, and competitive position data.
Pure code \u2014 zero LLM calls.
"""
from __future__ import annotations
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.pricing.models import compute_suggested_price
from backend.services.analysis_insight import AnalysisInsightService
from backend.services.llm_service import LLMService


class PricingAgent(BaseAgent):
    """Analyse pricing and suggest optimal price.

    Flow::

        target_product + market_benchmark + competitive_position
            \u2192 Step 1: Compute cost-plus price (30 %)
            \u2192 Step 2: Compute competitor-based price (40 %)
            \u2192 Step 3: Compute value-based price (30 %)
            \u2192 Step 4: Dynamic factor + floor/ceiling
            \u2192 Step 5: Classify strategy

    Pure code \u2014 zero LLM calls.
    """

    agent_name = "pricing"

    def __init__(self, margin: float = 0.25, llm_service: LLMService | None = None) -> None:
        self._margin = margin
        self._insight = AnalysisInsightService(llm_service)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Accept target_product from input_data or context pipeline
        target_product: dict[str, Any] = (
            input_data.get("target_product")
            or (context.get("competitor_analysis", {}).get("output_data", {}).get("product_positioning", [None]) or [None])[0]
            or input_data.get("product")
            or {}
        )

        # If we have multiple products, process each
        products: list[dict[str, Any]] = input_data.get("products", [])
        if not products:
            products = context.get("product_analysis", {}).get("output_data", {}).get("selected_products", [])
        if not products and target_product:
            products = [target_product]

        if not products:
            return {
                "pricing_results": [],
                "summary": "\u6ca1\u6709\u53ef\u7528\u7684\u4ea7\u54c1\u6570\u636e\u8fdb\u884c\u5b9a\u4ef7\u5206\u6790\u3002",
            }

        # Build market benchmarks from context
        market_benchmarks: dict[str, dict[str, Any]] = (
            context.get("competitor_analysis", {}).get("output_data", {}).get("category_benchmarks", {})
            or input_data.get("market_benchmarks", {})
        )

        # Build position lookup if available
        positioning: list[dict[str, Any]] = (
            context.get("competitor_analysis", {}).get("output_data", {}).get("product_positioning", [])
            or input_data.get("positioning_data", [])
        )
        pos_lookup: dict[int, dict[str, Any]] = {}
        for pos in positioning:
            pid = pos.get("product_id", 0) or pos.get("id", 0)
            if pid:
                pos_lookup[pid] = pos

        results = []
        for product in products:
            pid = product.get("id", 0)
            title = product.get("title", "Unknown")
            category = product.get("category", "unknown")
            current_price = max(product.get("price", 0), 0.01)

            # Get market benchmark for this category
            market_benchmark = market_benchmarks.get(category, {})

            # Get competitive position for this product
            competitive_position = pos_lookup.get(pid) or {
                "rating": (product.get("rating", {}) or {}).get("rate", 0),
                "competitive_score": 50,
                "rating_percentile": 0.5,
                "price_percentile": 0.5,
                "advantages": [],
                "disadvantages": [],
                "differentiators": [],
            }

            # Compute pricing
            pricing = compute_suggested_price(
                current_price=current_price,
                market_benchmark=market_benchmark,
                competitive_position=competitive_position,
                margin=self._margin,
            )

            results.append({
                "product_id": pid,
                "title": title,
                "category": category,
                "current_price": current_price,
                "suggested_price": pricing["suggested_price"],
                "price_change": pricing["price_change"],
                "strategy": pricing["strategy"],
                "confidence": pricing["confidence"],
                "reason": pricing["reason"],
                "factor_breakdown": pricing["factor_breakdown"],
            })

        # Summary
        strategies: dict[str, int] = {}
        for r in results:
            s = r["strategy"]
            strategies[s] = strategies.get(s, 0) + 1

        strategy_desc = "\uff0c".join(f"{s}:{c}\u6b3e" for s, c in sorted(strategies.items()))
        summary = (
            f"\u5b9a\u4ef7\u5206\u6790\u5b8c\u6210\uff1a\u5bf9{len(results)}\u6b3e\u5546\u54c1\u8fdb\u884c\u4e86\u4e09\u56e0\u5b50\u5b9a\u4ef7\u6a21\u578b\u5206\u6790\u3002"
            f"\u7b56\u7565\u5206\u5e03\uff1a{strategy_desc}"
        )

        output = {
            "pricing_results": results,
            "summary": summary,
        }
        query = str(input_data.get("user_query") or context.get("user_query") or "")
        top_result = results[0] if results else {}
        top_title = str(top_result.get("title") or "重点商品")
        top_price = top_result.get("suggested_price", 0)
        top_change = top_result.get("price_change", 0)
        insight = await self._insight.generate(
            agent_name=self.agent_name,
            user_query=query,
            evidence={
                "pricing_results": results[:8],
                "strategy_distribution": strategies,
            },
            fallback_insight=(
                f'{top_title}建议价格为{top_price}，当前价格变化{top_change}%；'
                '建议先以小流量测试价格弹性，再根据转化率、毛利和竞品价格分位做二次调整。'
            ),
            fallback_findings=[
                f'本次完成{len(results)}款商品的三因子定价分析。',
                f'策略分布：{strategy_desc}。',
                f'首个重点商品建议价为{top_price}。',
            ],
            limitations=['模型缺少成本、毛利、广告费和真实转化率，建议价不能直接视为最终财务定价。'],
        )
        output.update(insight)
        return output
