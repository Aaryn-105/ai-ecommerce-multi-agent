from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services.llm_service import LLMService, _safe_json_loads

logger = logging.getLogger(__name__)


def _is_empty_data(sections) -> bool:
    """Detect whether all visible sections have matched_count == 0 (or no products at all)."""
    if not sections:
        return True
    for sec in sections.values():
        if not isinstance(sec, dict):
            continue
        scope = sec.get("analysis_scope") or {}
        matched = scope.get("matched_count") if isinstance(scope, dict) else None
        if matched is None:
            matched = sec.get("matched_count")
        if matched is None:
            for list_key in ("selected_products", "product_forecasts", "product_positioning", "items", "copies"):
                lst = sec.get(list_key)
                if isinstance(lst, list) and len(lst) > 0:
                    return False
            continue
        if isinstance(matched, (int, float)) and matched > 0:
            return False
    return True


_AGENT_LABELS = {
    "product_analysis": "选品策略",
    "trend_forecast": "趋势预测",
    "competitor_analysis": "竞品对比",
    "marketing_copy": "营销文案",
    "inventory": "库存建议",
    "pricing": "定价策略",
    "promotion": "促销推荐",
}

_AGENT_REPORT_TITLES = {
    "product_analysis": "选品加权评分模型",
    "trend_forecast": "时序趋势与运营节奏",
    "competitor_analysis": "竞品对比矩阵",
    "marketing_copy": "卖点与目标人群",
    "inventory": "库存健康度与补货优先级",
    "pricing": "定价模型与弹性",
    "promotion": "促销匹配与ROI估算",
}

_SOURCE_LABEL = "数据来源：FakeStore API v2.0 · 本地模拟销量日志"
_VERSION = "报告版本：v2.0 (Professional Analyst Edition)"


# ── Section ordering based on visible agents ─────────────────────────────────
# When only a few agents run, the report should emphasize them in different
# order rather than blindly following a fixed template.
_SECTION_ORDER = [
    "marketing_copy",       # content-first if asked for copy
    "product_analysis",
    "trend_forecast",
    "competitor_analysis",
    "pricing",
    "inventory",
    "promotion",
]


def _build_system_prompt(task_extensions: str) -> str:
    """Compose a focused, task-aware system prompt.

    The prompt is intentionally compact so the LLM stays focused and the
    response is more likely to parse as JSON.
    """
    return (
        "你是一位拥有 10 年以上经验的资深电商商业数据分析师，专长零售/电商商品运营与增长策略。\n"
        "你需要基于用户任务和智能体产出的真实数据，撰写一份企业级的 Markdown 分析报告。\n\n"
        "硬性要求：\n"
        "1) 严格按用户任务定制分析维度——不同任务输出结构必须显著不同，禁止套用雷同模板。\n"
        "2) 只引用 sections 中已存在的真实数据；缺失模块写'本模块暂无有效数据'，禁止编造销量/评分/价格/GMV。\n"
        "3) 严禁输出思维链、推理过程、工具调用记录或<think>标签。\n"
        "4) 业务结论必须回答：发现了什么、对业务意味什么、下一步做什么。\n"
        "5) 每个章节第一句话必须是该章节核心结论；细节数据后置。\n"
        "6) 报告总长 2000-3500 字，使用 Markdown；表格使用 Markdown 语法；数值保留 2 位小数。\n"
        "7) 当用户任务只涉及 1-2 个分析维度时（如'生成营销文案'/'竞品对比'），应聚焦这两个维度深入展开，"
        "其余章节可省略或合并为'配套建议'，禁止堆砌无关模块。\n"
        "8) 严格返回合法 JSON，对象包含 polished_report（Markdown 字符串）和 executive_summary（≤80字）两个字段，"
        "不要包含任何 JSON 之外的文本、Markdown 代码块或注释。\n\n"
        f"{task_extensions}\n\n"
        "JSON 输出结构：\n"
        "{\n"
        '  "polished_report": "## 一、摘要与核心建议\\n### 一句话结论\\n...\\n## 二、专项分析\\n...",\n'
        '  "executive_summary": "一句话总结，不超过80字"\n'
        "}"
    )


