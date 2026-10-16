"""Supervisor router: read a farmer's question, decide which specialist agent(s) should answer, run them, and reply
in English and Urdu.

How it understands: weighted keyword matching over English, Roman Urdu and Urdu script (see lexicon.py). It has no
language model, so it can miss unusual wording; when it finds nothing it says what it CAN help with instead of
guessing. The router never answers a "which pesticide / how much" question: that route is a fixed, honest refusal
until official Pakistani lists and advisories are loaded (rag/guardrail.py enforces the same rule for any future
treatment answer).

All Urdu text below is a first draft by the developer and needs a native-speaker review.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from router.lexicon import AMBIGUOUS_COMMODITY, COMMODITIES, COMMODITY_URDU, NORMALISED, THRESHOLD
from router.places import BY_NAME, CITIES, City, nearest
from router.text import contains_phrase, is_urdu, normalize, tokens

MAX_ROUTES = 3

# English negation ("I won't sell", "do not hold") cancels a sell/hold word. Only these words, only in English, and never
# for the pesticide route: a refusal must not be skipped on a technicality. Urdu puts the negative AFTER the verb
# ("بیچنا نہیں چاہتا"), which this does not handle (a known limit).
NEGATIONS = {"not", "no", "never", "dont", "don", "won", "wont", "doesnt", "didnt", "cant", "cannot"}
NEGATABLE = {"sell", "selling", "hold", "holding", "sell now", "wait or sell"}
NEGATION_WINDOW = 3
LIMITATIONS = [
    "Understanding is keyword-based: unusual wording can be missed.",
    "Answers come from the same specialist tools as the other pages, with the same limits.",
]
EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
UR_DAYS = ["پیر", "منگل", "بدھ", "جمعرات", "جمعہ", "ہفتہ", "اتوار"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
UR_MONTHS = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"]


@dataclass(frozen=True)
class Agents:
    """The specialist agents, passed in so the router can be tested without the network."""
    spray: Callable[[float, float], tuple[list[dict], str]]  # lat, lon -> (safe windows [{"start","end","hours"}], weather source name)
    market_options: Callable[[], dict]                 # -> {"commodities": [{"name", "markets": [...]}]}
    market: Callable[[str, str], dict]                 # commodity, market -> analysis (KeyError if none)
    field: Callable[[float, float], dict]              # lat, lon -> field report


@dataclass
class Part:
    name: str
    en: str
    ur: str
    data: dict | None = None
    needs: str | None = None   # what is missing: photo | location | coordinates | commodity | crop_choice


@dataclass
class Intent:
    name: str
    score: int
    matched: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ understanding
def _negated(words: list[str], phrase: str) -> bool:
    """True if an English negation appears within NEGATION_WINDOW words before the phrase."""
    parts = phrase.split()
    for i in range(len(words) - len(parts) + 1):
        if words[i : i + len(parts)] == parts and any(w in NEGATIONS for w in words[max(0, i - NEGATION_WINDOW) : i]):
            return True
    return False


def detect_intents(text: str) -> list[Intent]:
    """Every intent whose keyword score reaches THRESHOLD, strongest first. Treatment is always listed first."""
    norm = normalize(text)
    words = tokens(text)
    found = []
    for name, entries in NORMALISED.items():
        matched = [p for p, _ in entries if contains_phrase(norm, p) and not (name == "market" and p in NEGATABLE and _negated(words, p))]
        score = sum(w for p, w in entries if p in matched)
        if score >= THRESHOLD:
            found.append(Intent(name, score, matched))
    found.sort(key=lambda i: (i.name != "treatment", -i.score))
    return found


def find_city(text: str) -> City | None:
    norm = normalize(text)
    for c in CITIES:
        if any(contains_phrase(norm, a) for a in c.aliases):
            return c
    return None


def find_commodity(text: str) -> str | None:
    """A crop name the market agent knows, "?" if the farmer said just "daal", or None."""
    norm = normalize(text)
    for name, aliases in COMMODITIES:
        if any(contains_phrase(norm, a) for a in aliases):
            return name
    if any(contains_phrase(norm, a) for a in AMBIGUOUS_COMMODITY):
        return "?"
    return None


# ------------------------------------------------------------------ formatting helpers
def _when(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def urdu_period(hour: int) -> str:
    """The word Urdu speakers put before a clock time: صبح (morning), دوپہر (midday), سہ پہر (afternoon), شام (evening), رات (night)."""
    if 4 <= hour <= 11:
        return "صبح"
    if 12 <= hour <= 14:
        return "دوپہر"
    if 15 <= hour <= 16:
        return "سہ پہر"
    if 17 <= hour <= 19:
        return "شام"
    return "رات"


def urdu_clock(t: datetime) -> tuple[str, str]:
    """(period word, 'N بجے') for a time, on the 12-hour clock: 18:00 -> ('شام', '6 بجے'). Half hours read 'ساڑھے N بجے'."""
    h12 = t.hour % 12 or 12
    if t.minute == 0:
        return urdu_period(t.hour), f"{h12} بجے"
    if t.minute == 30:
        return urdu_period(t.hour), f"ساڑھے {h12} بجے"
    return urdu_period(t.hour), f"{h12}:{t.minute:02d} بجے"


def urdu_time_range(s: datetime, e: datetime) -> str:
    """'صبح 5 بجے سے شام 6 بجے تک'; when both ends fall in the same part of the day: 'صبح 5 سے 9 بجے تک'."""
    (p1, c1), (p2, c2) = urdu_clock(s), urdu_clock(e)
    if p1 == p2 and s.minute == 0 and e.minute == 0:
        return f"{p1} {s.hour % 12 or 12} سے {c2} تک"
    return f"{p1} {c1} سے {p2} {c2} تک"


def fmt_window(w: dict, lang: str) -> str:
    s, e = _when(w["start"]), _when(w["end"])
    if lang == "ur":
        return f"{UR_DAYS[s.weekday()]} {s.day} {UR_MONTHS[s.month - 1]}، {urdu_time_range(s, e)}"
    return f"{EN_DAYS[s.weekday()]} {s.day} {EN_MONTHS[s.month - 1][:3]} {s:%H:%M}-{e:%H:%M}"


def month_label(ym: str, lang: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{(UR_MONTHS if lang == 'ur' else EN_MONTHS)[m - 1]} {y}"


# ------------------------------------------------------------------ the specialist handlers
def weather_part(city: City | None, lat: float | None, lon: float | None, agents: Agents) -> Part:
    if city is None and lat is None:
        return Part("weather", "Which city is this for? Write its name (for example Lahore, Peshawar or Multan).",
                    "کس شہر کے لیے؟ شہر کا نام لکھیں (مثلاً لاہور، پشاور یا ملتان)۔", needs="location")
    if lat is None:
        lat, lon = city.lat, city.lon
    name_en = city.name if city else "your location"
    name_ur = city.urdu if city else "آپ کے مقام"
    all_windows, source = agents.spray(lat, lon)
    windows = all_windows[:3]
    backup = source != "open-meteo"
    span_en, span_ur = ("2", "دو") if backup else ("5", "پانچ")   # the backup source only covers about 2 days
    note_en = " (Backup weather source in use: about 2 days only, and no wind-gust or rain-probability data.)" if backup else ""
    note_ur = " (متبادل موسمی ذریعہ استعمال ہو رہا ہے: صرف تقریباً دو دن، اور ہوا کے جھکڑ یا بارش کے امکان کے اعداد و شمار کے بغیر۔)" if backup else ""
    if not windows:
        return Part("weather", f"No safe spray window was found in {name_en} in the next {span_en} days (wind, rain or heat)." + note_en,
                    f"{name_ur} میں اگلے {span_ur} دنوں میں سپرے کا کوئی محفوظ وقت نہیں ملا (ہوا، بارش یا گرمی کی وجہ سے)۔" + note_ur, {"windows": [], "source": source})
    en = "; ".join(fmt_window(w, "en") for w in windows)
    ur = "؛ ".join(fmt_window(w, "ur") for w in windows)
    return Part(
        "weather",
        f"Safe spray windows in {name_en} over the next {span_en} days: {en}. These limits are rules of thumb, not official advice; check the product label for its rain-free time." + note_en,
        f"{name_ur} میں اگلے {span_ur} دنوں میں سپرے کے محفوظ اوقات: {ur}۔ یہ حدیں عام اصول ہیں، سرکاری مشورہ نہیں؛ دوا کے لیبل پر بارش سے محفوظ رہنے کا وقت ضرور دیکھیں۔" + note_ur,
        {"windows": windows, "source": source},
    )


_SIGNAL_UR = {
    "hold": "ماضی میں قیمتیں یہاں سے بڑھتی رہی ہیں؛ اگر آپ محفوظ طریقے سے ذخیرہ کر سکتے ہیں تو انتظار فائدہ مند ہو سکتا ہے۔",
    "sell": "ماضی میں قیمتیں یہاں سے گرتی رہی ہیں؛ جلد بیچنا بہتر ہو سکتا ہے۔",
    "none_beats": "کوئی واضح اشارہ نہیں: امکانی دائرے میں اضافہ اور کمی دونوں شامل ہیں۔ فیصلہ اپنے اخراجات اور ضرورت کے مطابق کریں۔",
    "none_naive": "ہمارا اندازہ لگانے کا طریقہ \"قیمتیں جوں کی توں رہیں گی\" سے بہتر نہیں، اس لیے کوئی قابل اعتماد اشارہ نہیں۔",
}


def market_part(commodity: str | None, city: City | None, lat: float | None, lon: float | None, agents: Agents) -> Part:
    if commodity is None:
        return Part("market", "Which crop's price do you want? I have wheat, flour, rice, basmati, sugar, masur, moong and mash.",
                    "کس فصل کا نرخ چاہیے؟ میرے پاس گندم، آٹا، چاول، باسمتی، چینی، مسور، مونگ اور ماش کے نرخ ہیں۔", needs="commodity")
    if commodity == "?":
        return Part("market", "Which lentil: masur, moong or mash?", "کون سی دال: مسور، مونگ یا ماش؟", needs="crop_choice")
    markets = next((c["markets"] for c in agents.market_options()["commodities"] if c["name"] == commodity), [])
    if not markets:
        return Part("market", f"I do not have a reliable price history for {commodity}.", f"{COMMODITY_URDU[commodity]} کی قابل اعتماد قیمتوں کی تاریخ میرے پاس نہیں۔")
    if city and city.name in markets:
        market, note_en, note_ur = city.name, "", ""
    elif city or lat is not None:
        ref_lat, ref_lon = (lat, lon) if lat is not None else (city.lat, city.lon)
        near = nearest(ref_lat, ref_lon, markets)
        market = near.name
        note_en = f" (the nearest price market to you is {near.name})"
        note_ur = f" (آپ کے سب سے قریب نرخ کی منڈی {near.urdu} ہے)"
    else:
        return Part("market", "Which city's market? I have prices for " + ", ".join(markets) + ".",
                    "کس شہر کی منڈی؟ میرے پاس نرخ ہیں: " + "، ".join(BY_NAME[m].urdu for m in markets) + "۔", needs="location")
    try:
        a = agents.market(commodity, market)
    except KeyError:
        return Part("market", f"I do not have a reliable price history for {commodity} in {market}.", f"{market} میں {COMMODITY_URDU[commodity]} کی قابل اعتماد قیمتوں کی تاریخ میرے پاس نہیں۔")
    end = a["forecast"][-1]
    price = round(a["last_price"])
    key = "hold" if a["signal"] == "hold" else "sell" if a["signal"] == "sell" else ("none_beats" if a["method"]["beats_naive"] else "none_naive")
    lo, hi = round(end["low"]), round(end["high"])
    message_en = a["message"]
    message_ur = _SIGNAL_UR[key]
    if key == "none_naive":  # the agent's own wording points at a chart on its page; here there is none, so state the range
        message_en = ("Our forecasting method is no better than simply assuming prices stay where they are, so there is no reliable signal. "
                      f"Three months ahead, past forecasts of this kind landed between about {lo} and {hi} {a['unit']}.")
        message_ur += f" تین ماہ بعد اس طرح کے ماضی کے اندازے تقریباً {lo} سے {hi} روپے فی کلو کے درمیان رہے ہیں۔"
    en = (f"{commodity} in {market}{note_en}: the latest price ({month_label(a['data_as_of'], 'en')}) is {price} {a['unit']}. {message_en} "
          "Remember: these are retail prices, not what you are paid at the mandi, and this is an estimate, not advice.")
    ur = (f"{COMMODITY_URDU[commodity]} ({BY_NAME[market].urdu}){note_ur}: تازہ ترین قیمت ({month_label(a['data_as_of'], 'ur')}) {price} روپے فی کلو ہے۔ {message_ur} "
          "یاد رکھیں: یہ خوردہ قیمتیں ہیں، منڈی میں کسان کو ملنے والا بھاؤ نہیں، اور یہ صرف اندازہ ہے، مشورہ نہیں۔")
    data = {"commodity": commodity, "market": market, "last_price": a["last_price"], "unit": a["unit"], "data_as_of": a["data_as_of"],
            "signal": a["signal"], "beats_naive": a["method"]["beats_naive"], "forecast_end": {k: end[k] for k in ("month", "price", "low", "high")}}
    return Part("market", en, ur, data)


_FIELD_UR = {
    "bare": "زیادہ تر ننگی زمین یا بہت کم ہریالی ہے: ابھی فصل کا جائزہ لینے کے لیے کچھ خاص نہیں (یا زمین خالی ہے)۔",
    "even": "کھیت کا یہ حصہ ہموار ہے: ہریالی ہر جگہ تقریباً یکساں ہے، اس حصے میں کسی مسئلے کا اشارہ نہیں۔",
    "mixed": "حصے میں کچھ فرق ہے، مگر کسی ایک جگہ واضح نہیں۔",
    "unknown": "پچھلے سال میں اس جگہ کی کوئی صاف سیٹلائٹ تصویر نہیں ملی۔",
}


def field_part(lat: float | None, lon: float | None, agents: Agents) -> Part:
    if lat is None:
        return Part("field", "To look at your field from space I need its exact location: open the Field page and drop your pin (or send latitude and longitude).",
                    "کھیت کو سیٹلائٹ سے دیکھنے کے لیے مجھے اس کا درست مقام چاہیے: \"خلا سے کھیت کی جانچ\" صفحہ کھولیں اور اپنا پن لگائیں (یا عرض البلد اور طول البلد بھیجیں)۔", needs="coordinates")
    r = agents.field(lat, lon)
    latest = r.get("latest")
    pattern = latest["assessment"]["pattern"] if latest else "unknown"
    ur_msg = (f"ناہموار: تقریباً {round(latest['assessment']['lagging_fraction'] * 100)}% حصہ باقی حصے سے واضح طور پر کم ہرا ہے۔ یہ پورے کھیت کے بجائے کھیت کے ایک حصے میں مسئلے کی طرف اشارہ ہے۔"
              if pattern == "patchy" else _FIELD_UR[pattern])
    en = r["message"] + " This shows greenness only, not the cause."
    ur = ur_msg + " یہ صرف ہریالی دکھاتا ہے، وجہ نہیں۔"
    return Part("field", en, ur, {"pattern": pattern, "median_ndvi": latest["median"] if latest else None, "scenes_used": r["scenes_used"], "last_year": r["last_year"]})


def diagnosis_part() -> Part:
    return Part("diagnosis",
                "To check a sick plant I need a photo: open the Diagnose page and send one clear, close photo of a single leaf. I cannot diagnose from words alone.",
                "بیمار پودے کی جانچ کے لیے مجھے تصویر چاہیے: \"پتے کی تشخیص\" صفحہ کھولیں اور ایک پتے کی صاف، قریب سے تصویر بھیجیں۔ میں صرف الفاظ سے تشخیص نہیں کر سکتا۔",
                needs="photo")


def treatment_part() -> Part:
    return Part("treatment",
                "I cannot name pesticides or doses yet: the official Pakistani registered-pesticide lists and advisories are not loaded, and I never guess. Please ask your local agriculture extension office.",
                "میں ابھی کیڑے مار ادویات کے نام یا مقدار نہیں بتا سکتا: پاکستان کی سرکاری فہرستیں ابھی میرے پاس موجود نہیں، اور میں اندازے سے کچھ نہیں بتاتا۔ براہ کرم اپنے مقامی زرعی توسیعی دفتر سے رجوع کریں۔",
                {"refused": True})


def help_part() -> Part:
    return Part("unknown",
                "I can help with: checking a sick leaf from a photo, safe spray times, market price history, and a satellite look at your field. Please ask about one of these.",
                "میں ان چیزوں میں مدد کر سکتا ہوں: تصویر سے بیمار پتے کی جانچ، سپرے کا محفوظ وقت، منڈی کے نرخ کی تاریخ، اور سیٹلائٹ سے کھیت کی جانچ۔ اپنا سوال ان میں سے کسی کے بارے میں لکھیں۔")


# ------------------------------------------------------------------ the supervisor
def ask(text: str, agents: Agents, lat: float | None = None, lon: float | None = None) -> dict:
    """Route one question. Returns the answer in both languages, which agents answered, and what was understood."""
    lang = "ur" if is_urdu(text) else "en"
    intents = detect_intents(text)[:MAX_ROUTES]
    city, commodity = find_city(text), find_commodity(text)

    parts: list[Part] = []
    for it in intents:
        if it.name == "treatment":
            parts.append(treatment_part())
        elif it.name == "weather":
            parts.append(weather_part(city, lat, lon, agents))
        elif it.name == "market":
            parts.append(market_part(commodity, city, lat, lon, agents))
        elif it.name == "field":
            parts.append(field_part(lat, lon, agents))
        elif it.name == "diagnosis":
            parts.append(diagnosis_part())
    if not parts:
        parts.append(help_part())

    answer_en = "\n\n".join(p.en for p in parts)
    answer_ur = "\n\n".join(p.ur for p in parts)
    return {
        "language": lang,
        "route": parts[0].name,
        "routes": [p.name for p in parts],
        "intents": [{"name": i.name, "score": i.score, "matched": i.matched} for i in intents],
        "understood": {"city": city.name if city else None, "commodity": None if commodity in (None, "?") else commodity, "has_coordinates": lat is not None},
        "needs": next((p.needs for p in parts if p.needs), None),
        "answer": answer_ur if lang == "ur" else answer_en,
        "answer_en": answer_en,
        "answer_ur": answer_ur,
        "results": {p.name: p.data for p in parts if p.data is not None},
        "limitations": LIMITATIONS,
    }
