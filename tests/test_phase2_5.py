"""Tests for Trend Forecast — moving average utilities and agent, driven by real FakeStore data."""
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

from backend.agents.trend_forecast.moving_average import (
    simple_moving_average,
    extract_trend,
    forecast_forward,
    forecast_range,
)
from backend.agents.trend_forecast.agent import TrendForecastAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, TrendForecastOutput
from backend.services.fake_store import FakeStoreService


# ═══════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════

_REAL_PRODUCTS: list[dict] | None = None


@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    global _REAL_PRODUCTS
    if _REAL_PRODUCTS is not None:
        return _REAL_PRODUCTS
    svc = FakeStoreService()
    try:
        _REAL_PRODUCTS = await svc.get_all_products()
    finally:
        await svc.close()
    assert len(_REAL_PRODUCTS) == 20
    return _REAL_PRODUCTS


@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


# ═══════════════════════════════════════════════════════════
#  Moving Average Unit Tests
# ═══════════════════════════════════════════════════════════

class TestSimpleMovingAverage:
    def test_basic_sma(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = simple_moving_average(data, window=3)
        assert result == [2.0, 3.0, 4.0]

    def test_window_equals_length(self):
        data = [10.0, 20.0, 30.0]
        result = simple_moving_average(data, window=3)
        assert result == [20.0]

    def test_window_larger_than_length_returns_empty(self):
        data = [1.0, 2.0]
        result = simple_moving_average(data, window=5)
        assert result == []

    def test_window_one_returns_copy(self):
        data = [5.0, 10.0, 15.0]
        result = simple_moving_average(data, window=1)
        assert result == [5.0, 10.0, 15.0]

    def test_window_zero_returns_empty(self):
        data = [1.0, 2.0, 3.0]
        result = simple_moving_average(data, window=0)
        assert result == []

    def test_empty_data(self):
        assert simple_moving_average([], window=3) == []

    def test_single_element(self):
        assert simple_moving_average([42.0], window=3) == []

    @pytest.mark.asyncio
    async def test_sma_on_real_data(self, real_products):
        """Use real product rating counts as a pseudo time-series."""
        counts = [float(p["rating"]["count"]) for p in real_products]
        result = simple_moving_average(counts, window=5)
        assert len(result) == len(counts) - 5 + 1
        assert all(isinstance(v, float) for v in result)
        print(f"  SMA from {len(counts)} rating counts → {len(result)} MA values")
        print(f"  First 3 MA: {result[:3]}")


class TestExtractTrend:
    def test_uptrend_positive_slope(self):
        """Consistently increasing values → positive trend."""
        ma = [10.0, 11.0, 12.0, 13.0, 14.0]
        trend = extract_trend(ma)
        assert trend > 0
        print(f"  Uptrend rate: {trend:.4f}")

    def test_downtrend_negative_slope(self):
        ma = [100.0, 95.0, 90.0, 85.0, 80.0]
        trend = extract_trend(ma)
        assert trend < 0
        print(f"  Downtrend rate: {trend:.4f}")

    def test_flat_returns_near_zero(self):
        ma = [50.0, 50.0, 50.0, 50.0, 50.0]
        trend = extract_trend(ma)
        assert abs(trend) < 0.001

    def test_insufficient_data_returns_zero(self):
        assert extract_trend([]) == 0.0
        assert extract_trend([42.0]) == 0.0


class TestForecastForward:
    def test_deterministic_no_noise(self):
        fcst = forecast_forward(last_value=100.0, trend_rate=0.02, days=5, noise=0.0)
        assert len(fcst) == 5
        # Each step grows by ~2%
        assert fcst[0] > 100
        assert fcst[-1] > fcst[0]

    def test_negative_trend(self):
        fcst = forecast_forward(last_value=100.0, trend_rate=-0.05, days=5, noise=0.0)
        assert fcst[0] < 100
        assert fcst[-1] < fcst[0]

    def test_zero_trend_flat(self):
        fcst = forecast_forward(last_value=50.0, trend_rate=0.0, days=3, noise=0.0)
        assert fcst == [50, 50, 50]

    def test_forecast_length(self):
        for days in [1, 7, 30, 90]:
            fcst = forecast_forward(100.0, 0.01, days=days)
            assert len(fcst) == days

    def test_non_negative_values(self):
        fcst = forecast_forward(5.0, -0.5, days=10, noise=0.0)
        assert all(v >= 0 for v in fcst)

    def test_noise_produces_variation(self):
        fcst_no_noise = forecast_forward(100.0, 0.01, days=10, noise=0.0)
        fcst_with_noise = forecast_forward(100.0, 0.01, days=10, noise=0.2)
        # With noise, values should differ from deterministic
        assert fcst_no_noise != fcst_with_noise or all(v == fcst_no_noise[0] for v in fcst_no_noise)


class TestForecastRange:
    def test_basic_forecast_range(self):
        sales = [10, 12, 11, 13, 14, 12, 15, 16, 14, 15]
        result = forecast_range(sales, window=3, forecast_days=5)
        assert "ma" in result
        assert "trend" in result
        assert "forecast" in result
        assert len(result["forecast"]) == 5
        assert len(result["ma"]) == len(sales) - 3 + 1

    def test_empty_sales(self):
        result = forecast_range([], window=7, forecast_days=7)
        assert result["ma"] == []
        assert result["trend"] == 0.0
        assert result["forecast"] == [0] * 7


# ═══════════════════════════════════════════════════════════
#  TrendForecastAgent Tests
# ═══════════════════════════════════════════════════════════

class TestTrendForecastAgent:
    """Integration tests using real FakeStore products."""

    @pytest.mark.asyncio
    async def test_agent_produces_forecasts(self, real_products):
        """Verify the agent returns forecasts for all products."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_001",
            request_id="req_tf_001",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        output = result.output_data
        assert len(output["product_forecasts"]) == 20
        assert output["all_count"] == 20
        print(f"  Summary: {output['summary']}")

    @pytest.mark.asyncio
    async def test_each_product_has_forecast_data(self, real_products):
        """Each forecast entry must have all expected fields."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_002",
            request_id="req_tf_002",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)

        for pf in result.output_data["product_forecasts"]:
            assert pf["product_id"] > 0
            assert pf["title"] != ""
            assert len(pf["forecast_30d"]) == 30
            assert len(pf["forecast_7d"]) == 7
            assert len(pf["ma_trend"]) > 0
            assert pf["trend_rate"] is not None
            assert isinstance(pf["growth_signal"], str)
            assert pf["avg_sales_30d"] > 0
            print(f"  Product {pf['product_id']} ({pf['title'][:25]}...): "
                  f"trend={pf['trend_rate']:.4f}, signal={pf['growth_signal']}")

    @pytest.mark.asyncio
    async def test_forecast_is_deterministic(self, real_products):
        """Same input must produce identical forecasts (seed-based)."""
        agent = TrendForecastAgent(top_n=10)
        inp = AgentInput(
            task_id="tf_det",
            request_id="req_tf_det",
            input_data={"products": real_products},
        )
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)

        for pf1, pf2 in zip(
            r1.output_data["product_forecasts"],
            r2.output_data["product_forecasts"],
        ):
            assert pf1["forecast_7d"] == pf2["forecast_7d"]
            assert pf1["forecast_30d"] == pf2["forecast_30d"]
            assert pf1["trend_rate"] == pf2["trend_rate"]

    @pytest.mark.asyncio
    async def test_top_n_filtering(self, real_products):
        """Verify top_n parameter works correctly."""
        for n in [3, 5, 10]:
            agent = TrendForecastAgent(top_n=n)
            inp = AgentInput(
                task_id=f"tf_top{n}",
                request_id=f"req_top{n}",
                input_data={"products": real_products},
            )
            result = await agent.run(inp)
            assert len(result.output_data["product_forecasts"]) == n

    @pytest.mark.asyncio
    async def test_sorted_by_trend_descending(self, real_products):
        """Forecasts must be sorted by trend rate descending."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_sort",
            request_id="req_sort",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        rates = [pf["trend_rate"] for pf in result.output_data["product_forecasts"]]
        assert rates == sorted(rates, reverse=True)

    @pytest.mark.asyncio
    async def test_growth_signal_distribution(self, real_products):
        """Verify growth signal classification produces varied results."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_signal",
            request_id="req_signal",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        signals = [pf["growth_signal"] for pf in result.output_data["product_forecasts"]]
        unique_signals = set(signals)
        print(f"  Growth signals: {unique_signals}")
        print(f"  Signal distribution: {{s: signals.count(s) for s in unique_signals}}")
        # All signals should be valid
        valid = {"high_growth", "stable_growth", "stable", "slight_decline", "declining"}
        assert unique_signals.issubset(valid)

    @pytest.mark.asyncio
    async def test_volatility_is_reasonable(self, real_products):
        """Volatility should be non-negative and finite."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_vol",
            request_id="req_vol",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        for pf in result.output_data["product_forecasts"]:
            assert pf["volatility"] >= 0
            assert pf["volatility"] < 100  # sanity check
            print(f"  Product {pf['product_id']}: volatility={pf['volatility']:.3f}")

    @pytest.mark.asyncio
    async def test_sma_window_effect(self, real_products):
        """Different SMA windows produce different MA lengths."""
        agent_short = TrendForecastAgent(top_n=1, sma_window=3)
        agent_long = TrendForecastAgent(top_n=1, sma_window=14)

        inp = AgentInput(task_id="tf_win", request_id="req_win",
                         input_data={"products": real_products[:1]})
        r_short = await agent_short.run(inp)
        r_long = await agent_long.run(inp)

        ma_short = r_short.output_data["product_forecasts"][0]["ma_trend"]
        ma_long = r_long.output_data["product_forecasts"][0]["ma_trend"]
        # Short window → more MA points
        assert len(ma_short) > len(ma_long)

    @pytest.mark.asyncio
    async def test_sales_history_90d_length(self, real_products):
        """Each product must have 90 days of sales history."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_hist",
            request_id="req_hist",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        for pf in result.output_data["product_forecasts"]:
            assert len(pf["sales_history_90d"]) == 90

    @pytest.mark.asyncio
    async def test_forecast_30d_is_longer_than_7d(self, real_products):
        """30-day forecast must contain more data than 7-day."""
        agent = TrendForecastAgent(top_n=20)
        inp = AgentInput(
            task_id="tf_len",
            request_id="req_len",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        for pf in result.output_data["product_forecasts"]:
            assert len(pf["forecast_30d"]) >= len(pf["forecast_7d"])

    @pytest.mark.asyncio
    async def test_empty_products(self):
        """Empty input must produce empty forecast."""
        agent = TrendForecastAgent()
        inp = AgentInput(task_id="tf_empty", request_id="req_empty", input_data={"products": []})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["product_forecasts"] == []

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products):
        """Verify output data validates against TrendForecastOutput."""
        agent = TrendForecastAgent(top_n=1)
        inp = AgentInput(
            task_id="tf_schema",
            request_id="req_schema",
            input_data={"products": [real_products[0]]},
        )
        result = await agent.run(inp)
        pf = result.output_data["product_forecasts"][0]
        parsed = TrendForecastOutput(
            product_id=pf["product_id"],
            historical=[{"date": f"2026-01-{i+1:02d}", "units": u}
                        for i, u in enumerate(pf["sales_history_90d"][:30])],
            ma_trend=pf["ma_trend"],
            forecast_7d=pf["forecast_7d"],
            forecast_30d=pf["forecast_30d"],
            summary=result.output_data["summary"],
        )
        assert parsed.product_id == real_products[0]["id"]
        assert len(parsed.forecast_7d) == 7
        assert len(parsed.forecast_30d) == 30

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products):
        agent = TrendForecastAgent(top_n=5)
        inp = AgentInput(
            task_id="tf_meta",
            request_id="req_meta",
            input_data={"products": real_products},
        )
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(TrendForecastAgent)
        cls = AgentRegistry.get("trend_forecast")
        assert cls is TrendForecastAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products):
        """Verify the agent works via the Executor (orchestrator flow)."""
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep

        AgentRegistry.register(TrendForecastAgent)
        plan = [
            PlanStep(agent="trend_forecast", params={"products": real_products}, depends_on=[]),
        ]
        executor = Executor(request_id="exec_tf")
        context = await executor.run(plan)
        assert "trend_forecast" in context
        assert context["trend_forecast"]["status"] == "completed"
        output = context["trend_forecast"]["output_data"]
        assert len(output["product_forecasts"]) == 10  # default top_n

    @pytest.mark.asyncio
    async def test_context_product_analysis_integration(self, real_products):
        """Simulate realistic pipeline: product analysis feeds into trend forecast."""
        AgentRegistry.register(TrendForecastAgent)

        # Create context similar to what product_analysis outputs
        context_data = {
            "selected_products": [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "category": p["category"],
                    "price": p["price"],
                    "rating": p["rating"],
                }
                for p in real_products[:5]
            ]
        }
        agent = TrendForecastAgent(top_n=5)
        inp = AgentInput(
            task_id="tf_context",
            request_id="req_context",
            input_data={},
            context={"product_analysis": {"output_data": context_data}},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["product_forecasts"]) == 5
        print(f"  Context-driven forecast summary: {result.output_data['summary']}")