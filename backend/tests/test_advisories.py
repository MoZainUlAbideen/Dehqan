from rag.advisories import advise, load, normalize_pest, parse
from rag.guardrail import contains_phrase

ENTRIES, TEXTS, META = load()


def test_parses_the_known_tables():
    by = {(e.pest, e.product): e.dose for e in ENTRIES}
    assert by[("thrips", "Spintoram 120 SC")] == "60 mL"
    assert by[("pink bollworm", "Deltamethrin + Triazophos 36 EC")] == "500-600 ml"
    assert by[("mealy bug", "Sulfuxaflor 50% WG/240 SC")] == "40-50 g/80-100 ml"
    assert by[("jassid", "Flonicamid 50% WDG")] == "60 g"


def test_row_counts_match_the_printed_tables():
    n = lambda p: len([e for e in ENTRIES if e.pest == p])
    assert (n("thrips"), n("jassid"), n("mealy bug"), n("pink bollworm")) == (5, 4, 4, 11)
    assert n("whitefly") == 9   # row 2 prints "125 ml + Adjacent" (a tank-mix note): not a clean dose, skipped not guessed


def test_unclean_row_is_skipped_not_guessed():
    text = "Chemical Control of Whitefly\n2 Spirotetramat 240 SC + Bio Power (IGR) 125 ml + Adjacent\n"
    assert parse("s", "cotton", text) == []


def test_headings_end_a_table():
    text = "Chemical Control of Thrips\n1 Abamectin 1.8 EC 200 ml\nPink Bollworm\n2 Fake Product 1 EC 999 ml\n"
    assert [e.product for e in parse("s", "cotton", text)] == ["Abamectin 1.8 EC"]


def test_every_option_quote_really_is_in_the_source():
    for pest in ("thrips", "jassid", "whitefly", "pink bollworm", "mealy bug"):
        r = advise("cotton", pest, ENTRIES, TEXTS, META)
        assert r["options"]
        for o in r["options"]:
            assert contains_phrase(TEXTS["punjab_cotton_2026-10_w1"], o["quote"])
            assert o["dose_per_acre"] in o["quote"]


def test_aliases_and_urdu_pest_names():
    assert normalize_pest("White fly") == "whitefly" and normalize_pest("سفید مکھی") == "whitefly" and normalize_pest("PBW") == "pink bollworm"


def test_unknown_pest_or_crop_returns_nothing_not_a_guess():
    assert not advise("cotton", "locust", ENTRIES, TEXTS, META)["available"]
    assert not advise("wheat", "aphid", ENTRIES, TEXTS, META)["available"]   # the wheat bulletin has no treatment table


def test_answers_always_disclose_the_missing_registered_list_and_ppe():
    r = advise("cotton", "thrips", ENTRIES, TEXTS, META)
    text = " ".join(r["notes"])
    assert "NOT checked against the national registered-pesticide list" in text and r["ppe"] is None
