"""Serves market analyses to the API: loads the committed price snapshot once and caches each answer."""

import json
from functools import lru_cache

from data_sources.wfp_prices import gap_free_tail, load_series, unit_of
from forecast.agent import MIN_SERIES, analyse

from pathlib import Path

SUMMARY_FILE = Path(__file__).parent / "eval_summary.json"


@lru_cache(maxsize=1)
def _series():
    return load_series()


@lru_cache(maxsize=1)
def _summary() -> dict | None:
    try:
        return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def eligible() -> dict[tuple[str, str], list]:
    """Series with enough consecutive recent months to be forecast at all."""
    return {k: s for k, s in _series().items() if len(gap_free_tail(s)) >= MIN_SERIES}


@lru_cache(maxsize=1)
def options() -> dict:
    by: dict[str, list[str]] = {}
    for commodity, market in sorted(eligible()):
        by.setdefault(commodity, []).append(market)
    latest = max(tail[-1][0] for tail in (gap_free_tail(s) for s in eligible().values()))
    return {
        "commodities": [{"name": c, "unit": f"PKR per {unit_of(c).lower()}", "markets": m} for c, m in by.items()],
        "data_as_of": latest,
        "source": "World Food Programme (WFP) food prices for Pakistan, via the Humanitarian Data Exchange (CC BY-IGO)",
    }


@lru_cache(maxsize=64)
def analysis(commodity: str, market: str) -> dict:
    """Raises KeyError if the series does not exist or is too gappy to forecast."""
    series = eligible().get((commodity, market))
    if series is None:
        raise KeyError((commodity, market))
    result = analyse(commodity, market, unit_of(commodity), series)
    summary = _summary()
    if summary:
        c = summary["by_commodity"].get(commodity)
        result["track_record"] = {
            "months_checked": summary["evaluated_months"],
            "range_target": summary["target_coverage"],
            "range_actually_contained_outcome": c["coverage"] if c else None,
            "agent_error_pct": c["agent_error_pct"] if c else None,
            "naive_error_pct": c["naive_error_pct"] if c else None,
            "note": "Measured by replaying the last 12 months using only data available at the time.",
        }
    result["source"] = options()["source"]
    return result
