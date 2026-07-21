import sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'D:\新建文件夹\New_Goods_Project 2\backend\services\report_export.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

CHART_HELPER_CODE = '''
# ─── Chart helpers (native ReportLab vector charts) ─────────
from reportlab.lib.colors import HexColor as _HexColor

_CHART_PRIMARY = _HexColor("#0f3460")
_CHART_ACCENT  = _HexColor("#e94560")
_CHART_SUCCESS = _HexColor("#22c55e")
_CHART_WARNING = _HexColor("#f59e0b")
_CHART_DARK    = _HexColor("#1a1a2e")
_CHART_GREY    = _HexColor("#94a3b8")


def _truncate_label(s: str, n: int = 10) -> str:
    """Shorten chart labels to keep x-axis readable."""
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _build_bar_chart(
    title: str,
    labels,
    values,
    *,
    y_label: str = "",
    color=None,
    height: float = 180,
    width: float = 480,
    value_format: str = "{:.1f}",
    bar_label_color=None,
    show_values: bool = True,
) -> object:
    """Render a single-series vertical bar chart as a reportlab Drawing."""
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String, Rect
    from reportlab.lib.colors import black

    if color is None:
        color = _CHART_PRIMARY
    if bar_label_color is None:
        bar_label_color = _CHART_DARK

    safe_labels = [_truncate_label(l, 10) for l in labels]
    safe_values = [float(v or 0) for v in values]

    drawing = Drawing(width, height)
    drawing.add(String(
        width / 2, height - 12, title,
        fontSize=10, fillColor=_CHART_DARK,
        fontName=_CJK_FONT_NAME, textAnchor="middle",
    ))
    drawing.add(Rect(0, 0, width, height, strokeColor=_HexColor("#e2e8f0"),
                     strokeWidth=0.5, fillColor=_HexColor("#fafafa")))

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 28
    chart.width = width - 70
    chart.height = height - 50
    chart.data = [safe_values]
    chart.categoryAxis.categoryNames = safe_labels
    chart.bars[0].fillColor = color
    chart.bars[0].strokeColor = color
    chart.valueAxis.valueMin = 0
    if safe_values:
        vmax = max(safe_values)
        chart.valueAxis.valueMax = vmax * 1.18 if vmax > 0 else 1.0
        step = (vmax * 1.18) / 4 if vmax > 0 else 0.2
        chart.valueAxis.valueStep = step
    chart.valueAxis.labelTextFormat = value_format
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = _CJK_FONT_NAME
    chart.valueAxis.labels.fillColor = _CHART_DARK
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fontName = _CJK_FONT_NAME
    chart.categoryAxis.labels.fillColor = _CHART_DARK
    chart.categoryAxis.labels.boxAnchor = "n"
    chart.bars[0].barWidth = 14

    if y_label:
        drawing.add(String(
            12, chart.y + chart.height / 2, y_label,
            fontSize=8, fillColor=_CHART_DARK,
            fontName=_CJK_FONT_NAME, textAnchor="middle",
        ))

    drawing.add(String(
        chart.x + chart.width / 2, 14, "商品",
        fontSize=8, fillColor=_CHART_DARK,
        fontName=_CJK_FONT_NAME, textAnchor="middle",
    ))

    drawing.add(chart)
    return drawing


def _build_grouped_bar_chart(
    title: str,
    labels,
    series_a,
    series_b,
    *,
    legend_a: str = "当前",
    legend_b: str = "建议",
    color_a=None,
    color_b=None,
    height: float = 200,
    width: float = 480,
    value_format: str = "${:.0f}",
) -> object:
    """Render a two-series grouped bar chart (e.g. current vs suggested price)."""
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String, Rect
    if color_a is None: color_a = _CHART_GREY
    if color_b is None: color_b = _CHART_ACCENT

    safe_labels = [_truncate_label(l, 8) for l in labels]
    sa = [float(v or 0) for v in series_a]
    sb = [float(v or 0) for v in series_b]

    drawing = Drawing(width, height)
    drawing.add(String(
        width / 2, height - 12, title,
        fontSize=10, fillColor=_CHART_DARK,
        fontName=_CJK_FONT_NAME, textAnchor="middle",
    ))
    drawing.add(Rect(0, 0, width, height, strokeColor=_HexColor("#e2e8f0"),
                     strokeWidth=0.5, fillColor=_HexColor("#fafafa")))

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 28
    chart.width = width - 70
    chart.height = height - 55
    chart.data = [sa, sb]
    chart.categoryAxis.categoryNames = safe_labels
    chart.bars[0].fillColor = color_a
    chart.bars[1].fillColor = color_b
    chart.valueAxis.valueMin = 0
    if sa or sb:
        vmax = max(sa + sb) or 1
        chart.valueAxis.valueMax = vmax * 1.18
        chart.valueAxis.valueStep = vmax * 1.18 / 4
    chart.valueAxis.labelTextFormat = value_format
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = _CJK_FONT_NAME
    chart.valueAxis.labels.fillColor = _CHART_DARK
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fontName = _CJK_FONT_NAME
    chart.categoryAxis.labels.fillColor = _CHART_DARK
    chart.bars[0].barWidth = 10
    chart.bars[1].barWidth = 10
    chart.groupSpacing = 12

    drawing.add(chart)

    leg_y = height - 28
    drawing.add(Rect(width - 110, leg_y - 2, 10, 8, fillColor=color_a, strokeColor=color_a))
    drawing.add(String(width - 96, leg_y + 1, legend_a,
                       fontSize=8, fillColor=_CHART_DARK, fontName=_CJK_FONT_NAME))
    drawing.add(Rect(width - 60, leg_y - 2, 10, 8, fillColor=color_b, strokeColor=color_b))
    drawing.add(String(width - 46, leg_y + 1, legend_b,
                       fontSize=8, fillColor=_CHART_DARK, fontName=_CJK_FONT_NAME))

    drawing.add(String(
        chart.x + chart.width / 2, 14, "商品",
        fontSize=8, fillColor=_CHART_DARK,
        fontName=_CJK_FONT_NAME, textAnchor="middle",
    ))
    return drawing


def _build_pie_chart(
    title: str,
    labels,
    values,
    *,
    height: float = 180,
    width: float = 320,
) -> object:
    """Render a simple pie chart for category/share data."""
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, String, Rect

    safe_labels = [str(l) for l in labels]
    safe_values = [max(float(v or 0), 0.001) for v in values]
    palette = [_CHART_PRIMARY, _CHART_ACCENT, _CHART_SUCCESS,
               _CHART_WARNING, _CHART_GREY, _HexColor("#6366f1")]

    drawing = Drawing(width, height)
    drawing.add(String(
        width / 2, height - 12, title,
        fontSize=10, fillColor=_CHART_DARK,
        fontName=_CJK_FONT_NAME, textAnchor="middle",
    ))
    pie = Pie()
    pie.x = 30
    pie.y = 20
    pie.width = height - 50
    pie.height = height - 50
    pie.data = safe_values
    pie.labels = safe_labels
    pie.slices.strokeWidth = 0.5
    for i, slc in enumerate(pie.slices):
        slc.fillColor = palette[i % len(palette)]
        slc.strokeColor = _HexColor("#ffffff")
    pie.labelFormat = "%(label)s"
    pie.fontSize = 7
    pie.fontName = _CJK_FONT_NAME
    drawing.add(pie)

    leg_x = pie.x + pie.width + 10
    leg_y = pie.y + pie.height - 8
    for i, (lab, val) in enumerate(zip(safe_labels, safe_values)):
        ly = leg_y - 12 * i
        drawing.add(Rect(leg_x, ly - 4, 8, 8,
                         fillColor=palette[i % len(palette)],
                         strokeColor=palette[i % len(palette)]))
        drawing.add(String(leg_x + 12, ly, f"{lab} ({val:.0f})",
                           fontSize=7, fillColor=_CHART_DARK,
                           fontName=_CJK_FONT_NAME))
    return drawing


'''

