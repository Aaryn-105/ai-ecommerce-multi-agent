"""Report export service — generates PDF (ReportLab) and DOCX (python-docx) files.

Usage::

    svc = ReportExportService()
    pdf_bytes = svc.to_pdf("Report Title", "Summary text", sections_dict)
    docx_bytes = svc.to_docx("Report Title", "Summary text", sections_dict)
"""
from __future__ import annotations

import io
import os
import tempfile
from typing import Any

from backend.core.config import settings

# ── Optional dependency helpers ──────────────────────────

def _check_reportlab() -> None:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        msg = "reportlab is required for PDF export. Install: pip install reportlab"
        raise ImportError(msg)


def _check_docx() -> None:
    try:
        import docx  # noqa: F401
    except ImportError:
        msg = "python-docx is required for DOCX export. Install: pip install python-docx"
        raise ImportError(msg)


# ── Section label mapping (Chinese) ──────────────────────

_SECTION_LABELS: dict[str, str] = {
    "product_analysis": "商品选品分析",
    "trend_forecast": "销售趋势预测",
    "competitor_analysis": "竞品对比分析",
    "marketing_copy": "营销文案",
    "inventory": "库存补货建议",
    "pricing": "定价建议",
    "promotion": "促销方案",
}

_AGENT_ORDER = [
    "product_analysis",
    "trend_forecast",
    "competitor_analysis",
    "marketing_copy",
    "inventory",
    "pricing",
    "promotion",
]


def _fmt(val: Any, decimals: int = 2) -> str:
    """Format a number nicely, or return the value as-is."""
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    if isinstance(val, int):
        return str(val)
    return str(val)


# ═══════════════════════════════════════════════════════════
#  PDF Generation (ReportLab)
# ═══════════════════════════════════════════════════════════

def _build_pdf(
    title: str,
    summary: str,
    sections: dict[str, Any],
) -> bytes:
    """Generate a PDF report using ReportLab platypus."""
    _check_reportlab()

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm, cm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=28,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a2e"),
    )
    body_style = ParagraphStyle(
        "SectionBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "SmallText",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    elements: list[Any] = []

    # ── Title page ───────────────────────────────────────
    elements.append(Spacer(1, 4 * cm))
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 1 * cm))
    if summary:
        elements.append(Paragraph(summary, body_style))
    elements.append(PageBreak())

    # ── Sections ─────────────────────────────────────────
    for agent_key in _AGENT_ORDER:
        if agent_key not in sections:
            continue
        data = sections[agent_key]
        label = _SECTION_LABELS.get(agent_key, agent_key)
        elements.append(Paragraph(label, heading_style))

        _render_pdf_section(elements, agent_key, data, body_style, small_style)
        elements.append(Spacer(1, 6 * mm))

    doc.build(elements)
    return buf.getvalue()


