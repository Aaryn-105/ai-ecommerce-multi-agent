"""Inventory Agent \u2014 analyse stock levels, compute replenishment plans.

Uses 4-dimension scoring + EOQ + safety stock calculations.
Pure code \u2014 zero LLM calls.
"""
from __future__ import annotations
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.inventory.models import score_inventory
from backend.services.analysis_insight import AnalysisInsightService
from backend.services.llm_service import LLMService


class InventoryAgent(BaseAgent):
    """Analyse inventory and generate replenishment plans.

    Flow::

        candidate_products
            \u2192 Step 1: compute global max rating count
            \u2192 Step 2: score each product (4 dimensions + EOQ + safety stock)
            \u2192 Step 3: rank by composite_score, classify urgency
            \u2192 Step 4: summarise

    Pure code \u2014 zero LLM calls.
    """

    agent_name = "inventory"

    def __init__(self, top_n: int = 20, llm_service: LLMService | None = None) -> None:
        self._top_n = top_n
        self._insight = AnalysisInsightService(llm_service)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        candidate_products: list[dict[str, Any]] = (
            input_data.get("candidate_products")
            or input_data.get("products")
            or (context.get("product_analysis", {}).get("output_data", {}).get("selected_products"))
            or (context.get("product_analysis", {}).get("output_data", {}).get("all_products"))
            or []
        )

        if not candidate_products:
            return {
                "replenishment_plans": [],
                "overall_summary": {
                    "urgent_count": 0,
                    "normal_count": 0,
                    "no_action_count": 0,
                    "total_order_value": 0.0,
                },
            }

        # Step 1: global max
        max_rating_count = max(
            (p.get("rating", {}) or {}).get("count", 0) for p in candidate_products
        ) or 1

        # Step 2: score each product
        scored_products = []
        for p in candidate_products:
            try:
                result = score_inventory(p, max_rating_count)
                scored_products.append(result)
            except Exception:
                continue

        # Step 3: rank by composite desc, then urgency
        scored_products.sort(key=lambda x: (-x["composite_score"], x["priority"]))

        top = scored_products[:self._top_n]

        # Build output
        plans = []
        urgent = normal = no_action = 0
        total_value = 0.0

        for sp in top:
            action = sp["suggested_action"]
            if sp["priority"] <= 2:
                urgent += 1
            elif sp["priority"] <= 4:
                normal += 1
            else:
                no_action += 1

            total_value += sp["suggested_reorder_qty"] * sp["price"]

            plans.append({
                "product_id": sp["product_id"],
                "title": sp["title"],
                "sales_velocity_score": sp["sales_velocity_score"],
                "stock_health_score": sp["stock_health_score"],
                "replenishment_urgency_score": sp["replenishment_urgency_score"],
                "turnover_rate_score": sp["turnover_rate_score"],
                "composite_score": sp["composite_score"],
                "suggested_reorder_qty": sp["suggested_reorder_qty"],
                "suggested_action": action,
                "priority": sp["priority"],
            })

        summary = (
            f"\u5e93\u5b58\u5206\u6790\u5b8c\u6210\uff1a\u5171\u8bc4\u4f30{len(scored_products)}\u6b3e\u5546\u54c1\u3002"
            f"\u7d27\u6025\u8865\u8d27{urgent}\u6b3e\uff0c\u5e38\u89c4\u7ef4\u62a4{normal}\u6b3e\uff0c"
            f"\u6682\u65e0\u9700\u6c42{no_action}\u6b3e\u3002"
            f"\u5efa\u8bae\u8865\u8d27\u603b\u91d1\u989d${total_value:.2f}"
        )

        output = {
            "replenishment_plans": plans,
            "overall_summary": {
                "urgent_count": urgent,
                "normal_count": normal,
                "no_action_count": no_action,
                "total_order_value": round(total_value, 2),
            },
            "summary": summary,
        }
        query = str(input_data.get("user_query") or context.get("user_query") or "")
        urgent_plan = plans[0] if plans else {}
        urgent_title = str(urgent_plan.get("title") or "暂无")
        urgent_action = str(urgent_plan.get("suggested_action") or "暂无")
        insight = await self._insight.generate(
            agent_name=self.agent_name,
            user_query=query,
            evidence={
                "overall_summary": output["overall_summary"],
                "top_replenishment_plans": plans[:8],
            },
            fallback_insight=(
                f"当前模型将{urgent}款商品列为紧急补货，最高优先级商品为{urgent_title}；"
                "建议先核对真实库存和近30天订单，再按资金占用分批下单，避免仅依据评价数代理需求。"
            ),
            fallback_findings=[
                f"共评估{len(scored_products)}款商品，紧急补货{urgent}款、常规维护{normal}款。",
                f"模型建议补货总金额为${total_value:.2f}。",
                f"最高优先级商品建议动作：{urgent_action}。",
            ],
            limitations=["当前库存与补货需求由评价数代理推导，不是仓储系统的实时库存和订单数据。"],
        )
        output.update(insight)
        return output
