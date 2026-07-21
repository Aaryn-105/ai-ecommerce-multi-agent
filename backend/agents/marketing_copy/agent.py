"""Marketing Copy Agent — generate tagline, bullets, description, and social copy.

Two modes:
- **LLM mode**: builds a structured prompt from the product + marketing brief,
  calls OpenAI to generate all four copy types concurrently.
- **Template fallback**: uses template_providers when no API key is configured.
"""
from __future__ import annotations
import asyncio
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
    "你是一位资深的电商营销文案策划，擅长为不同品类商品撰写差异化、可量化、能刺激转化率的中文文案。\n\n"
    "严格要求：\n"
    "1) 禁止套用'品质优选/价格实惠/好评如潮/快速发货/好物推荐'等通用模板话术；每一句文案都必须与该商品的真实属性强相关。\n"
    "2) 优先从商品标题、描述、关键词中提取差异化卖点（如品类特点、适用场景、功能优势），禁止空泛描述。\n"
    "3) 文案必须使用中文输出；面向C端消费者，语气真诚、可信、有画面感。\n"
    "4) tagline ≤ 20 字，要包含商品核心定位；bullets 4-5 条，每条不超过 22 字，要具体、可量化、有差异化；description 180-260 字，必须包含具体使用场景与差异化优势；social 80-120 字，可直接复制到微博/小红书。\n"
    "5) 严格返回合法 JSON，对象包含 tagline / bullets / description / social 四个字段，不要输出任何 JSON 之外的文本、Markdown 代码块或<think>标签。\n\n"
    "输出 JSON 示例结构（仅展示字段，内容要根据商品改写）：\n"
    "{\n"
    '  "tagline": "<≤20字、含核心卖点>",\n'
    '  "bullets": "<4-5条要点，\\n分隔，每条≤22字>",\n'
    '  "description": "<180-260字产品描述，含具体场景>",\n'
    '  "social": "<80-120字社交媒体文案>"\n'
    "}"
)

