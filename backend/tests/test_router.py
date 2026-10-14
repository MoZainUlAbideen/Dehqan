import re

import pytest

from router.core import Agents, ask, detect_intents, find_city, find_commodity, fmt_window
from router.text import is_urdu, normalize

WINDOW = {"start": "2026-10-15T05:00:00", "end": "2026-10-15T18:00:00", "hours": 14}
MARKETS = ["Karachi", "Lahore", "Multan", "Peshawar", "Quetta"]


def analysis(commodity, market, signal="none", beats=False):
    return {
        "commodity": commodity, "market": market, "unit": "PKR per kg", "data_as_of": "2026-08", "last_price": 140.4,
        "signal": signal, "message": "No clear signal.", "method": {"beats_naive": beats},
        "forecast": [{"month": "2026-11", "price": 140.0, "low": 120.0, "high": 160.0}],
    }


class Calls:
    def __init__(self):
        self.log = []


def make_agents(calls: Calls, signal="none", beats=False) -> Agents:
    def spray(lat, lon):
        calls.log.append(("spray", lat, lon))
        return [WINDOW]

    def market(commodity, market_name):
        calls.log.append(("market", commodity, market_name))
        return analysis(commodity, market_name, signal, beats)

    def field(lat, lon):
        calls.log.append(("field", lat, lon))
        return {"message": "Uneven: about 26% of the patch is clearly less green.", "scenes_used": 20, "last_year": None,
                "latest": {"median": 0.7, "assessment": {"pattern": "patchy", "lagging_fraction": 0.26}}}

    return Agents(
        spray=spray,
        market_options=lambda: {"commodities": [{"name": n, "markets": MARKETS} for n in ("Wheat", "Wheat flour", "Rice (coarse)", "Rice (basmati, broken)", "Sugar", "Lentils (masur)", "Lentils (moong)", "Beans(mash)")]},
        market=market, field=field,
    )


def run(text, lat=None, lon=None, **kw):
    calls = Calls()
    return ask(text, make_agents(calls, **kw), lat, lon), calls.log


# ---------- text handling ----------
def test_normalize_unifies_urdu_letter_variants_and_drops_marks_and_punctuation():
    assert normalize("گندم!") == normalize("گندم") == "گندم"
    assert normalize("كيا") == normalize("کیا")                       # Arabic kaf and yeh
    assert normalize("بَارِش،  ہوگی؟") == "بارش ہوگی"                  # vowel marks, punctuation, spacing
    assert normalize("آٹا") == normalize("اٹا")                        # alef-madda is folded on both sides
    assert normalize("Price?? of Wheat") == "price of wheat" and normalize("۱۴۰ روپے") == "140 روپے"


def test_is_urdu_detects_urdu_script_only():
    assert is_urdu("گندم کی قیمت") and is_urdu("wheat کی قیمت") and not is_urdu("gandum ki qeemat")


# ---------- which intents are found ----------
@pytest.mark.parametrize("text,expected", [
    ("What is the weather for spraying tomorrow in Lahore?", {"weather"}),
    ("kal barish hogi kya spray ke liye", {"weather"}),
    ("کل بارش ہو گی؟ سپرے کب کروں", {"weather"}),
    ("Should I sell my wheat or hold? What is the price in Multan", {"market"}),
    ("gandum ka bhao kya hai", {"market"}),
    ("گندم کی قیمت کیا ہے", {"market"}),
    ("Check my field with satellite", {"field"}),
    ("mera khet kaisa hai satellite se", {"field"}),
    ("میرے کھیت کی حالت سیٹلائٹ سے دیکھیں", {"field"}),
    ("There are yellow spots on the leaves, what disease is it?", {"diagnosis"}),
    ("pattay peelay ho rahe hain bimari lagti hai", {"diagnosis"}),
    ("پتوں پر داغ ہیں، یہ کیا بیماری ہے", {"diagnosis"}),
    ("Which pesticide and what dose for rust?", {"treatment", "diagnosis"}),
    ("kon si dawai dalun kitni dawai", {"treatment"}),
    ("کون سی دوا ڈالوں اور کتنی مقدار", {"treatment"}),
    ("hello", set()),
    ("what is your name", set()),
])
def test_intent_detection(text, expected):
    assert {i.name for i in detect_intents(text)} == expected


