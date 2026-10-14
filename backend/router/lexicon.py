"""Keywords for each kind of question, in English, Roman Urdu and Urdu script.

Each entry is (phrase, weight). A strong word (2) can decide an intent alone; a weak word (1) is ambiguous on its own
("spray", "leaf", "field") and only counts together with something else. An intent needs a total of THRESHOLD.
Phrases are matched as whole words after normalisation (see text.normalize), so spelling variants are listed.

THIS LIST NEEDS A NATIVE-SPEAKER REVIEW: it was written by the developer, and real farmers type more variants.
"""

from router.text import normalize

THRESHOLD = 2

S, W = 2, 1  # strong, weak

LEXICON: dict[str, list[tuple[str, int]]] = {
    "weather": [
        ("weather", S), ("forecast", S), ("rain", S), ("raining", S), ("rainfall", S), ("windy", S), ("wind", S),
        ("safe to spray", S), ("spray window", S), ("spray time", S), ("when to spray", S),
        ("mausam", S), ("barish", S), ("baarish", S), ("barsaat", S), ("andhi", S), ("tez hawa", S), ("spray kab", S),
        ("موسم", S), ("بارش", S), ("برسات", S), ("آندھی", S), ("تیز ہوا", S), ("سپرے کا وقت", S), ("اسپرے کا وقت", S),
        ("سپرے کب", S), ("اسپرے کب", S),
        ("spray", W), ("spraying", W), ("spre", W), ("سپرے", W), ("اسپرے", W),
        ("today", W), ("tomorrow", W), ("kal", W), ("aaj", W), ("آج", W), ("کل", W),
        ("when", W), ("kab", W), ("کب", W), ("time", W), ("waqt", W), ("وقت", W),
        ("dry", W), ("hawa", W), ("ہوا", W), ("garmi", W), ("گرمی", W), ("temperature", W), ("hot", W),
    ],
    "market": [
        ("price", S), ("prices", S), ("rate", S), ("rates", S), ("mandi", S), ("sell", S), ("selling", S), ("hold", S),
        ("holding", S), ("sell now", S), ("wait or sell", S),
        ("bhao", S), ("bhaw", S), ("bhav", S), ("qeemat", S), ("keemat", S), ("qimat", S), ("bechna", S), ("bechun", S),
        ("bechoon", S), ("becho", S), ("bechni", S), ("bechne", S), ("bech do", S), ("bech dun", S), ("bech dein", S),
        ("منڈی", S), ("بھاؤ", S), ("بھاو", S), ("قیمت", S), ("قیمتیں", S), ("قیمتوں", S), ("نرخ", S), ("ریٹ", S),
        ("بیچ", S), ("بیچوں", S), ("بیچنا", S), ("بیچنے", S), ("بیچنی", S),
        ("market", W), ("bazaar", W), ("بازار", W),
    ],
    "field": [
        ("satellite", S), ("ndvi", S), ("from space", S), ("greenness", S), ("sentinel", S),
        ("my field", S), ("mera khet", S), ("mere khet", S), ("field health", S), ("crop health", S), ("khet ki halat", S),
        ("سیٹلائٹ", S), ("خلا", S), ("ہریالی", S), ("میرا کھیت", S), ("میرے کھیت", S), ("کھیت کی حالت", S),
        ("فصل کی حالت", S), ("فصل کی صحت", S),
        ("field", W), ("fields", W), ("khet", W), ("khait", W), ("کھیت", W), ("کھیتوں", W), ("patch", W), ("patchy", W),
        ("uneven", W), ("ناہموار", W), ("weak", W), ("kamzor", W), ("کمزور", W), ("hara", W), ("ہرا", W),
    ],
    "diagnosis": [
        ("disease", S), ("diseased", S), ("blight", S), ("rust", S), ("mildew", S), ("wilt", S), ("wilting", S),
        ("fungus", S), ("spots", S), ("lesion", S), ("leaf curl", S), ("photo", S), ("picture", S), ("image", S),
        ("diagnose", S), ("diagnosis", S), ("what is wrong", S), ("whats wrong", S),
        ("bimari", S), ("bemari", S), ("tasveer", S), ("tasvir", S), ("tashkhees", S), ("kya masla", S), ("daagh", S), ("dagh", S), ("daag", S), ("dhabbe", S), ("dhabay", S), ("dhabbay", S),
        ("بیماری", S), ("تصویر", S), ("داغ", S), ("دھبے", S), ("دھبہ", S), ("زنگ", S), ("جھلساو", S), ("تشخیص", S),
        ("کیا مسئلہ", S), ("پتے پر", S), ("پتوں پر", S),
        ("leaf", W), ("leaves", W), ("pattay", W), ("pattey", W), ("patta", W), ("patton", W),
        ("پتے", W), ("پتوں", W), ("پتا", W), ("پتہ", W), ("yellow", W), ("peela", W), ("peelay", W), ("پیلا", W), ("پیلے", W),
        ("sick", W), ("sukh", W), ("سوکھ", W), ("سوکھنا", W), ("kaala", W), ("کالا", W), ("کالے", W), ("spot", W),
        ("کیا ہوا", W), ("kya hua", W),
    ],
    # Anything about which chemical to use or how much. This route NEVER answers with a product or a dose.
    "treatment": [
        ("pesticide", S), ("pesticides", S), ("insecticide", S), ("fungicide", S), ("herbicide", S), ("chemical", S),
        ("chemicals", S), ("dose", S), ("dosage", S), ("medicine", S), ("medication", S), ("treatment", S), ("cure", S),
        ("remedy", S), ("what to spray", S), ("what should i spray", S), ("which spray", S), ("how much to spray", S),
        ("ml per", S), ("ml", S), ("gram per", S), ("per acre", S), ("per litre", S), ("per liter", S),
        ("dawai", S), ("dawa", S), ("dawaee", S), ("dawayi", S), ("dawaiyan", S), ("ilaj", S), ("kon si dawai", S), ("kitni dawai", S),
        ("دوا", S), ("دوائی", S), ("دوائیں", S), ("دوایی", S), ("ادویات", S), ("کیڑے مار", S), ("کیڑا مار", S), ("زہر", S),
        ("مقدار", S), ("ملی لیٹر", S), ("علاج", S), ("کون سی دوا", S), ("کتنی دوا", S), ("کیا سپرے", S),
        ("tebuconazole", S), ("propiconazole", S), ("chlorpyrifos", S), ("cypermethrin", S), ("imidacloprid", S),
        ("glyphosate", S), ("mancozeb", S), ("paraquat", S), ("carbendazim", S), ("lambda", S), ("endosulfan", S),
    ],
}