_TASK_EXTENSIONS = {
    "product_analysis": (
        "[选品场景专项要求]\n"
        "- 展示候选商品原始指标表，完整输出所有字段（价格、评分、评价数）。\n"
        "- 构建加权评分模型，详细列明各维度权重（评分30%、热度30%、价值25%、描述15%）及归一化公式。\n"
        "- 输出Min-Max归一化矩阵，注明每项指标的Min值和Max值，防止未来数据溢出。\n"
        "- 加权贡献分解：展示每项指标对最终分数的绝对贡献值，并计算贡献占比。\n"
        "- 综合评分结果划分「强势推荐>=70」「推荐40-70」「备选<40」三级标签。\n"
        "- 估算30天GMV区间（下限/上限），将预测销量与当前库存量做80%红线预警。\n"
        "- 对Top1商品给出A/B测试建议（如降价5% vs 赠送配件），并预估获客成本（CAC）。"
    ),
    "trend_forecast": (
        "[趋势预测场景专项要求]\n"
        "- 按7天/30天窗口列预测销量、置信度和WAPE误差（模型拟合误差）。\n"
        "- 趋势分类：明确划分「上升期」「稳定期」「衰退期」，并给出对应运营动作。\n"
        "- 评分×置信度二维交叉分析：高评分+高置信度=必胜品；高评分+低置信度=需小流量测试。\n"
        "- 列明各商品的拟合模型类型（Seasonal Naive / ARIMA / Prophet等）。"
    ),
    "competitor_analysis": (
        "[竞品对比场景专项要求]\n"
        "- 输出价格带分布图（将竞品价格按区间分组），标注目标商品所在百分位。\n"
        "- 核心维度对比矩阵：价格、评分、评价数、综合得分，标注最强/最弱项。\n"
        "- 竞品优劣势分析：逐个指出每个竞品的核心短板与优势。\n"
        "- 基于对比结果给出差异化话术建议或价格跟随策略。"
    ),
    "inventory": (
        "[库存场景专项要求]\n"
        "- 五级预警：滞销/低/正常/紧张/断货，每级标注对应SKU数。\n"
        "- 补货优先级排序：按资金占用×风险等级加权排序。\n"
        "- 滞销SKU清仓建议与预计损耗率；断货SKU紧急补货数量与到货时间窗。\n"
        "- 总库存健康度评分及风险汇总表。"
    ),
    "pricing": (
        "[定价场景专项要求]\n"
        "- 价格弹性区间与置信度，明确建议价格区间[floor, ceiling]。\n"
        "- 竞品价格带分析，本次商品在价格带的百分位。\n"
        "- A/B试价区间±5%与预期转化影响，价格监控阈值偏离±3%。\n"
        "- 毛利率测算与竞品毛利率对比。"
    ),
    "promotion": (
        "[促销场景专项要求]\n"
        "- 促销类型匹配：说明为什么这种促销适合该商品（如满减/限时折扣/捆绑销售）。\n"
        "- 折扣深度建议+最低折扣红线（防止利润倒挂）。\n"
        "- 档期建议（大促/平销/清仓）；基于历史促销系数估算ROI区间。\n"
        "- 促销前后销量弹性系数对比。"
    ),
    "marketing_copy": (
        "[营销文案场景专项要求]\n"
        "- 每款商品输出四件套：tagline（标语，≤15字）、bullets（3个核心卖点）、description（产品描述，100-200字）、social（社交文案，50-100字，含emoji和话题标签）。\n"
        "- 分析目标人群画像（年龄、性别、场景、痛点）。\n"
        "- 差异化话术：与同价位竞品的核心差异点。\n"
        "- 关键词建议：列出该商品应覆盖的5-8个搜索关键词。"
    ),
}