def test_one_ambiguous_word_is_never_enough():
    for word in ("spray", "leaf", "field", "market", "yellow", "tomorrow", "سپرے", "پتے", "کھیت"):
        assert detect_intents(word) == [], word


def test_treatment_is_always_listed_first():
    assert detect_intents("price of wheat and which pesticide to use")[0].name == "treatment"


# ---------- finding the city and crop ----------
def test_find_city_in_english_roman_and_urdu():
    assert find_city("weather in lahore").name == "Lahore" and find_city("پشاور میں بارش").name == "Peshawar"
    assert find_city("faisalabad ka mausam").name == "Faisalabad" and find_city("فیصل آباد").name == "Faisalabad"
    assert find_city("weather today") is None


def test_find_commodity_prefers_the_longer_phrase_and_asks_when_ambiguous():
    assert find_commodity("wheat flour price") == "Wheat flour" and find_commodity("gandum ka bhao") == "Wheat"
    assert find_commodity("basmati rice rate") == "Rice (basmati, broken)" and find_commodity("chawal ka rate") == "Rice (coarse)"
    assert find_commodity("چینی کا نرخ") == "Sugar" and find_commodity("masur ki daal") == "Lentils (masur)"
    assert find_commodity("daal ka bhao") == "?" and find_commodity("hello") is None


# ---------- the safety route ----------
@pytest.mark.parametrize("text", [
    "which pesticide for my cotton", "what dose of tebuconazole per acre", "kitni dawai spray karun", "کیڑے مار دوا کی مقدار بتائیں",
    "how much to spray for aphids", "ilaj batao", "is chlorpyrifos ok", "mancozeb 500 ml per acre?",
])
def test_pesticide_questions_are_refused_without_calling_any_agent_or_giving_numbers(text):
    r, calls = run(text)
    assert r["route"] == "treatment" and calls == []
    assert r["results"]["treatment"] == {"refused": True}
    for answer in (r["answer_en"], r["answer_ur"]):
        assert not re.search(r"\d", answer), "a refusal must not contain a dose or any number"
    assert "extension office" in r["answer_en"] and "زرعی توسیعی دفتر" in r["answer_ur"]


# ---------- the specialist routes ----------
def test_weather_needs_a_place_then_uses_the_city_or_the_coordinates():
    r, calls = run("is it safe to spray tomorrow?")
    assert r["needs"] == "location" and calls == []
    r, calls = run("is it safe to spray tomorrow in Lahore?")
    assert calls == [("spray", 31.52, 74.36)] and "Thu 15 Oct 05:00-18:00" in r["answer_en"] and "جمعرات 15 اکتوبر" in r["answer_ur"]
    r, calls = run("when to spray", lat=34.0, lon=71.5)
    assert calls == [("spray", 34.0, 71.5)] and r["needs"] is None


def test_market_asks_for_the_crop_and_the_lentil_kind():
    assert run("what is the price")[0]["needs"] == "commodity"
    assert run("daal ka bhao lahore")[0]["needs"] == "crop_choice"


def test_market_uses_the_named_market_or_the_nearest_one_and_says_so():
    r, calls = run("wheat price in Lahore")
    assert calls == [("market", "Wheat", "Lahore")] and "retail prices" in r["answer_en"] and "گندم" in r["answer_ur"]
    r, calls = run("wheat price in Islamabad")                      # Islamabad has no price market: nearest is Peshawar
    assert calls == [("market", "Wheat", "Peshawar")] and "nearest price market to you is Peshawar" in r["answer_en"]
    r, calls = run("gandum ka bhao", lat=31.4, lon=73.1)            # coordinates near Faisalabad -> Lahore or Multan, whichever is nearer
    assert calls[0][0] == "market" and calls[0][2] in ("Lahore", "Multan")
    assert run("wheat price")[0]["needs"] == "location"


