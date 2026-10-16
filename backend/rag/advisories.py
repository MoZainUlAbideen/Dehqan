"""Pesticide advice taken from an official advisory, with the exact line quoted as the citation.

Source: Punjab Agriculture Department, Directorate General of Pest Warning and Quality Control of Pesticides.
Its weekly cotton bulletin has "Chemical Control of <pest>" tables: product name + dose per acre.

What this is NOT: a check against the national registered-pesticide list (Department of Plant Protection). That list
could not be downloaded, so we cannot say "registered". We can only say "listed in the official Punjab advisory".
The guardrail is fed that way, and every answer says so.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rag.guardrail import Citation, Recommendation, Status, check

SOURCES_DIR = Path(__file__).parent / "sources"

HEADER = re.compile(r"^\s*Chemical Control of\s+(.+?)\s*$", re.I)
# "1 Spintoram 120 SC 60 mL"  /  "6 Deltamethrin + Triazophos 36 EC 500-600 ml"  /  "3 Sulfuxaflor 50% WG/240 SC 40-50 g/80-100 ml"
ROW = re.compile(r"^\s*(\d{1,2})\s+(?P<product>[A-Za-z].*?)\s+(?P<dose>\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*(?:ml|g|kg|l)\b(?:/\d+(?:-\d+)?\s*(?:ml|g)\b)?)\s*$", re.I)

PEST_ALIASES = {
    "whitefly": ["whitefly", "white fly", "safed makhi", "سفید مکھی"],
    "jassid": ["jassid", "tela", "green leaf hopper", "تیلا"],
    "thrips": ["thrips", "تھرپس"],
    "pink bollworm": ["pink bollworm", "pbw", "gulabi sundi", "گلابی سنڈی"],
    "mealy bug": ["mealy bug", "mealybug", "میلی بگ"],
}


@dataclass(frozen=True)
class Entry:
    crop: str
    pest: str
    product: str
    dose: str          # per acre, exactly as printed
    source_id: str
    line: str          # the full printed line: used as the citation quote


def normalize_pest(name: str) -> str:
    n = re.sub(r"\s+", " ", name.casefold()).strip()
    for canon, aliases in PEST_ALIASES.items():
        if any(a.casefold() in n for a in aliases):
            return canon
    return n


def parse(source_id: str, crop: str, text: str) -> list[Entry]:
    """Read the 'Chemical Control of X' tables. Anything that does not parse cleanly is skipped, never guessed."""
    entries, pest = [], None
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        h = HEADER.match(line)
        if h:
            pest = normalize_pest(h.group(1))
            continue
        if pest is None:
            continue
        m = ROW.match(line)
        if m:
            entries.append(Entry(crop, pest, m.group("product").strip(), m.group("dose").strip(), source_id, line))
        elif line and re.match(r"^[A-Z][a-z]+( [A-Za-z]+){0,3}$", line) and not line.startswith(("Sr", "No", "Name")):
            pest = None   # a new heading such as "Pink Bollworm" or "Cotton Leaf Curl Virus" ends the table
    return entries


def load() -> tuple[list[Entry], dict[str, str], dict[str, dict]]:
    meta = json.loads((SOURCES_DIR / "sources.json").read_text(encoding="utf-8"))
    entries, texts = [], {}
    for sid, m in meta.items():
        text = (SOURCES_DIR / m["file"]).read_text(encoding="utf-8")
        texts[sid] = text
        entries += parse(sid, m["crop"], text)
    return entries, texts, meta


def advise(crop: str, pest: str, entries: list[Entry], texts: dict[str, str], meta: dict[str, dict]) -> dict:
    """Every returned option has passed the guardrail: its dose is a verbatim quote from the cited bulletin."""
    pest_n = normalize_pest(pest)
    matches = [e for e in entries if e.crop == crop.casefold() and e.pest == pest_n]
    allowed = {e.product for e in entries}   # 'listed in the official advisory' is the only list we have
    options = []
    for e in matches:
        rec = Recommendation(e.product, e.dose, (), (Citation(e.source_id, e.line),))
        verdict = check(rec, allowed, set(), texts)
        if verdict.status is Status.APPROVED:
            m = meta[e.source_id]
            options.append({"product": e.product, "dose_per_acre": e.dose, "quote": e.line,
                            "source": m["title"], "publisher": m["publisher"], "url": m["url"]})
    return {
        "crop": crop, "pest": pest_n, "options": options,
        "ppe": None,
        "notes": ["Doses are copied from the official Punjab bulletin, per acre. This bulletin does not give protective-gear (PPE) rules, "
                  "so none are shown: read the product label.",
                  "These products are listed in the Punjab advisory. They were NOT checked against the national registered-pesticide list "
                  "(not available to us). Ask your agriculture extension office before buying.",
                  "Rotate between different groups of insecticide; do not repeat the same one (bulletin advice)."],
        "available": bool(options),
    }