_LLM_USER_TEMPLATE = (
    "商品信息（请基于以下真实数据撰写差异化文案，不要凭空编造参数）：\n"
    "- 标题：{title}\n"
    "- 品类：{category}\n"
    "- 价格：${price}\n"
    "- 用户评分：{rating}/5（来自 {review_count} 条评价）\n"
    "- 商品描述：{description}\n\n"
    "营销简报：\n"
    "- 语气风格：{tone}\n"
    "- 核心卖点（基于商品描述提取）：{core_selling_point}\n"
    "- 定价策略：{price_strategy}\n"
    "- 可验证的卖点列表：\n{selling_points}\n\n"
    "差异化要求：\n"
    "- tagline 必须在 20 字以内、体现品类核心定位（如场景/功能/人群），禁止使用'品质优选''热销推荐'等空泛词。\n"
    "- bullets 4-5 条，**每条都要引用商品标题/描述/关键词中的真实信息**（如适用季节、材质、场景、功能），并**避免重复**。\n"
    "- description 必须用 180-260 字写一个具体场景下的产品价值故事，至少包含 1 个具体使用场景。\n"
    "- social 写适合小红书/微博的口语化文案，可使用 emoji，但不要复制 description。\n\n"
    "请严格按 JSON 返回 4 个字段，不要包含其他文本。"
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

        # ── Filter by user-mentioned product title (if any) ──
        user_query = (
            input_data.get("user_query")
            or context.get("user_query")
            or ""
        )
        products = self._filter_by_user_query(products, user_query)

        if not products:
            return {"copies": [], "total_generated": 0, "summary": "没有可用的商品数据。"}

        pos_lookup: dict[int, dict[str, Any]] = {}
        for pos in positioning_data:
            pid = pos.get("product_id", 0) or pos.get("id", 0)
            if pid:
                pos_lookup[pid] = pos

        llm_ok = self._llm_available
        prepared: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for product in products:
            pid = product.get("id", 0)
            position = pos_lookup.get(pid)
            brief = build_marketing_brief(product, position)
            prepared.append((product, brief))

        if llm_ok:
            generated = await asyncio.gather(
                *(self._llm_generate_copies(product, brief) for product, brief in prepared),
                return_exceptions=True,
            )
        else:
            generated = [template_copies(product, brief) for product, brief in prepared]

        copies_result: list[dict[str, Any]] = []
        for (product, brief), raw_result in zip(prepared, generated):
            pid = product.get("id", 0)
            title = product.get("title", "Unknown")
            category = product.get("category", "")
            raw_copies = (
                template_copies(product, brief)
                if isinstance(raw_result, BaseException)
                else raw_result
            )
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
            "llm_calls": len(prepared) if llm_ok else 0,
            "summary": summary,
        }

    @staticmethod
    def _filter_by_user_query(products, user_query):
        """If user mentions a specific product title in the query, keep only that one.
        Recognises patterns like:
          - "Mens Cotton Jacket这个产品"
          - "给Mens Cotton Jacket写文案"
          - "id=3" / "product_id=3"
        Falls back to all products when no specific title is detected.
        """
        if not products or not user_query:
            return products
        q_lower = user_query.strip().lower()
        import re as _re
        # 1) Match by product id
        id_match = _re.search(r"\b(?:id|product_id)\s*[=:]\s*(\d+)", q_lower)
        if id_match:
            pid = int(id_match.group(1))
            hit = [p for p in products if p.get("id") == pid]
            if hit:
                return hit
        # 2) Match by case-insensitive title substring (>= 6 chars)
        for p in products:
            title = (p.get("title") or "").strip()
            if len(title) >= 6 and title.lower() in q_lower:
                return [p]
        # 3) Fuzzy token overlap (>= 2 shared significant tokens)
        stop = {"the","a","an","for","with","and","of","to","in","on","at","by","this","that","product","item","good","help","generate","write","analyze","分析","生成","文案","营销","写","帮我","给","这个","这件","该","商品","产品"}
        q_tokens = set(t.lower() for t in _re.findall(r"[a-zA-Z\u4e00-\u9fff]+", q_lower) if len(t) >= 2 and t.lower() not in stop)
        if q_tokens:
            best = None
            best_score = 0
            for p in products:
                title = (p.get("title") or "")
                t_tokens = set(t.lower() for t in _re.findall(r"[a-zA-Z\u4e00-\u9fff]+", title.lower()) if len(t) >= 2 and t.lower() not in stop)
                score = len(q_tokens & t_tokens)
                if score > best_score:
                    best_score = score
                    best = p
            if best and best_score >= 2:
                return [best]
        return products


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
        # Use full description (truncate only at 600 chars to stay under token limits)
        description = (product.get("description", "") or "")[:600]
        tone = brief.get("tone", "专业")
        core_sp = brief.get("core_selling_point", "") or "商品核心卖点待提取"
        price_strat = brief.get("price_strategy", "")
        selling_points = brief.get("selling_points", []) or []
        # Format selling points as numbered list for LLM clarity
        selling_points_text = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(selling_points))

        user_msg = _LLM_USER_TEMPLATE.format(
            title=title, category=category, price=price,
            rating=rating, review_count=review_count,
            description=description, tone=tone,
            core_selling_point=core_sp, price_strategy=price_strat,
            selling_points=selling_points_text,
        )

        result = await self._llm.chat(
            system_prompt=_LLM_SYSTEM_PROMPT,
            user_message=user_msg,
            temperature=0.7,
            max_tokens=1500,
            json_mode=True,
            fallback=None,
        )

        # Robust parsing — accept either direct dict, or content wrapped in JSON
        parsed = self._extract_json(result)
        if parsed and parsed.get("tagline"):
            return {
                "tagline": str(parsed.get("tagline", "")).strip(),
                "bullets": str(parsed.get("bullets", "")).strip(),
                "description": str(parsed.get("description", "")).strip(),
                "social": str(parsed.get("social", "")).strip(),
            }

        # If LLM failed or returned unusable payload, use template fallback
        return template_copies(product, brief)

    @staticmethod
    def _extract_json(result):
        """Accept result as dict, string, or content with embedded JSON."""
        if isinstance(result, dict):
            return result
        if not isinstance(result, str):
            return None
        text = result.strip()
        if not text:
            return None
        # Strip markdown code blocks
        import re
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1)
        else:
            # find first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end+1]
        try:
            import json
            return json.loads(text)
        except Exception:
            return None

    async def run(self, agent_input) -> AgentResult:
        """Override run to correctly track LLM usage."""
        start = time.perf_counter()
        try:
            output = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
            error = None
            llm_used = output.get("llm_used", False)
            llm_calls = output.get("llm_calls", 0) if llm_used else 0
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
