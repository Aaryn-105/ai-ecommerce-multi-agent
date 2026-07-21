"""Trend Forecast Agent — analyse historical sales and predict future demand.

Uses Simple Moving Average (SMA) with trend extrapolation.
Pure code — zero LLM calls.
"""
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.services.analysis_insight import AnalysisInsightService
from backend.agents.trend_forecast.moving_average import forecast_range
from backend.services.data_generator import generate_sales_history
from backend.services.llm_service import LLMService


class TrendForecastAgent(BaseAgent):
    """Analyse sales history and forecast future demand.

    Flow::

        products → Step 1: generate sales history for each product
                 → Step 2: compute SMA + trend
                 → Step 3: forecast 7d / 30d
                 → Step 4: rank by growth & volatility, format output

    Deterministic forecasting is preserved; an optional LLM adds evidence-bound insight.
    """

    agent_name = "trend_forecast"

    def __init__(
        self,
        forecast_days: int = 30,
        sma_window: int = 7,
        top_n: int = 10,
        llm_service: LLMService | None = None,
    ) -> None:
        self._forecast_days = forecast_days
        self._sma_window = sma_window
        self._top_n = top_n
        self._insight = AnalysisInsightService(llm_service)

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Accept products from input_data or context
        raw_products: list[dict[str, Any]] = (
            input_data.get("products")
            or (context.get("product_analysis", {}).get("output_data", {}).get("selected_products"))
            or []
        )

        if not raw_products:
            return {
                "product_forecasts": [],
                "analysis_scope": {
                    "category": input_data.get("category") or "全部商品",
                    "matched_count": 0,
                    "data_source": "FakeStore API + 本地模拟销量历史",
                },
                "summary": f"真实数据中未找到{input_data.get('category') or '目标'}类目商品，无法进行趋势预测。",
                "high_growth_count": 0,
                "declining_count": 0,
            }

        # ── Step 1: Generate sales history for each product ──
        product_forecasts: list[dict[str, Any]] = []

        for p in raw_products:
            pid = p.get("id", 0)
            title = p.get("title", "Unknown")
            category = p.get("category", "")
            price = p.get("price", 0.0)
            rating = p.get("rating") or p.get("original_rating") or {}
            rating_count = rating.get("count", 0)

            # Generate 90 days of sales history
            sales_history = generate_sales_history(
                product_id=pid,
                rating_count=rating_count,
                days=90,
                seed=pid,  # deterministic per product
            )
            daily_units = [s["units"] for s in sales_history]

            # Use last 30 days for forecasting
            recent_30 = daily_units[-30:] if len(daily_units) >= 30 else daily_units

            # ── Step 2 & 3: SMA + trend + forecast ──
            result = forecast_range(
                recent_sales=recent_30,
                window=min(self._sma_window, len(recent_30)),
                forecast_days=self._forecast_days,
            )

            # Historical stats
            avg_sales_30d = round(sum(recent_30) / max(len(recent_30), 1), 1)
            max_sales_30d = max(recent_30) if recent_30 else 0
            min_sales_30d = min(recent_30) if recent_30 else 0

            # Volatility (coefficient of variation)
            if avg_sales_30d > 0 and len(recent_30) > 1:
                std = (sum((v - avg_sales_30d) ** 2 for v in recent_30) / len(recent_30)) ** 0.5
                volatility = round(std / avg_sales_30d, 3)
            else:
                volatility = 0.0

            # Forecast 7d total and 30d total
            fcst_7d = result["forecast"][:7]
            fcst_30d = result["forecast"]

            product_forecasts.append({
                "product_id": pid,
                "title": title,
                "category": category,
                "price": price,
                "sales_history_90d": daily_units,
                "ma_trend": result["ma"],
                "trend_rate": round(result["trend"], 6),
                "forecast_7d": fcst_7d,
                "forecast_30d": fcst_30d,
                "avg_sales_30d": avg_sales_30d,
                "max_sales_30d": max_sales_30d,
                "min_sales_30d": min_sales_30d,
                "volatility": volatility,
                # Derived signals
                "growth_signal": self._classify_growth(result["trend"]),
            })

        # ── Step 4: Rank & summarise ──
        # Sort by trend_rate descending
        product_forecasts.sort(key=lambda x: -x["trend_rate"])

        high_growth = sum(1 for pf in product_forecasts if pf["growth_signal"] == "high_growth")
        declining = sum(1 for pf in product_forecasts if pf["growth_signal"] == "declining")

        top_forecasts = product_forecasts[:self._top_n]

        summary = (
            f"分析了{len(product_forecasts)}款产品的90天销售历史，"
            f"其中高增长趋势{high_growth}款，平稳{len(product_forecasts) - high_growth - declining}款，下降趋势{declining}款。"
            f"前{self._top_n}款产品已详细输出趋势预测。"
        )

        output = {
            "product_forecasts": top_forecasts,
            "analysis_scope": {
                "category": input_data.get("category") or "全部商品",
                "matched_count": len(product_forecasts),
                "data_source": "FakeStore API + 本地模拟销量历史",
            },
            "all_count": len(product_forecasts),
            "high_growth_count": high_growth,
            "declining_count": declining,
            "summary": summary,
        }
        query = str(input_data.get("user_query") or context.get("user_query") or "")
        top_forecast = top_forecasts[0] if top_forecasts else {}
        insight = await self._insight.generate(
            agent_name=self.agent_name,
            user_query=query,
            evidence={
                "analysis_scope": output["analysis_scope"],
                "high_growth_count": high_growth,
                "declining_count": declining,
                "top_forecasts": [
                    {
                        "title": forecast["title"],
                        "avg_sales_30d": forecast["avg_sales_30d"],
                        "forecast_7d_total": round(sum(forecast["forecast_7d"]), 1),
                        "forecast_30d_total": round(sum(forecast["forecast_30d"]), 1),
                        "trend_rate": forecast["trend_rate"],
                        "volatility": forecast["volatility"],
                        "growth_signal": forecast["growth_signal"],
                    }
                    for forecast in top_forecasts[:5]
                ],
            },
            fallback_insight=(
                f"模型估算显示，{top_forecast.get('title', '重点商品')}的趋势斜率为"
                f"{top_forecast.get('trend_rate', 0)}，信号为{top_forecast.get('growth_signal', '未知')}。"
                "该结果适合用于排序和备货预案，不应替代真实订单时间序列。"
            ),
            fallback_findings=[
                f"覆盖{len(product_forecasts)}款商品，其中高增长{high_growth}款、下降{declining}款。",
                f"重点商品未来7天模型估算销量为{round(sum(top_forecast.get('forecast_7d', [])), 1)}件。",
                f"重点商品未来30天模型估算销量为{round(sum(top_forecast.get('forecast_30d', [])), 1)}件。",
            ],
            limitations=["FakeStore API不提供历史销量；当前时间序列由评价数代理生成，仅用于模型演示。"],
        )
        output.update(insight)
        return output

    @staticmethod
    def _classify_growth(trend_rate: float) -> str:
        """Classify growth signal based on daily trend rate."""
        if trend_rate > 0.03:
            return "high_growth"
        if trend_rate > 0.005:
            return "stable_growth"
        if trend_rate > -0.005:
            return "stable"
        if trend_rate > -0.03:
            return "slight_decline"
        return "declining"
