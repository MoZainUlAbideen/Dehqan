"""Market agent: forecast a price series, choose a method honestly, and give a sell/hold signal with a range.

Honesty rules built in:
1. A method is only used if it beat "prices stay the same" by a clear margin in a backtest on past data.
   Otherwise the agent says its forecast is no better than assuming prices stay the same.
2. The range shown is how wrong the chosen method actually was in past forecasts (empirical 10th to 90th
   percentile), not a made-up confidence interval.
3. A "hold" or "sell" signal needs the WHOLE range to point the same way by more than SIGNAL_THRESHOLD.
   Otherwise the answer is "no clear signal".
Nothing here knows storage costs, loan interest, spoilage or the price a farmer actually gets.
"""

from dataclasses import dataclass

from data_sources.wfp_prices import Series, gap_free_tail, next_month
from forecast.models import MODEL_DESCRIPTIONS, MODELS

HORIZON = 3               # months ahead
MIN_HISTORY = 48          # months a method may look back at, at the earliest origin
BACKTEST_ORIGINS = 60     # how many past forecast dates are used to judge methods
MARGIN = 0.05             # a method must cut the error by >= 5% versus naive to be used
SIGNAL_THRESHOLD = 0.03   # the whole range must clear +/-3% for a hold/sell signal
LOW_Q, HIGH_Q = 0.10, 0.90
MIN_SERIES = MIN_HISTORY + BACKTEST_ORIGINS + HORIZON

CAVEATS = [
    "These are retail prices from WFP market monitoring, not the price a farmer is paid at the mandi.",
    "Prices are monthly and the latest month is already some weeks old.",
    "Storage costs, spoilage, loan interest and transport are not included.",
    "This is a statistical guess about the next three months, not financial advice.",
]


def quantile(values: list[float], q: float) -> float:
    """Linear-interpolated quantile (q in 0..1) of a non-empty list."""
    s = sorted(values)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def origins_for(n: int) -> range:
    """Forecast origins t: history = values[:t], targets = values[t:t+HORIZON]. The most recent BACKTEST_ORIGINS."""
    last = n - HORIZON
    return range(last - BACKTEST_ORIGINS + 1, last + 1)


def backtest(values: list[float], model_name: str) -> list[tuple[list[float], list[float]]]:
    """[(forecasts, actuals), ...] for every origin, for one method."""
    f = MODELS[model_name]
    return [(f(values[:t], HORIZON), values[t : t + HORIZON]) for t in origins_for(len(values))]


def mape(pairs: list[tuple[list[float], list[float]]]) -> float:
    errs = [abs(a - p) / abs(a) for fc, ac in pairs for p, a in zip(fc, ac) if a != 0]
    return sum(errs) / len(errs)


@dataclass
class Choice:
    model: str
    beats_naive: bool
    mape_model: float
    mape_naive: float
    n_origins: int


def choose_model(values: list[float]) -> Choice:
    """Best method by past error, but only if it beats naive by MARGIN; otherwise naive."""
    if len(values) < MIN_SERIES:
        raise ValueError(f"need at least {MIN_SERIES} consecutive months, got {len(values)}")
    scores = {name: mape(backtest(values, name)) for name in MODELS}
    naive_score = scores["naive"]
    best = min(scores, key=lambda k: (scores[k], k != "naive"))
    if best != "naive" and scores[best] <= (1 - MARGIN) * naive_score:
        return Choice(best, True, scores[best], naive_score, BACKTEST_ORIGINS)
    return Choice("naive", False, naive_score, naive_score, BACKTEST_ORIGINS)


def error_ratios(values: list[float], model_name: str) -> list[list[float]]:
    """Per horizon (1..HORIZON): (actual - forecast) / forecast over all past origins."""
    pairs = backtest(values, model_name)
    return [[(ac[h] - fc[h]) / fc[h] for fc, ac in pairs if fc[h] != 0] for h in range(HORIZON)]


def forecast_with_range(values: list[float], model_name: str) -> list[tuple[float, float, float]]:
    """[(central, low, high)] for each of the next HORIZON months. The range = past forecast errors, 10th-90th pct."""
    central = MODELS[model_name](values, HORIZON)
    ratios = error_ratios(values, model_name)
    out = []
    for h in range(HORIZON):
        lo, hi = quantile(ratios[h], LOW_Q), quantile(ratios[h], HIGH_Q)
        out.append((central[h], central[h] * (1 + lo), central[h] * (1 + hi)))
    return out


def advise(last: float, low: float, high: float, beats_naive: bool) -> tuple[str, str]:
    """(signal, message) from the range for the month HORIZON ahead. signal is hold | sell | none."""
    if not beats_naive:
        return "none", (
            "Our forecasting method is no better than simply assuming prices stay where they are, "
            "so there is no reliable signal. The range below shows how far prices have usually moved in three months."
        )
    if low > last * (1 + SIGNAL_THRESHOLD):
        return "hold", "Prices have tended to rise from here. Holding may pay if you can store safely and afford to wait."
    if high < last * (1 - SIGNAL_THRESHOLD):
        return "sell", "Prices have tended to fall from here. Selling sooner may be better than waiting."
    return "none", "No clear signal: the likely range includes both rises and falls. Decide on your own costs and needs."


def analyse(commodity: str, market: str, unit: str, series: Series) -> dict:
    tail = gap_free_tail(series)
    values = [p for _, p in tail]
    if len(values) < MIN_SERIES:
        raise ValueError(f"not enough consecutive monthly data for {commodity} in {market}")
    choice = choose_model(values)
    fc = forecast_with_range(values, choice.model)
    last_month = tail[-1][0]
    months, m = [], last_month
    for _ in range(HORIZON):
        m = next_month(m)
        months.append(m)
    last = values[-1]
    signal, message = advise(last, fc[-1][1], fc[-1][2], choice.beats_naive)
    return {
        "commodity": commodity, "market": market, "unit": f"PKR per {unit.lower()}",
        "data_as_of": last_month, "last_price": last,
        "history": [{"month": mo, "price": round(p, 2)} for mo, p in tail[-36:]],
        "forecast": [
            {"month": mo, "price": round(c, 2), "low": round(lo, 2), "high": round(hi, 2)}
            for mo, (c, lo, hi) in zip(months, fc)
        ],
        "method": {
            "name": choice.model, "description": MODEL_DESCRIPTIONS[choice.model],
            "beats_naive": choice.beats_naive,
            "past_error_pct": round(choice.mape_model * 100, 1),
            "naive_error_pct": round(choice.mape_naive * 100, 1),
            "n_past_forecasts": choice.n_origins,
        },
        "signal": signal, "message": message, "caveats": CAVEATS,
    }
