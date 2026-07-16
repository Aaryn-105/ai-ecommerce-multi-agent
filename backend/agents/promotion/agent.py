"""Promotion Agent — match products to promotion types and recommend plans.

Pipeline
--------
Step 1 — Match: evaluate all 8 promotion types against product data
Step 2 — Calculate: compute discount rate, promotion price, duration
Step 3 — Plan: generate multiple promotion plans from matches
Step 4 — Score: estimate ROI for each plan and rank
Step 5 — Recommend: select the best plan, surface alternatives

Copy generation: uses LLM when ``OPENAI_API_KEY`` is set; template fallback otherwise.
Pure code (non-LLM) for all other calculations.
"""
from __future__ import annotations
import time
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.promotion.matcher import match_promotions, PROMO_LABELS
from backend.agents.promotion.calculator import (
    compute_discount_rate,
    compute_promotion_price,
    compute_duration_days,
    compute_estimated_roi,
    compute_threshold_condition,
    generate_promotion_copy_preview as template_promo_copy,
    PROMO_CAMPAIGN_NAMES,
)
from backend.core.config import settings
from backend.models.schemas import AgentResult, ExecutionMeta
from backend.services.llm_service import LLMService

_LLM_PROMPT = (
    "你是一位电商促销文案撰写专家。根据以下促销方案信息，"
    "生成一段吸引人的中文促销文案（50字以内）。"
    "要求语气符合促销类型，突出优惠力度和紧迫感。\n"
    "直接输出文案文字，不要包含 JSON 或额外格式。"
)

_LLM_USER_TEMPLATE = (
    '商品：{title}\n'
    '品类：{category}\n'
    '原价：¥{original_price}\n'
    '促销类型：{promotion_type_label}\n'
    '促销价：¥{promotion_price}\n'
    '折扣力度：{discount_label}\n'
    '持续天数：{duration_days}天\n'
    '生成一段促销文案：'
)