# Crops the market agent has prices for. Longer phrases are listed first so "wheat flour" wins over "wheat".
COMMODITIES: list[tuple[str, list[str]]] = [
    ("Wheat flour", ["wheat flour", "flour", "atta", "aata", "ata", "آٹا", "آٹے"]),
    ("Wheat", ["wheat", "gandum", "gehun", "gendum", "گندم"]),
    ("Rice (basmati, broken)", ["basmati", "باسمتی"]),
    ("Rice (coarse)", ["rice", "chawal", "chaawal", "irri", "چاول"]),
    ("Sugar", ["sugar", "cheeni", "chini", "چینی"]),
    ("Lentils (masur)", ["masur", "masoor", "مسور"]),
    ("Lentils (moong)", ["moong", "mung", "مونگ"]),
    ("Beans(mash)", ["mash", "ماش"]),
]
# "lentils" / "daal" alone does not say which one: ask.
AMBIGUOUS_COMMODITY = ["daal", "dal", "lentil", "lentils", "دال", "دالیں"]

COMMODITY_URDU = {
    "Wheat": "گندم", "Wheat flour": "آٹا", "Rice (coarse)": "چاول (موٹا)", "Rice (basmati, broken)": "باسمتی چاول (ٹوٹا)",
    "Sugar": "چینی", "Lentils (masur)": "مسور کی دال", "Lentils (moong)": "مونگ کی دال", "Beans(mash)": "ماش",
}

NORMALISED: dict[str, list[tuple[str, int]]] = {k: [(normalize(p), w) for p, w in v] for k, v in LEXICON.items()}