marker = "def _build_pdf("
assert marker in content, "marker not found"
content = content.replace(marker, CHART_HELPER_CODE + "\n\n" + marker, 1)

PROD_TABLE_MARKER = "def _render_product_table("
assert PROD_TABLE_MARKER in content

CHART_INJECT = '''def _render_pdf_charts(
    elements: list,
    agent_key: str,
    data: dict,
    body_style,
) -> None:
    """Insert native vector bar/pie charts into the PDF for quantitative agents."""
    from reportlab.platypus import Spacer

    if agent_key == "product_analysis":
        products = data.get("selected_products", []) or []
        if len(products) >= 2:
            items = products[:10]
            labels = [p.get("title", "") for p in items]
            values = [float(p.get("composite_score", 0) or 0) for p in items]
            if any(v > 0 for v in values):
                elements.append(Paragraph("<b>📊 Top 10 商品综合评分对比</b>", body_style))
                elements.append(Spacer(1, 2))
                elements.append(_build_bar_chart(
                    "综合评分（越高越优）",
                    labels, values,
                    color=_CHART_PRIMARY,
                    value_format="{:.1f}",
                ))
                elements.append(Spacer(1, 8))

            cat_dist = (data.get("statistics", {}) or {}).get("category_distribution", {}) or {}
            if len(cat_dist) >= 2:
                elements.append(Paragraph("<b>🥧 类目商品数分布</b>", body_style))
                elements.append(Spacer(1, 2))
                elements.append(_build_pie_chart(
                    "类目商品数",
                    list(cat_dist.keys()),
                    list(cat_dist.values()),
                ))
                elements.append(Spacer(1, 8))

    elif agent_key == "trend_forecast":
        forecasts = data.get("product_forecasts", []) or []
        if len(forecasts) >= 2:
            items = forecasts[:10]
            labels = [fc.get("title", "") for fc in items]
            values_30 = [float(fc.get("predicted_30d_total", 0) or fc.get("predicted_30d", 0) or 0) for fc in items]
            values_growth = [float(fc.get("growth_rate", 0) or 0) for fc in items]

            if any(v > 0 for v in values_30):
                elements.append(Paragraph("<b>📈 30 天销量预测对比</b>", body_style))
                elements.append(Spacer(1, 2))
                elements.append(_build_bar_chart(
                    "30天预测销量（件）",
                    labels, values_30,
                    color=_CHART_ACCENT,
                    value_format="{:.0f}",
                ))
                elements.append(Spacer(1, 8))

            if any(v != 0 for v in values_growth):
                color = _CHART_SUCCESS if any(v >= 0 for v in values_growth) else _CHART_ACCENT
                elements.append(Paragraph("<b>📊 增长率对比 (%)</b>", body_style))
                elements.append(Spacer(1, 2))
                elements.append(_build_bar_chart(
                    "增长率 (%)",
                    labels, values_growth,
                    color=color,
                    value_format="{:.1f}",
                ))
                elements.append(Spacer(1, 8))

    elif agent_key == "pricing":
        results = data.get("pricing_results", []) or []
        if len(results) >= 2:
            items = results[:8]
            labels = [r.get("title", "") for r in items]
            cur = [float(r.get("current_price", 0) or 0) for r in items]
            sug = [float(r.get("suggested_price", 0) or 0) for r in items]
            elements.append(Paragraph("<b>💰 定价对比：当前价 vs 建议价</b>", body_style))
            elements.append(Spacer(1, 2))
            elements.append(_build_grouped_bar_chart(
                "定价对比（USD）",
                labels, cur, sug,
                legend_a="当前价",
                legend_b="建议价",
                color_a=_CHART_GREY,
                color_b=_CHART_ACCENT,
                value_format="${:.0f}",
            ))
            elements.append(Spacer(1, 8))

    elif agent_key == "inventory":
        plans = data.get("replenishment_plans", []) or []
        if len(plans) >= 2:
            items = plans[:8]
            labels = [pl.get("title", "") for pl in items]
            values = [float(pl.get("suggested_reorder_qty", 0) or 0) for pl in items]
            if any(v > 0 for v in values):
                elements.append(Paragraph("<b>📦 建议补货数量</b>", body_style))
                elements.append(Spacer(1, 2))
                elements.append(_build_bar_chart(
                    "建议补货量（件）",
                    labels, values,
                    color=_CHART_WARNING,
                    value_format="{:.0f}",
                ))
                elements.append(Spacer(1, 8))


'''

content = content.replace(PROD_TABLE_MARKER, CHART_INJECT + "\n\n" + PROD_TABLE_MARKER, 1)

OLD_LOOP = '''    for agent_key in _AGENT_ORDER:
        if agent_key not in sections:
            continue
        data = sections[agent_key]
        label = _SECTION_LABELS.get(agent_key, agent_key)
        elements.append(Paragraph(label, heading_style))

        _render_pdf_section(elements, agent_key, data, body_style, small_style)
        elements.append(Spacer(1, 6 * mm))'''
NEW_LOOP = '''    for agent_key in _AGENT_ORDER:
        if agent_key not in sections:
            continue
        data = sections[agent_key]
        label = _SECTION_LABELS.get(agent_key, agent_key)
        elements.append(Paragraph(label, heading_style))

        _render_pdf_section(elements, agent_key, data, body_style, small_style)
        # ── Inject vector charts after structured data ──
        _render_pdf_charts(elements, agent_key, data, body_style)
        elements.append(Spacer(1, 6 * mm))'''
assert OLD_LOOP in content, "_build_pdf loop not found"
content = content.replace(OLD_LOOP, NEW_LOOP, 1)

with open(p, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"OK: {p} updated, {len(content)} bytes")
