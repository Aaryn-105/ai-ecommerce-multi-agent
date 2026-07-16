"""Marketing Copy Agent — generate tagline, bullets, description, and social copy.

Two modes:
- **LLM mode**: builds a structured prompt from the product + marketing brief,
  calls OpenAI to generate all four copy types concurrently.
- **Template fallback**: uses template_providers when no API key is configured.
"""
from __future__ import annotations
import time
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.marketing_copy.brief_generator import build_marketing_brief
from backend.agents.marketing_copy.template_providers import generate_all_copies as template_copies
from backend.agents.marketing_copy.validator import validate_copy_set
from backend.core.config import settings
from backend.models.schemas import AgentResult, ExecutionMeta
from backend.services.llm_service import LLMService

_LLM_SYSTEM_PROMPT = (
    "你是一位专业的电商营销文案撰写专家。根据提供的商品信息和营销简报，"
    "生成中文营销文案。要求：\n"
    "1. 语言简洁有力，符合电商场景\n"
    "2. 突出商品核心卖点和差异化优势\n"
    "3. 针对目标用户群体调整语气风格\n"
    "4. 输出严格的 JSON 格式，不要包含任何额外文字\n\n"
    "输出 JSON 结构：\n"
    "{\n"
    '  "tagline": "简短有力的广告语（15字以内）",\n'
    '  "bullets": "4-5条卖点要点（每行一条，用\\n分隔）",\n'
    '  "description": "200字以内的产品描述",\n'
    '  "social": "适合社交媒体的推广文案（100字以内）"\n'
    "}"
)

_LLM_USER_TEMPLATE = (
    '商品信息：\n'
    '- 标题：{title}\n'
    '- 品类：{category}\n'
    '- 价格：${price}\n'
    '- 评分：{rating}/5（共{review_count}条评价）\n'
    '- 描述：{description}\n\n'
    '营销简报：\n'
    '- 语气风格：{tone}\n'
    '- 核心卖点：{core_selling_point}\n'
    '- 定价策略：{price_strategy}\n'
    '- 卖点列表：{selling_points}\n\n'
    '请严格按照 JSON 格式输出。'
)


class MarketingCopyAgent(BaseAgent):
    """Generate marketing copy for selected products.

    Flow::

        products [+ positioning_data]
            → Step 1: Build marketing brief (tone, strategy, selling points)
            → Step 2: LLM generates copies (when API key is set)
            → Step 3: Validate & fallback to template engine
            → Step 4: Format output

    When ``OPENAI_API_KEY`` is set, uses LLM for copy generation.
    Falls back to template_providers when key is empty.
    """

    agent_name = "marketing_copy"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service or LLMService()

    @property
    def _llm_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        products: list[dict[str, Any]] = (
            input_data.get("products")
            or (context.get("product_analysis", {}).get("output_data", {}).get("selected_products"))
            or input_data.get("selected_products")
            or (context.get("competitor_analysis", {}).get("output_data", {}).get("product_positioning"))
            or []
        )

        positioning_data: list[dict[str, Any]] = (
            input_data.get("positioning_data")
            or (context.get("competitor_analysis", {}).get("output_data", {}).get("product_positioning"))
            or []
        )

        if not products:
            return {"copies": [], "total_generated": 0, "summary": "没有可用的商品数据。"}

        pos_lookup: dict[int, dict[str, Any]] = {}
        for pos in positioning_data:
            pid = pos.get("product_id", 0) or pos.get("id", 0)
            if pid:
                pos_lookup[pid] = pos

        copies_result: list[dict[str, Any]] = []
        llm_ok = self._llm_available

        for product in products:
            pid = product.get("id", 0)
            title = product.get("title", "Unknown")
            category = product.get("category", "")
            position = pos_lookup.get(pid)

            # Step 1: Build marketing brief
            brief = build_marketing_brief(product, position)

            # Step 2: Generate copies (LLM → template fallback)
            if llm_ok:
                raw_copies = await self._llm_generate_copies(product, brief)
            else:
                raw_copies = template_copies(product, brief)

            # Step 3: Validate
            validated = validate_copy_set(raw_copies, product)

            copies_result.append({
                "product_id": pid,
                "title": title,
                "category": category,
                "generated_copies": {
                    "tagline": validated.get("tagline", ""),
                    "bullets": validated.get("bullets", ""),
                    "description": validated.get("description", ""),
                    "social": validated.get("social", ""),
                },
                "copy_strategy": {
                    "tone": brief.get("tone", ""),
                    "core_selling_point": brief.get("core_selling_point", ""),
                    "price_strategy": brief.get("price_strategy", ""),
                },
                "sources_used": ["LLM"] if llm_ok else ["模板引擎"],
            })

        summary = (
            f"为{len(copies_result)}款商品生成了营销文案，"
            f"涵盖{len(set(c.get('category','') for c in copies_result))}个品类"
        )

        return {
            "copies": copies_result,
            "total_generated": len(copies_result),
            "llm_used": llm_ok,
            "summary": summary,
        }

    async def _llm_generate_copies(
        self,
        product: dict[str, Any],
        brief: dict[str, Any],
    ) -> dict[str, str]:
        """Generate copies via LLM, fallback to templates on failure."""
        title = product.get("title", "")
        category = product.get("category", "")
        price = product.get("price", 0)
        rating_obj = product.get("rating", {}) or {}
        rating = rating_obj.get("rate", 0)
        review_count = rating_obj.get("count", 0)
        description = product.get("description", "")[:200]
        tone = brief.get("tone", "专业")
        core_sp = brief.get("core_selling_point", "")
        price_strat = brief.get("price_strategy", "")
        selling_points = "；".join(brief.get("selling_points", []))

        user_msg = _LLM_USER_TEMPLATE.format(
            title=title, category=category, price=price,
            rating=rating, review_count=review_count,
            description=description, tone=tone,
            core_selling_point=core_sp, price_strategy=price_strat,
            selling_points=selling_points,
        )

        result = await self._llm.chat(
            system_prompt=_LLM_SYSTEM_PROMPT,
            user_message=user_msg,
            temperature=0.7,
            max_tokens=1024,
            json_mode=True,
            fallback=None,
        )

        if isinstance(result, dict) and result.get("tagline"):
            return {
                "tagline": str(result.get("tagline", "")),
                "bullets": str(result.get("bullets", "")),
                "description": str(result.get("description", "")),
                "social": str(result.get("social", "")),
            }

        # If LLM failed, use template fallback
        return template_copies(product, brief)

    async def run(self, agent_input) -> AgentResult:
        """Override run to correctly track LLM usage."""
        start = time.perf_counter()
        try:
            output = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
            error = None
            llm_used = output.get("llm_used", False)
            llm_calls = output.get("total_generated", 0) if llm_used else 0
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