class PromotionAgent(BaseAgent):
    """Analyse a product and recommend optimal promotion plans.

    When ``OPENAI_API_KEY`` is set, uses LLM to generate compelling
    promotion copy; falls back to template preview otherwise.

    Usage::

        agent = PromotionAgent()
        result = await agent.run(AgentInput(...))
    """

    agent_name = "promotion"

    def __init__(self, top_n: int = 5, llm_service: LLMService | None = None) -> None:
        self._top_n = top_n
        self._llm = llm_service or LLMService()

    @property
    def _llm_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # ── Resolve input product ────────────────────────
        product: dict[str, Any] = input_data.get("product", {})
        if not product:
            products = input_data.get("products", [])
            if products:
                product = products[0]
            else:
                pipeline = context.get("pricing", {}).get("output_data", {}).get("pricing_results", [])
                if pipeline:
                    product = pipeline[0]
        if not product:
            return {
                "promotion_result": {},
                "alternative_plans": [],
                "summary": "没有可用的产品数据进行促销分析。",
            }

        # ── Resolve context data ─────────────────────────
        category_avg_price = (
            input_data.get("category_avg_price", 0.0)
            or (context.get("competitor_analysis", {})
                 .get("output_data", {}).get("category_benchmarks", {})
                 .get(product.get("category", ""), {}).get("avg_price", 0.0))
        )

        inventory_status: dict[str, Any] | None = (
            input_data.get("inventory_status")
            or _find_in_inventory_context(context, product.get("id", 0))
        )

        pricing_context: dict[str, Any] | None = (
            input_data.get("pricing_context")
            or _find_in_pricing_context(context, product.get("id", 0))
        )

        marketing_context: dict[str, Any] | None = input_data.get("marketing_context")

        # ── Step 1: Match promotion types ────────────────
        matches = match_promotions(
            product, category_avg_price,
            inventory_status, pricing_context, marketing_context,
        )

        if not matches:
            return {
                "promotion_result": {},
                "alternative_plans": [],
                "summary": f"未找到适合商品「{product.get('title', '')}」的促销类型。",
            }

        # ── Step 2-3: Calculate & generate plans ─────────
        original_price = max(product.get("price", 0), 0.01)
        rating_count = (product.get("rating", {}) or {}).get("count", 0)
        product_title = product.get("title", "Unknown")
        llm_ok = self._llm_available

        plans = []
        for m in matches[:self._top_n]:
            ptype = m["promotion_type"]
            match_score = m["match_score"]

            discount_rate = compute_discount_rate(ptype, product, match_score)
            promo_price = compute_promotion_price(original_price, discount_rate)
            duration = compute_duration_days(ptype, discount_rate)
            roi = compute_estimated_roi(
                original_price, promo_price, discount_rate,
                ptype, rating_count,
            )
            condition = compute_threshold_condition(ptype, original_price)
            campaign_name = PROMO_CAMPAIGN_NAMES.get(ptype, "促销活动")
            discount_pct = round(discount_rate * 100)
            discount_label = f"{discount_pct}%折扣"

            # Generate promotion copy (LLM → template fallback)
            if llm_ok:
                promo_copy = await self._llm_generate_copy(
                    product, ptype, original_price, promo_price,
                    discount_label, duration, campaign_name,
                )
            else:
                promo_copy = template_promo_copy(
                    ptype, product_title, discount_rate, promo_price, campaign_name,
                )

            plans.append({
                "promotion_type": ptype,
                "campaign_name": campaign_name,
                "label": PROMO_LABELS.get(ptype, ptype),
                "original_price": original_price,
                "promotion_price": promo_price,
                "discount_rate": discount_rate,
                "discount_label": discount_label,
                "estimated_roi": roi,
                "promotion_copy": promo_copy,
                "duration_days": duration,
                "conditions": condition,
                "match_score": match_score,
                "match_reason": m["reason"],
            })

        # ── Step 4: Score & rank by ROI ──────────────────
        plans.sort(key=lambda p: p["estimated_roi"], reverse=True)

        # ── Step 5: Recommend ────────────────────────────
        recommended = plans[0] if plans else None
        alternatives = plans[1:] if len(plans) > 1 else []

        total_types = len(matches)
        top_label = recommended["label"] if recommended else "无"
        summary = (
            f"促销分析完成：商品「{product_title[:40]}」匹配到{total_types}种促销类型，"
            f"推荐策略为「{top_label}」"
            f"（折扣{recommended['discount_label'] if recommended else '—'}，"
            f"预估ROI {recommended['estimated_roi']:.2f}倍），"
            f"另有{len(alternatives)}个备选方案。"
        )

        return {
            "promotion_result": {
                "product_id": product.get("id", 0),
                "promotion_plan": recommended,
                "alternative_plans": alternatives,
                "recommended_plan_index": 0,
            },
            "alternative_plans": alternatives,
            "all_matched_types": [m["promotion_type"] for m in matches],
            "llm_used": llm_ok,
            "summary": summary,
        }

    async def _llm_generate_copy(
        self,
        product: dict[str, Any],
        promotion_type: str,
        original_price: float,
        promotion_price: float,
        discount_label: str,
        duration_days: int,
        campaign_name: str,
    ) -> str:
        """Generate promotion copy via LLM; fallback to template on failure."""
        title = product.get("title", "")[:60]
        category = product.get("category", "")
        type_label = PROMO_LABELS.get(promotion_type, promotion_type)

        user_msg = _LLM_USER_TEMPLATE.format(
            title=title, category=category,
            original_price=original_price,
            promotion_type_label=type_label,
            promotion_price=promotion_price,
            discount_label=discount_label,
            duration_days=duration_days,
        )

        result = await self._llm.chat(
            system_prompt=_LLM_PROMPT,
            user_message=user_msg,
            temperature=0.8,
            max_tokens=200,
            json_mode=False,
            fallback=None,
        )

        if result and isinstance(result, str) and len(result.strip()) > 5:
            return result.strip()[:200]

        # Fallback to template
        return template_promo_copy(
            promotion_type, title, 1.0 - (promotion_price / max(original_price, 0.01)),
            promotion_price, campaign_name,
        )

    async def run(self, agent_input) -> AgentResult:
        """Override run to correctly track LLM usage."""
        start = time.perf_counter()
        try:
            output = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
            error = None
            llm_used = output.get("llm_used", False)
            llm_calls = 1 if llm_used else 0
        except Exception as exc:
            output = {}
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            llm_used = False
            llm_calls = 0

        elapsed_ms = (time.perf_counter() - start) * 1000
        return AgentResult(
            task_id=agent_input.task_id,
            status=status,
            output_data=output,
            execution_meta=ExecutionMeta(
                execution_time_ms=round(elapsed_ms, 2),
                llm_used=llm_used,
                llm_calls=llm_calls,
            ),
            error=error,
        )


# ── Helpers ──────────────────────────────────────────────

def _find_in_inventory_context(context: dict[str, Any], product_id: int) -> dict[str, Any] | None:
    inv_output = context.get("inventory", {}).get("output_data", {})
    plans = inv_output.get("replenishment_plans", [])
    for plan in plans:
        if plan.get("product_id") == product_id:
            return plan
    return None


def _find_in_pricing_context(context: dict[str, Any], product_id: int) -> dict[str, Any] | None:
    pricing_results = context.get("pricing", {}).get("output_data", {}).get("pricing_results", [])
    for r in pricing_results:
        if r.get("product_id") == product_id:
            return r
    return None