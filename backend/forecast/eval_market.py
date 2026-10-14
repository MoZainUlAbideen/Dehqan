"""Evaluate the market agent the way it is used: walk forward month by month, using only data from before each date.

Usage (from backend/):
    uv run python -m forecast.eval_market

For every eligible price series and each of the last 12 forecast dates (cutoffs):
  1. take only the history before the cutoff,
  2. let the agent choose its method (so the choice never sees the future) and build its forecast and range,
  3. compare with what prices actually did over the next 3 months.
Reported against the simple baseline "prices stay the same" (naive):
  - average percentage error of the agent vs naive, and how many series the agent improved
  - how often the agent chose something other than naive
  - whether the 10th-90th percentile range really contained the outcome about 80% of the time
Writes evals/market_forecast.json.
"""

import json
from collections import defaultdict
from pathlib import Path

from data_sources.wfp_prices import gap_free_tail, load_series
from forecast.agent import HORIZON, MIN_SERIES, choose_model, forecast_with_range
from forecast.models import MODELS
from vision.train_baseline import EVALS_DIR

N_CUTOFFS = 12
SUMMARY_FILE = Path(__file__).parent / "eval_summary.json"


def evaluate_series(values: list[float]) -> dict:
    n = len(values)
    agent_err, naive_err, fixed_err = [], [], defaultdict(list)
    inside, inside_by_h, picks = 0, [0] * HORIZON, 0
    total = 0
    for t in range(n - HORIZON - N_CUTOFFS + 1, n - HORIZON + 1):
        hist, actual = values[:t], values[t : t + HORIZON]
        if len(hist) < MIN_SERIES:
            continue
        choice = choose_model(hist)
        picks += choice.model != "naive"
        fc = forecast_with_range(hist, choice.model)
        nv = MODELS["naive"](hist, HORIZON)
        for h in range(HORIZON):
            c, lo, hi = fc[h]
            a = actual[h]
            agent_err.append(abs(a - c) / a)
            naive_err.append(abs(a - nv[h]) / a)
            for name, f in MODELS.items():
                try:
                    fixed_err[name].append(abs(a - f(hist, HORIZON)[h]) / a)
                except ValueError:
                    pass
            hit = lo <= a <= hi
            inside += hit
            inside_by_h[h] += hit
            total += 1
    cutoffs = total // HORIZON
    mean = lambda xs: sum(xs) / len(xs)
    return {
        "n_cutoffs": cutoffs,
        "agent_mape": mean(agent_err), "naive_mape": mean(naive_err),
        "chose_non_naive": picks / cutoffs,
        "coverage": inside / total, "coverage_by_horizon": [x / cutoffs for x in inside_by_h],
        "fixed_mape": {k: mean(v) for k, v in fixed_err.items()},
    }


def main() -> None:
    series = load_series()
    per_series, by_commodity = {}, defaultdict(list)
    for (commodity, market), s in sorted(series.items()):
        values = [p for _, p in gap_free_tail(s)]
        if len(values) < MIN_SERIES + N_CUTOFFS:
            continue
        r = evaluate_series(values)
        per_series[f"{commodity} | {market}"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "fixed_mape"}
        by_commodity[commodity].append(r)
        print(f"{commodity:24}{market:10} agent {r['agent_mape']*100:5.1f}%  naive {r['naive_mape']*100:5.1f}%  non-naive picks {r['chose_non_naive']*100:3.0f}%  coverage {r['coverage']*100:3.0f}%", flush=True)

    all_r = [r for rs in by_commodity.values() for r in rs]
    mean = lambda xs: sum(xs) / len(xs)
    better = sum(r["agent_mape"] < r["naive_mape"] - 1e-9 for r in all_r)
    worse = sum(r["agent_mape"] > r["naive_mape"] + 1e-9 for r in all_r)
    fixed = defaultdict(list)
    for r in all_r:
        for k, v in r["fixed_mape"].items():
            fixed[k].append(v)
    result = {
        "what": "Walk-forward replay of the market agent on WFP Pakistan retail prices (monthly), last 12 forecast dates, 3 months ahead",
        "n_series": len(all_r),
        "n_forecasts_per_series": N_CUTOFFS * HORIZON,
        "mean_error_pct": {"agent": round(mean([r["agent_mape"] for r in all_r]) * 100, 2), "naive_baseline": round(mean([r["naive_mape"] for r in all_r]) * 100, 2)},
        "series_agent_better_than_naive": better,
        "series_agent_worse_than_naive": worse,
        "series_tied": len(all_r) - better - worse,
        "share_of_forecast_dates_where_agent_used_a_method_other_than_naive": round(mean([r["chose_non_naive"] for r in all_r]), 3),
        "range_coverage": {
            "target": 0.80,
            "observed_all_horizons": round(mean([r["coverage"] for r in all_r]), 3),
            "observed_by_horizon_months": [round(mean([r["coverage_by_horizon"][h] for r in all_r]), 3) for h in range(HORIZON)],
        },
        "fixed_method_mean_error_pct_for_context": {k: round(mean(v) * 100, 2) for k, v in sorted(fixed.items())},
        "by_commodity": {
            c: {"agent_error_pct": round(mean([r["agent_mape"] for r in rs]) * 100, 2), "naive_error_pct": round(mean([r["naive_mape"] for r in rs]) * 100, 2), "coverage": round(mean([r["coverage"] for r in rs]), 3)}
            for c, rs in sorted(by_commodity.items())
        },
        "per_series": per_series,
    }
    EVALS_DIR.mkdir(exist_ok=True)
    (EVALS_DIR / "market_forecast.json").write_text(json.dumps(result, indent=2))
    # A small copy ships with the API (the deployed image has no evals/ folder) so each answer can show how far
    # its range has deserved to be trusted.
    summary = {
        "evaluated_months": N_CUTOFFS,
        "target_coverage": 0.8,
        "overall": {"agent_error_pct": result["mean_error_pct"]["agent"], "naive_error_pct": result["mean_error_pct"]["naive_baseline"], "coverage": result["range_coverage"]["observed_all_horizons"]},
        "by_commodity": result["by_commodity"],
    }
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps({k: v for k, v in result.items() if k not in ("per_series", "what")}, indent=2))


if __name__ == "__main__":
    main()