def test_market_answer_includes_the_signal_in_both_languages_and_honest_limits():
    r, _ = run("sell wheat in Multan?", signal="hold", beats=True)
    assert "hold" == r["results"]["market"]["signal"] and "انتظار" in r["answer_ur"]
    r, _ = run("sell wheat in Multan?", signal="none", beats=False)
    assert "جوں کی توں" in r["answer_ur"] and "estimate, not advice" in r["answer_en"]


def test_field_needs_exact_coordinates_and_never_states_a_cause():
    r, calls = run("check my field from satellite")
    assert r["needs"] == "coordinates" and calls == []
    r, calls = run("check my field from satellite", lat=31.3, lon=72.9)
    assert calls == [("field", 31.3, 72.9)] and "not the cause" in r["answer_en"] and "وجہ نہیں" in r["answer_ur"]
    assert "26%" in r["answer_en"] and "26%" in r["answer_ur"]


def test_diagnosis_always_asks_for_a_photo():
    r, calls = run("my wheat leaves have yellow rust spots")
    assert r["route"] == "diagnosis" and r["needs"] == "photo" and calls == []
    assert "photo" in r["answer_en"] and "تصویر" in r["answer_ur"]


def test_unknown_questions_get_the_help_text_and_no_agent_runs():
    r, calls = run("tell me a joke")
    assert r["route"] == "unknown" and calls == [] and r["intents"] == []
    assert "I can help with" in r["answer_en"] and "مدد" in r["answer_ur"]


def test_several_questions_in_one_are_answered_together_and_capped():
    r, calls = run("when to spray tomorrow in Lahore and what is the wheat price in Lahore")
    assert set(r["routes"]) == {"weather", "market"} and {c[0] for c in calls} == {"spray", "market"}
    r, _ = run("which pesticide, price of wheat, weather forecast, satellite field, leaf disease photo")
    assert len(r["routes"]) <= 3 and r["routes"][0] == "treatment"


def test_answer_follows_the_language_of_the_question_and_both_are_always_present():
    en, _ = run("wheat price in Lahore")
    ur, _ = run("لاہور میں گندم کی قیمت")
    assert en["language"] == "en" and en["answer"] == en["answer_en"]
    assert ur["language"] == "ur" and ur["answer"] == ur["answer_ur"]
    assert en["answer_ur"] and ur["answer_en"] and en["limitations"]


def test_window_formatting():
    assert fmt_window(WINDOW, "en") == "Thu 15 Oct 05:00-18:00"
    assert fmt_window(WINDOW, "ur") == "جمعرات 15 اکتوبر، 05:00 سے 18:00 تک"


# ---------- negation and spelling variants ----------
def test_english_negation_cancels_a_sell_or_hold_word_but_not_the_price_words():
    names = lambda t: {i.name for i in detect_intents(t)}
    assert names("I won't sell now, just tell me tomorrow's weather") == {"weather"}
    assert names("I do not want to hold, what is the price today") == {"market"}      # "price" still counts
    assert names("should I sell my wheat") == {"market"}                                # no negation: unchanged


def test_negation_never_switches_off_the_pesticide_refusal():
    for text in ("I don't know which pesticide to use", "no idea what dose, which medicine", "I cannot find the right insecticide"):
        assert "treatment" in {i.name for i in detect_intents(text)}, text


@pytest.mark.parametrize("text,expected", [
    ("kya mujhe gandum abhi bechni chahiye", "market"),
    ("fasal par daagh hain", "diagnosis"),
    ("کھیت میں کہیں کہیں فصل کمزور ہے", "field"),
])
def test_spelling_variants_found_by_the_dev_set_are_recognised(text, expected):
    assert expected in {i.name for i in detect_intents(text)}


def test_no_signal_answer_states_the_range_itself_and_never_points_at_a_chart_that_is_not_there():
    r, _ = run("sell wheat in Multan?", signal="none", beats=False)
    assert "between about 120 and 160" in r["answer_en"] and "below" not in r["answer_en"].lower()
    assert "120" in r["answer_ur"] and "160" in r["answer_ur"]
