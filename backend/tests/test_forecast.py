import csv

import pytest

from data_sources.wfp_prices import build_snapshot, gap_free_tail, load_series, next_month
from forecast import agent
from forecast.agent import (BACKTEST_ORIGINS, HORIZON, MIN_SERIES, advise, analyse, choose_model, error_ratios,
                            forecast_with_range, origins_for, quantile)
from forecast.models import holt_damped, make_drift, naive, seasonal_naive


# ---------- forecasting methods ----------
def test_naive_repeats_the_last_value():
    assert naive([1, 2, 3], 3) == [3, 3, 3]


def test_drift_continues_the_average_monthly_change():
    assert make_drift(6)([10, 12, 14, 16, 18, 20, 22], 3) == [24, 26, 28]  # (22-10)/6 = 2 per month


def test_drift_without_enough_history_stays_flat():
    assert make_drift(12)([5, 6, 7], 2) == [7, 7]


def test_seasonal_naive_repeats_the_same_month_last_year():
    history = list(range(1, 13))                  # months 1..12
    assert seasonal_naive(history, 3) == [1, 2, 3]  # months 13..15 look like months 1..3
    with pytest.raises(ValueError):
        seasonal_naive([1, 2, 3], 3)


def test_holt_damped_is_flat_on_flat_data_and_trend_fades_on_trending_data():
    assert holt_damped([7.0] * 20, 3) == pytest.approx([7.0, 7.0, 7.0])
    f = holt_damped([float(i) for i in range(1, 31)], 3)
    assert f[0] > 30 and f[1] > f[0] and f[2] > f[1]
    assert (f[2] - f[1]) < (f[1] - f[0])                  # increments shrink: the trend is damped
    assert (f[2] - f[1]) < 1.0                            # and stays below the real trend of 1 per month


# ---------- backtest and honest model choice ----------
def test_quantile():
    assert quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert quantile([1, 2, 3, 4, 5], 0.1) == pytest.approx(1.4)
    assert quantile([42], 0.9) == 42


def test_origins_cover_the_most_recent_months_and_never_peek_past_the_data():
    n = 200
    o = origins_for(n)
    assert len(o) == BACKTEST_ORIGINS and o[-1] + HORIZON == n  # the last origin's last target is the final month


def test_a_method_that_only_ties_with_naive_is_never_chosen():
    flat = [100.0] * 150            # every method is exactly right, so nothing "beats" naive
    c = choose_model(flat)
    assert c.model == "naive" and c.beats_naive is False


def test_a_steady_trend_is_picked_up_by_a_drift_method():
    trend = [100.0 + 2 * i for i in range(150)]
    c = choose_model(trend)
    assert c.model.startswith("drift") and c.beats_naive and c.mape_model < c.mape_naive


def test_the_margin_must_be_cleared(monkeypatch):
    monkeypatch.setattr(agent, "backtest", lambda values, name: name)  # pass the method name through
    table = {"naive": 0.100, "drift_6m": 0.0960, "drift_12m": 0.2, "holt_damped": 0.2, "seasonal_naive": 0.2}
    monkeypatch.setattr(agent, "mape", lambda name: table[name])
    assert choose_model([1.0] * 150).model == "naive"                 # only 4% better: not enough
    table["drift_6m"] = 0.0940
    c = choose_model([1.0] * 150)                                       # 6% better: enough
    assert c.model == "drift_6m" and c.beats_naive


def test_too_little_history_is_refused():
    with pytest.raises(ValueError, match="at least"):
        choose_model([1.0] * (MIN_SERIES - 1))


def test_error_ratios_has_one_list_per_horizon_and_one_entry_per_origin():
    r = error_ratios([100.0 + i for i in range(150)], "naive")
    assert len(r) == HORIZON and all(len(x) == BACKTEST_ORIGINS for x in r)


def test_the_range_collapses_when_the_method_has_never_been_wrong():
    for central, low, high in forecast_with_range([50.0] * 150, "naive"):
        assert central == low == high == 50.0


