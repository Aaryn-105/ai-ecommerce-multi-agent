import sys
sys.path.insert(0, r"D:\新建文件夹\New_Goods_Project 2")
from backend.services.report_export import ReportExportService

svc = ReportExportService()
sections = {
    "product_analysis": {
        "selected_products": [
            {"title": "无线降噪耳机", "composite_score": 92.3},
            {"title": "智能手表 Pro", "composite_score": 88.1},
            {"title": "便携咖啡机",   "composite_score": 79.5},
            {"title": "蓝牙音箱",     "composite_score": 71.0},
        ],
        "statistics": {
            "category_distribution": {"数码": 12, "家居": 8, "服饰": 5, "美妆": 3},
        },
    },
    "trend_forecast": {
        "product_forecasts": [
            {"title": "降噪耳机", "predicted_30d_total": 1500, "growth_rate": 0.25},
            {"title": "智能手表", "predicted_30d_total":  900, "growth_rate": 0.12},
            {"title": "咖啡机",   "predicted_30d_total":  300, "growth_rate": -0.08},
        ],
    },
    "pricing": {
        "pricing_results": [
            {"title": "耳机", "current_price": 299, "suggested_price": 269},
            {"title": "手表", "current_price": 499, "suggested_price": 459},
            {"title": "咖啡机","current_price": 199, "suggested_price": 219},
        ],
    },
    "inventory": {
        "replenishment_plans": [
            {"title": "耳机", "suggested_reorder_qty": 500},
            {"title": "手表", "suggested_reorder_qty": 200},
            {"title": "咖啡机","suggested_reorder_qty": 80},
        ],
    },
}

pdf = svc.to_pdf("测试报告", "含图表的端到端冒烟测试", sections)
out = r"D:\新建文件夹\New_Goods_Project 2\smoke_charts.pdf"
with open(out, "wb") as f:
    f.write(pdf)
print("PDF OK, %d bytes -> %s" % (len(pdf), out))
