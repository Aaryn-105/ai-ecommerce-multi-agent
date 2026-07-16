"""Simple Moving Average (SMA) utilities for trend forecasting.

Provides SMA calculation, trend extraction, and forward forecasting
using weighted recent trends.
"""
from __future__ import annotations

from typing import Any


def simple_moving_average(
    data: list[float],
    window: int,
) -> list[float]:
    """Compute the simple moving average over *window* elements.

    Args:
        data:   Input time-series values.
        window: Sliding window size (>= 1).

    Returns:
        A list of length `len(data) - window + 1` (empty if shorter).
    """
    if window < 1 or len(data) < window:
        return []

    result: list[float] = []
    for i in range(len(data) - window + 1):
        avg = sum(data[i : i + window]) / window
        result.append(round(avg, 2))
    return result


def extract_trend(ma_values: list[float]) -> float:
    """Estimate average daily change rate from the MA series.

    Uses linear regression slope normalised by the mean.

    Args:
        ma_values: SMA values (at least 2 points).

    Returns:
        A fractional daily trend (e.g. 0.02 = +2 % / day).
        Returns 0.0 when insufficient data.
    """
    if len(ma_values) < 2:
        return 0.0

    n = len(ma_values)
    x_vals = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(ma_values) / n

    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, ma_values))
    den = sum((x - mean_x) ** 2 for x in x_vals)

    if den == 0:
        return 0.0

    slope = num / den
    base = mean_y if mean_y > 0 else 1.0
    return slope / base


def forecast_forward(
    last_value: float,
    trend_rate: float,
    days: int,
    noise: float = 0.0,
) -> list[int]:
    """Generate a *days*-length forecast based on exponential trend.

    Each day: `value_{t+1} = value_t * (1 + trend_rate)`.

    Args:
        last_value: The last known value (e.g. last day's sales).
        trend_rate: Daily fractional growth rate.
        days:       Number of forecast days.
        noise:      Optional fractional noise amplitude (0.0 = deterministic).

    Returns:
        List of integer forecast values of length *days*.
    """
    import random as _random

    result: list[int] = []
    current = float(last_value)

    for _ in range(days):
        # Apply trend
        current = current * (1.0 + trend_rate)
        # Add noise if requested
        if noise > 0:
            noise_factor = 1.0 + _random.uniform(-noise, noise)
            current *= noise_factor
        # Ensure non-negative
        result.append(max(0, round(current)))

    return result


def forecast_range(
    recent_sales: list[int],
    window: int = 7,
    forecast_days: int = 7,
) -> dict[str, Any]:
    """Convenience: compute SMA + trend + forward forecast in one call.

    Args:
        recent_sales:  Daily sales units (last N days).
        window:        SMA window size.
        forecast_days: Number of days to forecast.

    Returns:
        `{"ma": list[float], "trend": float, "forecast": list[int]}`
    """
    if not recent_sales:
        return {"ma": [], "trend": 0.0, "forecast": [0] * forecast_days}

    float_data = [float(v) for v in recent_sales]
    ma = simple_moving_average(float_data, window)
    trend = extract_trend(ma) if ma else 0.0
    last_val = float(recent_sales[-1])
    fcst = forecast_forward(last_val, trend, forecast_days)

    return {"ma": ma, "trend": trend, "forecast": fcst}