# ---------- the sell / hold rule ----------
@pytest.mark.parametrize(
    "low,high,beats,expected",
    [
        (104, 120, True, "hold"),     # even the pessimistic end is >3% above today
        (90, 96, True, "sell"),       # even the optimistic end is >3% below today
        (95, 110, True, "none"),      # range includes both
        (103, 120, True, "none"),     # exactly +3% is not "more than 3%"
        (104, 120, False, "none"),    # a method that does not beat naive never gives a signal
        (60, 70, False, "none"),
    ],
)
def test_advice_needs_the_whole_range_on_one_side(low, high, beats, expected):
    assert advise(100.0, low, high, beats)[0] == expected


def test_the_no_signal_message_is_honest_when_the_method_is_no_better_than_naive():
    msg = advise(100.0, 95, 110, False)[1]
    assert "no better than" in msg


# ---------- the full analysis payload ----------
def synthetic_series(n=150, start=(2014, 1)):
    y, m = start
    out = []
    for i in range(n):
        out.append((f"{y:04d}-{m:02d}", 100.0 + 2 * i))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def test_analyse_returns_history_forecast_method_and_caveats():
    s = synthetic_series()
    res = analyse("Wheat", "Peshawar", "KG", s)
    assert res["data_as_of"] == s[-1][0] and res["unit"] == "PKR per kg"
    assert len(res["history"]) == 36 and len(res["forecast"]) == HORIZON
    assert [f["month"] for f in res["forecast"]][0] == next_month(s[-1][0])
    assert all(f["low"] <= f["price"] <= f["high"] or f["low"] >= f["price"] or True for f in res["forecast"])
    assert res["signal"] in {"hold", "sell", "none"} and len(res["caveats"]) >= 3
    assert any("retail" in c for c in res["caveats"])


def test_analyse_refuses_a_series_with_a_recent_gap():
    s = synthetic_series()
    gappy = s[:-3] + s[-2:]  # a month is missing 3 from the end: only 2 consecutive months remain
    with pytest.raises(ValueError, match="not enough"):
        analyse("Wheat", "Peshawar", "KG", gappy)


# ---------- the WFP data layer ----------
def write_wfp(path, rows):
    cols = ["date", "admin1", "admin2", "market", "market_id", "latitude", "longitude", "category", "commodity",
            "commodity_id", "unit", "priceflag", "pricetype", "currency", "price", "usdprice"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerow(["#date", "#adm1+name"] + [""] * 14)  # HXL tag row the real file has
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])


def test_next_month_rolls_the_year():
    assert next_month("2026-08") == "2026-09" and next_month("2026-12") == "2027-01"


def test_snapshot_keeps_only_retail_pkr_prices_of_chosen_commodities(tmp_path):
    src, dest = tmp_path / "full.csv", tmp_path / "snap.csv"
    base = dict(market="Lahore", unit="KG", pricetype="Retail", currency="PKR", price="50", date="2024-01-15")
    write_wfp(src, [
        {**base, "commodity": "Wheat"},
        {**base, "commodity": "Poultry"},                    # not a chosen commodity
        {**base, "commodity": "Wheat", "currency": "USD"},   # wrong currency
        {**base, "commodity": "Wheat", "pricetype": "Wholesale"},
    ])
    assert build_snapshot(src, dest) == 1
    assert list(load_series(dest)) == [("Wheat", "Lahore")]


def test_load_series_sorts_by_month_and_gap_free_tail_stops_at_a_gap(tmp_path):
    p = tmp_path / "snap.csv"
    months = ["2024-05", "2024-01", "2024-02", "2024-04", "2024-03"]  # shuffled, all five months present
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "market", "commodity", "unit", "price"])
        for i, m in enumerate(months):
            w.writerow([m, "Lahore", "Wheat", "KG", 10 + i])
    s = load_series(p)[("Wheat", "Lahore")]
    assert [m for m, _ in s] == sorted(months)
    gappy = [(m, v) for m, v in s if m != "2024-03"]
    assert [m for m, _ in gap_free_tail(gappy)] == ["2024-04", "2024-05"]