def _render_pdf_section(
    elements: list[Any],
    agent_key: str,
    data: dict[str, Any],
    body_style: Any,
    small_style: Any,
) -> None:
    """Render a single agent section into the PDF element list."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    summary = data.get("summary") or data.get("market_summary") or ""
    if summary:
        elements.append(Paragraph(f"<b>摘要：</b>{summary}", body_style))
        elements.append(Spacer(1, 3))

    if agent_key == "product_analysis":
        _render_product_table(elements, data.get("selected_products", []), body_style, small_style)
        stats = data.get("statistics", {})
        if stats:
            elements.append(Paragraph(
                f"<b>统计：</b>共分析 {stats.get('total_analyzed', 0)} 件商品，"
                f"精选 {stats.get('selected_count', 0)} 件，"
                f"涵盖 {len(stats.get('category_distribution', {}))} 个品类",
                small_style,
            ))

    elif agent_key == "trend_forecast":
        forecasts = data.get("product_forecasts", [])
        for fc in forecasts[:5]:
            elements.append(Paragraph(
                f"<b>{fc.get('title', '')[:50]}</b> — "
                f"7日预测总量: {sum(fc.get('forecast_7d', [0])):.0f} | "
                f"30日预测总量: {sum(fc.get('forecast_30d', [0])):.0f} | "
                f"增长率: {fc.get('growth_rate', 0):.1%}",
                small_style,
            ))

    elif agent_key == "competitor_analysis":
        positioning = data.get("product_positioning", [])
        for pos in positioning[:5]:
            adv = "; ".join(pos.get("advantages", [])[:3])
            disadv = "; ".join(pos.get("disadvantages", [])[:3])
            elements.append(Paragraph(
                f"<b>{pos.get('title', '')[:40]}</b> — "
                f"综合评分: {pos.get('composite_score', 0):.2f} | "
                f"优势: {adv} | 劣势: {disadv}",
                small_style,
            ))

    elif agent_key == "marketing_copy":
        copies = data.get("copies", [])
        for cp in copies[:3]:
            gc = cp.get("generated_copies", {})
            elements.append(Paragraph(
                f"<b>{cp.get('title', '')[:40]}</b> — "
                f"标语: {gc.get('tagline', '')[:50]}",
                small_style,
            ))

    elif agent_key == "inventory":
        plans = data.get("replenishment_plans", [])
        header = ["商品", "综合评分", "建议补货", "优先级"]
        rows = [header]
        for pl in plans[:8]:
            rows.append([
                pl.get("title", "")[:20],
                _fmt(pl.get("composite_score", 0), 2),
                str(pl.get("suggested_reorder_qty", 0)),
                str(pl.get("priority", 99)),
            ])
        if len(rows) > 1:
            t = Table(rows, colWidths=[120, 60, 60, 50])
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]))
            elements.append(t)

    elif agent_key == "pricing":
        results = data.get("pricing_results", [])
        header = ["商品", "当前价", "建议价", "策略", "置信度"]
        rows = [header]
        for pr in results[:8]:
            rows.append([
                pr.get("title", "")[:20],
                f"${_fmt(pr.get('current_price', 0))}",
                f"${_fmt(pr.get('suggested_price', 0))}",
                pr.get("strategy", "")[:10],
                pr.get("confidence", ""),
            ])
        if len(rows) > 1:
            t = Table(rows, colWidths=[100, 50, 50, 60, 50])
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ]))
            elements.append(t)

    elif agent_key == "promotion":
        promo = data.get("promotion_result", {}).get("promotion_plan", {})
        if promo:
            elements.append(Paragraph(
                f"<b>推荐策略：</b>{promo.get('campaign_name', '')} "
                f"(类型: {promo.get('promotion_type', '')})",
                body_style,
            ))
            elements.append(Paragraph(
                f"原价 ${_fmt(promo.get('original_price', 0))} → "
                f"促销价 ${_fmt(promo.get('promotion_price', 0))} "
                f"(折扣 {promo.get('discount_label', '')}) | "
                f"预估 ROI {_fmt(promo.get('estimated_roi', 0))}x | "
                f"持续 {promo.get('duration_days', 0)} 天",
                small_style,
            ))

        alts = data.get("alternative_plans", [])
        if alts:
            elements.append(Paragraph("<b>备选方案：</b>", small_style))
            for a in alts[:3]:
                elements.append(Paragraph(
                    f"  - {a.get('campaign_name', '')} "
                    f"(折扣 {a.get('discount_label', '')}, "
                    f"ROI {_fmt(a.get('estimated_roi', 0))}x)",
                    small_style,
                ))


def _render_product_table(
    elements: list[Any],
    products: list[dict[str, Any]],
    body_style: Any,
    small_style: Any,
) -> None:
    """Render selected products as a table."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    if not products:
        return

    header = ["排名", "商品名称", "品类", "价格", "评分", "综合得分"]
    rows = [header]
    for i, p in enumerate(products[:10], 1):
        rows.append([
            str(i),
            p.get("title", "")[:25],
            p.get("category", "")[:12],
            f"${_fmt(p.get('price', 0))}",
            _fmt(p.get("original_rating", {}).get("rate", 0)),
            _fmt(p.get("final_score", 0), 4),
        ])

    t = Table(rows, colWidths=[30, 140, 70, 50, 40, 60])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elements.append(t)


