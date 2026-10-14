from datetime import datetime, timedelta, timezone

from app import field_service
from app.field_service import field_report, nearest_last_year


def pt(day, median, valid=1.0):
    return {"date": day, "median": median, "valid_fraction": valid, "assessment": {"message": f"msg {day}"}, "grid": [[median]]}


def days_ago(n):
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def test_nearest_last_year_picks_the_closest_scene_within_three_weeks():
    pts = [pt("2025-03-01", 0.5), pt("2025-03-20", 0.6), pt("2025-06-01", 0.3)]
    assert nearest_last_year(pts, "2026-03-22")["date"] == "2025-03-20"       # about 367 days earlier
    assert nearest_last_year(pts, "2026-09-01") is None                         # nothing near Sept 2025


def test_report_has_latest_message_comparison_and_caveats():
    field_service._cache.clear()
    latest_day, old_day = days_ago(5), days_ago(5 + 365)
    tl = {"scenes_found": 9, "scenes_failed": 0, "scenes_timed_out": 0, "seconds": 1.0, "points": [pt(old_day, 0.5), pt(days_ago(100), 0.4), pt(latest_day, 0.4)]}
    r = field_report(34.0, 71.5, 300, timeline=lambda lat, lon, half_m, months: tl)
    assert r["latest"]["date"] == latest_day and r["message"] == f"msg {latest_day}"
    assert r["last_year"]["change_pct"] == -20.0 and r["last_year"]["last_year_date"] == old_day
    assert all(p["date"] >= days_ago(366) for p in r["points"])               # only the last 12 months are shown
    assert r["scenes_used"] == 2 and len(r["caveats"]) >= 4 and "Sentinel" in r["source"]


def test_empty_answers_say_so_and_are_not_cached_but_good_ones_are():
    field_service._cache.clear()
    calls = []

    def empty(lat, lon, half_m, months):
        calls.append(1)
        return {"scenes_found": 0, "scenes_failed": 0, "scenes_timed_out": 0, "seconds": 0.1, "points": []}

    assert "No clear satellite view" in field_report(31.0, 73.0, 300, timeline=empty)["message"]
    field_report(31.0, 73.0, 300, timeline=empty)
    assert len(calls) == 2                                                       # not cached

    good = {"scenes_found": 1, "scenes_failed": 0, "scenes_timed_out": 0, "seconds": 0.1, "points": [pt(days_ago(3), 0.6)]}
    n = []
    f = lambda lat, lon, half_m, months: (n.append(1), good)[1]
    a = field_report(32.0, 72.0, 300, timeline=f, now=1000.0)
    b = field_report(32.0004, 72.0004, 300, timeline=f, now=1500.0)             # same ~100 m cell, within 6 h
    assert a is b and len(n) == 1
    field_report(32.0, 72.0, 300, timeline=f, now=1000.0 + field_service.CACHE_SECONDS + 1)
    assert len(n) == 2                                                           # expired