def _sanitize_markdown(value):
    text = str(value or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"```(?:markdown|md)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "")
    return text.strip()


def _build_task_extensions(sections):
    seen: list[str] = []
    for name in (sections or {}).keys():
        if name in _TASK_EXTENSIONS and name not in seen:
            seen.append(name)
    if not seen:
        return "(本任务无特定模块要求，按通用结构输出)"
    return "\n\n".join(_TASK_EXTENSIONS[n] for n in seen)


class ReportPolisher:
    def __init__(self, llm_service=None):
        self._llm = llm_service or LLMService()

    async def polish(self, user_query, sections, raw_summary, failed_agents=None):
        sections = sections or {}
        if not sections:
            empty = "本次查询未检测到有效的分析数据。"
            return {"polished_report": "## 分析结析\n\n" + empty, "executive_summary": empty}
        empty_data = _is_empty_data(sections)
        task_ext = _build_task_extensions(sections)
        prompt = _build_system_prompt(task_ext)
        payload = self._build_payload(user_query, sections, raw_summary, failed_agents, empty=empty_data)
        user_message = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            response = await self._llm.chat(
                system_prompt=prompt,
                user_message=user_message,
                temperature=0.4,
                max_tokens=9000,
                json_mode=False,
                fallback=None,
            )
        except Exception as exc:
            logger.warning("ReportPolisher LLM call failed: %s", exc)
            return self._fallback(user_query, sections, raw_summary, failed_agents)
        polished, summary = self._parse_response(response)
        if not polished or len(polished) < 200:
            return self._fallback(user_query, sections, raw_summary, failed_agents)
        return {"polished_report": polished, "executive_summary": summary}

    @staticmethod
    def _parse_response(response):
        """Parse LLM response into (polished_report, executive_summary).

        Handles nested JSON: if polished_report value looks like JSON, parse it recursively.
        """
        text = ""
        if isinstance(response, dict):
            # Direct JSON object
            if response.get("polished_report") is not None:
                polished_raw = response.get("polished_report", "")
                summary = str(response.get("executive_summary", "")).strip()
                # Handle nested JSON string
                if isinstance(polished_raw, str):
                    trimmed = polished_raw.strip()
                    if trimmed.startswith("{") and trimmed.endswith("}"):
                        try:
                            nested = json.loads(trimmed)
                            if isinstance(nested, dict):
                                inner_report = nested.get("polished_report")
                                inner_summary = nested.get("executive_summary")
                                if inner_report is not None:
                                    polished = _sanitize_markdown(str(inner_report))
                                    summary = str(inner_summary or summary).strip()
                                    return polished, summary
                        except Exception:
                            # Try with newline fix on the trimmed string
                            try:
                                fixed_inner = trimmed.replace(chr(10), "\\n").replace(chr(13), "\\n")
                                nested = json.loads(fixed_inner)
                                inner_report = nested.get("polished_report")
                                inner_summary = nested.get("executive_summary")
                                if inner_report is not None:
                                    polished = _sanitize_markdown(str(inner_report))
                                    summary = str(inner_summary or summary).strip()
                                    return polished, summary
                            except Exception:
                                pass
                    polished = _sanitize_markdown(polished_raw)
                    return polished, summary
                if isinstance(polished_raw, dict):
                    inner_report = polished_raw.get("polished_report") or polished_raw.get("report") or str(polished_raw)
                    inner_summary = polished_raw.get("executive_summary") or polished_raw.get("summary") or summary
                    polished = _sanitize_markdown(str(inner_report))
                    summary = str(inner_summary).strip()
                    return polished, summary
                polished = _sanitize_markdown(str(polished_raw))
                return polished, summary
            text = (response.get("content") or response.get("text") or response.get("__raw__") or "")
        else:
            text = str(response or "")

        cleaned = _sanitize_markdown(text)
        if not cleaned:
            return "", ""

        obj = _safe_json_loads(cleaned)
        if isinstance(obj, dict) and "polished_report" in obj:
            polished = _sanitize_markdown(obj.get("polished_report", ""))
            summary = str(obj.get("executive_summary", "")).strip()
            return polished, summary

        start_brace = cleaned.find("{")
        end_brace = cleaned.rfind("}")
        if start_brace >= 0 and end_brace > start_brace:
            candidate = cleaned[start_brace:end_brace + 1]
            obj = _safe_json_loads(candidate)
            if isinstance(obj, dict) and "polished_report" in obj:
                polished = _sanitize_markdown(obj.get("polished_report", ""))
                summary = str(obj.get("executive_summary", "")).strip()
                return polished, summary

        return cleaned, ""

    @staticmethod
    def _build_payload(user_query, sections, raw_summary, failed_agents, empty=False):
        compact = {}
        for name, sec in sections.items():
            if not isinstance(sec, dict):
                continue
            entry = {}
            for key in (
                "summary", "insight", "key_findings", "recommended_actions",
                "limitations", "market_summary",
                "selected_products", "product_forecasts", "product_positioning",
                "category_benchmarks", "analysis_scope",
                "copies", "total_generated",
            ):
                if key in sec:
                    entry[key] = sec[key]
            compact[name] = entry
        scope = (sections.get("product_analysis") or {}).get("analysis_scope") or {}
        all_scopes = {
            name: (sec.get("analysis_scope") if isinstance(sec, dict) else None)
            for name, sec in sections.items()
        }
        visible = [k for k, v in compact.items() if v]
        return {
            "user_query": user_query,
            "raw_summary": raw_summary,
            "failed_agents": failed_agents or [],
            "visible_modules": visible,
            "matched_count": scope.get("matched_count"),
            "all_scopes": all_scopes,
            "empty_data": empty,
            "sections": compact,
        }

    @staticmethod
    def _data_driven_summary(user_query: str, sections: dict) -> str:
        """Generate a real data-driven executive summary (no template strings)."""
        if not sections:
            return "本次查询未匹配到有效数据，建议补充数据源。"
        # Prefer product_analysis insight
        pa = sections.get("product_analysis") or {}
        insight = pa.get("insight") or pa.get("summary")
        if insight and isinstance(insight, str):
            return insight.strip()[:120]
        # marketing copy
        mc = sections.get("marketing_copy") or {}
        if mc.get("copies"):
            total = mc.get("total_generated") or len(mc["copies"])
            return f"已为 {total} 款商品生成差异化营销文案。"
        # competitor
        ca = sections.get("competitor_analysis") or {}
        if ca.get("insight"):
            return str(ca["insight"])[:120]
        # trend
        tf = sections.get("trend_forecast") or {}
        if tf.get("insight"):
            return str(tf["insight"])[:120]
        # inventory
        inv = sections.get("inventory") or {}
        if inv.get("insight"):
            return str(inv["insight"])[:120]
        # pricing
        pr = sections.get("pricing") or {}
        if pr.get("insight"):
            return str(pr["insight"])[:120]
        # promotion
        pm = sections.get("promotion") or {}
        if pm.get("insight"):
            return str(pm["insight"])[:120]
        return f"基于 {len(sections)} 个分析模块输出洞察。"

    @staticmethod
    def _fallback_summary(user_query: str, sections: dict) -> str:
        return ReportPolisher._data_driven_summary(user_query, sections)

    @staticmethod
    def _fallback(user_query, sections, raw_summary, failed_agents):
        """Generate a data-driven report from agent outputs (no LLM needed).

        Critical: this is what users see when the LLM fails. It must be:
        - Specific to the task (use the actual user query + agent insights)
        - Not template-similar (vary structure per visible modules)
        """
        sections = sections or {}
        lines: list[str] = []
        title = user_query or "电商业务分析报告"
        lines.append(f"# {title}\n")
        lines.append(f"> {_SOURCE_LABEL}  ·  {_VERSION}\n")

        # ── 摘要 ────────────────────────────────────────────────
        lines.append("## 一、摘要与核心建议\n")
        lines.append(ReportPolisher._data_driven_summary(user_query, sections) + "\n")
        lines.append("\n")

        # ── 可见模块概览 ─────────────────────────────────────────
        visible_labels = [_AGENT_LABELS.get(name, name) for name in sections.keys()]
        if visible_labels:
            lines.append("## 二、本次分析覆盖模块\n")
            for label in visible_labels:
                lines.append(f"- {label}")
            lines.append("\n")

        # ── 专项分析结果（按用户任务定制顺序）────────────────────
        lines.append("## 三、专项分析结果\n")
        ordered = sorted(
            sections.keys(),
            key=lambda n: _SECTION_ORDER.index(n) if n in _SECTION_ORDER else 99,
        )
        for name in ordered:
            sec = sections.get(name)
            if not isinstance(sec, dict):
                continue
            heading = _AGENT_REPORT_TITLES.get(name, _AGENT_LABELS.get(name, name))
            lines.append(f"### {heading}\n")

            # Insight/summary line — core conclusion first
            insight = sec.get("insight") or sec.get("summary")
            if insight:
                lines.append(f"**核心结论：** {insight}\n")

            # ── Marketing copy special rendering ───────────────
            if name == "marketing_copy" and sec.get("copies"):
                lines.append("\n**文案产出：**\n")
                for item in sec["copies"][:5]:
                    title_str = item.get("title", "未命名商品")
                    copies = item.get("generated_copies", {}) or {}
                    lines.append(f"#### {title_str}\n")
                    if copies.get("tagline"):
                        lines.append(f"- **Tagline**：{copies['tagline']}")
                    if copies.get("bullets"):
                        lines.append(f"- **卖点**：\n{copies['bullets']}")
                    if copies.get("description"):
                        lines.append(f"- **产品描述**：{copies['description']}")
                    if copies.get("social"):
                        lines.append(f"- **社交文案**：{copies['social']}")
                    lines.append("")
                lines.append("\n")

            # ── Selected products (product_analysis) ───────────
            if sec.get("selected_products"):
                lines.append("\n**候选商品摘要：**\n")
                lines.append("| 商品 | 价格 | 评分 | 综合得分 |")
                lines.append("|------|------|------|----------|")
                for p in sec["selected_products"][:8]:
                    title = p.get("title", "")[:40]
                    price = p.get("price", 0)
                    rating = (p.get("rating") or {}).get("rate", 0) if isinstance(p.get("rating"), dict) else p.get("rating", 0)
                    score = p.get("composite_score", p.get("score", "-"))
                    lines.append(f"| {title} | ${price} | {rating} | {score} |")
                lines.append("\n")

            # ── Product forecasts ─────────────────────────────
            if sec.get("product_forecasts"):
                lines.append("\n**销量预测：**\n")
                lines.append("| 商品 | 7天预测 | 30天预测 | 置信度 |")
                lines.append("|------|---------|----------|--------|")
                for f in sec["product_forecasts"][:6]:
                    lines.append(f"| {f.get('title', '')[:30]} | {f.get('forecast_7d', '-')} | {f.get('forecast_30d', '-')} | {f.get('confidence', '-')} |")
                lines.append("\n")

            # ── Key findings ──────────────────────────────────
            findings = sec.get("key_findings") or []
            if isinstance(findings, list) and findings:
                lines.append("\n**关键发现：**\n")
                for f in findings[:6]:
                    lines.append(f"- {f}")
                lines.append("\n")

            # ── Recommended actions ───────────────────────────
            actions = sec.get("recommended_actions") or []
            if isinstance(actions, list) and actions:
                lines.append("\n**建议动作：**\n")
                for a in actions[:5]:
                    lines.append(f"- {a}")
                lines.append("\n")

            # ── Limitations ───────────────────────────────────
            limits = sec.get("limitations") or []
            if isinstance(limits, list) and limits:
                lines.append("\n**数据局限：**\n")
                for l in limits[:3]:
                    lines.append(f"- {l}")
                lines.append("\n")

        # ── 附录 ─────────────────────────────────────────────
        lines.append("## 四、附录\n")
        lines.append(f"- {_SOURCE_LABEL}")
        lines.append(f"- 报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- {_VERSION}")
        if failed_agents:
            lines.append(f"- 失败模块：{', '.join(failed_agents)}")

        report = "\n".join(lines).strip() + "\n"
        return {
            "polished_report": report,
            "executive_summary": ReportPolisher._data_driven_summary(user_query, sections),
        }