# ═══════════════════════════════════════════════════════════
#  DOCX Generation (python-docx)
# ═══════════════════════════════════════════════════════════

def _build_docx(
    title: str,
    summary: str,
    sections: dict[str, Any],
) -> bytes:
    """Generate a DOCX report using python-docx."""
    _check_docx()

    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # ── Styles ───────────────────────────────────────────
    style = doc.styles["Normal"]
    style.font.name = "微软雅黑"
    style.font.size = Pt(10)
    style.paragraph_format.space_after = Pt(4)

    # ── Title ────────────────────────────────────────────
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ── Summary ──────────────────────────────────────────
    if summary:
        p = doc.add_paragraph()
        run = p.add_run("报告摘要")
        run.bold = True
        run.font.size = Pt(12)
        doc.add_paragraph(summary)

    doc.add_page_break()

    # ── Sections ─────────────────────────────────────────
    for agent_key in _AGENT_ORDER:
        if agent_key not in sections:
            continue
        data = sections[agent_key]
        label = _SECTION_LABELS.get(agent_key, agent_key)
        doc.add_heading(label, level=1)

        _render_docx_section(doc, agent_key, data)

        doc.add_paragraph()  # spacer

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _render_docx_section(
    doc: Any,
    agent_key: str,
    data: dict[str, Any],
) -> None:
    """Render a single agent section into the DOCX document."""
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    summary = data.get("summary") or data.get("market_summary") or ""
    if summary:
        p = doc.add_paragraph()
        run = p.add_run("摘要：")
        run.bold = True
        doc.add_paragraph(summary)

    if agent_key == "product_analysis":
        products = data.get("selected_products", [])
        if products:
            table = doc.add_table(rows=1, cols=6)
            table.style = "Light Grid Accent 1"
            hdr = table.rows[0].cells
            for i, txt in enumerate(["排名", "商品名称", "品类", "价格", "评分", "综合得分"]):
                hdr[i].text = txt
            for i, p in enumerate(products[:10], 1):
                row = table.add_row().cells
                row[0].text = str(i)
                row[1].text = p.get("title", "")[:30]
                row[2].text = p.get("category", "")[:15]
                row[3].text = f"${_fmt(p.get('price', 0))}"
                row[4].text = _fmt(p.get("original_rating", {}).get("rate", 0))
                row[5].text = _fmt(p.get("final_score", 0), 4)

        stats = data.get("statistics", {})
        if stats:
            doc.add_paragraph(
                f"共分析 {stats.get('total_analyzed', 0)} 件商品，"
                f"精选 {stats.get('selected_count', 0)} 件，"
                f"涵盖 {len(stats.get('category_distribution', {}))} 个品类"
            )

    elif agent_key == "trend_forecast":
        forecasts = data.get("product_forecasts", [])
        if forecasts:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Light Grid Accent 1"
            hdr = table.rows[0].cells
            for i, txt in enumerate(["商品", "7日预测", "30日预测", "增长率", "波动率"]):
                hdr[i].text = txt
            for fc in forecasts[:8]:
                row = table.add_row().cells
                row[0].text = fc.get("title", "")[:20]
                row[1].text = _fmt(sum(fc.get("forecast_7d", [0])), 0)
                row[2].text = _fmt(sum(fc.get("forecast_30d", [0])), 0)
                row[3].text = f"{fc.get('growth_rate', 0):.1%}"
                row[4].text = _fmt(fc.get("volatility", 0), 2)

    elif agent_key == "competitor_analysis":
        positioning = data.get("product_positioning", [])
        if positioning:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Light Grid Accent 1"
            hdr = table.rows[0].cells
            for i, txt in enumerate(["商品", "综合评分", "价格分位", "评分分位", "优势"]):
                hdr[i].text = txt
            for pos in positioning[:8]:
                row = table.add_row().cells
                row[0].text = pos.get("title", "")[:20]
                row[1].text = _fmt(pos.get("composite_score", 0), 2)
                row[2].text = f"{pos.get('price_percentile', 0):.0%}"
                row[3].text = f"{pos.get('rating_percentile', 0):.0%}"
                row[4].text = "; ".join(pos.get("advantages", [])[:2])

    elif agent_key == "marketing_copy":
        copies = data.get("copies", [])
        for cp in copies[:5]:
            doc.add_heading(cp.get("title", "")[:40], level=3)
            gc = cp.get("generated_copies", {})
            if gc.get("tagline"):
                p = doc.add_paragraph()
                run = p.add_run(f"标语：{gc['tagline']}")
                run.italic = True
            if gc.get("bullets"):
                doc.add_paragraph(gc["bullets"])
            if gc.get("description"):
                doc.add_paragraph(gc["description"])
            if gc.get("social"):
                doc.add_paragraph(f"[社交媒体] {gc['social']}")

    elif agent_key == "inventory":
        plans = data.get("replenishment_plans", [])
        if plans:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Light Grid Accent 1"
            hdr = table.rows[0].cells
            for i, txt in enumerate(["商品", "综合评分", "建议补货", "建议操作", "优先级"]):
                hdr[i].text = txt
            for pl in plans[:8]:
                row = table.add_row().cells
                row[0].text = pl.get("title", "")[:20]
                row[1].text = _fmt(pl.get("composite_score", 0), 2)
                row[2].text = str(pl.get("suggested_reorder_qty", 0))
                row[3].text = pl.get("suggested_action", "")[:12]
                row[4].text = str(pl.get("priority", 99))

    elif agent_key == "pricing":
        results = data.get("pricing_results", [])
        if results:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Light Grid Accent 1"
            hdr = table.rows[0].cells
            for i, txt in enumerate(["商品", "当前价", "建议价", "策略", "置信度"]):
                hdr[i].text = txt
            for pr in results[:8]:
                row = table.add_row().cells
                row[0].text = pr.get("title", "")[:20]
                row[1].text = f"${_fmt(pr.get('current_price', 0))}"
                row[2].text = f"${_fmt(pr.get('suggested_price', 0))}"
                row[3].text = pr.get("strategy", "")[:10]
                row[4].text = pr.get("confidence", "")

    elif agent_key == "promotion":
        promo = data.get("promotion_result", {}).get("promotion_plan", {})
        if promo:
            doc.add_paragraph(
                f"推荐策略：{promo.get('campaign_name', '')} "
                f"（类型: {promo.get('promotion_type', '')}）"
            )
            doc.add_paragraph(
                f"原价 ${_fmt(promo.get('original_price', 0))} → "
                f"促销价 ${_fmt(promo.get('promotion_price', 0))} "
                f"（折扣 {promo.get('discount_label', '')}）"
            )
            doc.add_paragraph(
                f"预估 ROI: {_fmt(promo.get('estimated_roi', 0))}x | "
                f"持续 {promo.get('duration_days', 0)} 天 | "
                f"条件: {promo.get('conditions', '')}"
            )

        alts = data.get("alternative_plans", [])
        if alts:
            doc.add_paragraph("备选方案：")
            for a in alts[:3]:
                doc.add_paragraph(
                    f"  - {a.get('campaign_name', '')} "
                    f"（折扣 {a.get('discount_label', '')}, "
                    f"ROI {_fmt(a.get('estimated_roi', 0))}x）",
                    style="List Bullet",
                )


# ═══════════════════════════════════════════════════════════
#  Public Service Class
# ═══════════════════════════════════════════════════════════

class ReportExportService:
    """Generate PDF and DOCX reports from structured sections data."""

    def to_pdf(
        self,
        title: str,
        summary: str,
        sections: dict[str, Any],
    ) -> bytes:
        """Render a full PDF report and return the bytes."""
        return _build_pdf(title, summary, sections)

    def to_docx(
        self,
        title: str,
        summary: str,
        sections: dict[str, Any],
    ) -> bytes:
        """Render a full DOCX report and return the bytes."""
        return _build_docx(title, summary, sections)
