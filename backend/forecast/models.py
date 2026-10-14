"""Simple, transparent price forecasters. Each takes a history (oldest first) and a horizon, and returns one
forecast per future month.

Deliberately basic: with a few hundred monthly points per series and prices that jump (wheat flour in Peshawar went
from 55 to 131 PKR/kg within a year), fancy models would mostly overfit. The "naive" model, which assumes next
month looks like this month, is the bar every other model has to clear.
"""

from typing import Callable

Forecaster = Callable[[list[float], int], list[float]]


def naive(history: list[float], horizon: int) -> list[float]:
    """Prices stay where they are."""
    return [history[-1]] * horizon


def make_drift(window: int) -> Forecaster:
    """Continue the average monthly change seen over the last `window` months."""

    def drift(history: list[float], horizon: int) -> list[float]:
        slope = (history[-1] - history[-1 - window]) / window if len(history) > window else 0.0
        return [history[-1] + slope * k for k in range(1, horizon + 1)]

    return drift


def seasonal_naive(history: list[float], horizon: int, period: int = 12) -> list[float]:
    """Each month looks like the same month a year earlier."""
    if len(history) < period or horizon > period:
        raise ValueError("need at least one full season of history and horizon <= period")
    n = len(history)
    return [history[n - period + k - 1] for k in range(1, horizon + 1)]


def holt_damped(history: list[float], horizon: int, alpha: float = 0.6, beta: float = 0.2, phi: float = 0.85) -> list[float]:
    """Level + trend smoothing where the trend fades out (phi < 1), so forecasts do not run away."""
    if len(history) < 2:
        return naive(history, horizon)
    level, trend = history[0], history[1] - history[0]
    for y in history[1:]:
        prev = level
        level = alpha * y + (1 - alpha) * (prev + phi * trend)
        trend = beta * (level - prev) + (1 - beta) * phi * trend
    out, damp = [], 0.0
    for k in range(1, horizon + 1):
        damp += phi**k
        out.append(level + damp * trend)
    return out


MODELS: dict[str, Forecaster] = {
    "naive": naive,
    "drift_6m": make_drift(6),
    "drift_12m": make_drift(12),
    "holt_damped": holt_damped,
    "seasonal_naive": seasonal_naive,
}

MODEL_DESCRIPTIONS = {
    "naive": "assumes prices stay where they are",
    "drift_6m": "continues the average monthly change of the last 6 months",
    "drift_12m": "continues the average monthly change of the last 12 months",
    "holt_damped": "smoothed level and trend, with the trend fading out",
    "seasonal_naive": "assumes each month repeats the same month last year",
}
