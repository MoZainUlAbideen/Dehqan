"""Text handling for farmer questions in English, Roman Urdu and Urdu script."""

import re
import unicodedata

# Arabic-script letters that Urdu keyboards and phones produce in several forms. Map them to one form so that
# "گندم" typed on any keyboard matches, and strip vowel marks, which people rarely type.
_CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ې": "ی", "ك": "ک", "ة": "ہ", "ۃ": "ہ", "ھ": "ہ",
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ی", "ۓ": "ے",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
_MARKS = re.compile("[ً-ٰٟـ‌‍‎‏]")  # vowel marks, tatweel, zero-width
_ARABIC_SCRIPT = re.compile("[؀-ۿݐ-ݿ]")
_SPLIT = re.compile(r"[^\w]+", re.UNICODE)


def normalize(text: str) -> str:
    """Lowercase, unify Urdu letter variants, drop vowel marks and punctuation. Returns space-separated tokens."""
    t = unicodedata.normalize("NFKC", text).lower().translate(_CHAR_MAP)
    t = _MARKS.sub("", t)
    return " ".join(w for w in _SPLIT.split(t) if w)


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def is_urdu(text: str) -> bool:
    """True if the question is written (at least partly) in Urdu script."""
    return bool(_ARABIC_SCRIPT.search(text))


def contains_phrase(norm_text: str, phrase: str) -> bool:
    """Whole-word match of a (possibly multi-word) normalised phrase inside a normalised text."""
    return f" {normalize(phrase)} " in f" {norm_text} "
