"""Safety guardrail for treatment recommendations.

Two non-negotiable rules from the project spec:
1. Never recommend a pesticide that is banned or not on the registered list.
2. Dose and protective gear (PPE) must come from a retrieved, cited source, never from LLM memory.

How rule 2 is enforced: every dose / PPE claim must carry a citation (source id + exact quote). We check that
the quote really appears in that source's text, and that the dose / PPE wording appears inside the quote.
If a claim cannot be traced to its source it is rejected, however plausible it sounds.

The registered and banned lists are INPUTS (loaded from official documents later); this module only decides.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    APPROVED = "approved"        # registered, not banned, every dose/PPE claim verified in a source
    NO_DOSE = "no_dose"          # registered and not banned, but no dose given: say "ask the extension office"
    REJECTED = "rejected"        # must not be shown to the farmer


@dataclass(frozen=True)
class Citation:
    source_id: str
    quote: str


@dataclass(frozen=True)
class Recommendation:
    active_ingredient: str
    dose: str | None = None
    ppe: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()


@dataclass
class Verdict:
    status: Status
    reasons: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace so harmless formatting differences do not break matching."""
    return re.sub(r"\s+", " ", text.casefold()).strip()


def contains_phrase(haystack: str, needle: str) -> bool:
    """Whole-token match after normalising. Plain `in` is unsafe for doses: "20 ml" is inside "120 ml" and
    "5 ml" is inside "0.5 ml", which are very different doses. So a match may not start in the middle of a
    number/word (or right after a decimal point) and may not stop in the middle of one (or before ".5")."""
    h, n = normalize(haystack), normalize(needle)
    if not n:
        return False
    start = r"(?<![\w.])" if re.match(r"\w", n[0]) else ""
    end = r"(?!\w|\.\d)" if re.match(r"\w", n[-1]) else ""
    return re.search(start + re.escape(n) + end, h) is not None


def _quote_in_source(citation: Citation, sources: dict[str, str]) -> bool:
    source = sources.get(citation.source_id)
    return source is not None and contains_phrase(source, citation.quote)


def _claim_cited(claim: str, rec: Recommendation, sources: dict[str, str]) -> bool:
    """True if some citation's quote is genuinely in its source AND contains the claim's wording."""
    return any(_quote_in_source(c, sources) and contains_phrase(c.quote, claim) for c in rec.citations)


def check(
    rec: Recommendation,
    registered: set[str],
    banned: set[str],
    sources: dict[str, str],
) -> Verdict:
    """Decide whether a recommendation may be shown. Banned beats everything; unverifiable claims reject."""
    active = normalize(rec.active_ingredient)
    banned_n = {normalize(b) for b in banned}
    registered_n = {normalize(r) for r in registered}

    if active in banned_n:
        return Verdict(Status.REJECTED, [f"'{rec.active_ingredient}' is banned"])
    if active not in registered_n:
        return Verdict(Status.REJECTED, [f"'{rec.active_ingredient}' is not on the registered list"])

    reasons: list[str] = []
    if rec.dose is not None and not _claim_cited(rec.dose, rec, sources):
        reasons.append(f"dose '{rec.dose}' is not backed by a verbatim quote from a cited source")
    for item in rec.ppe:
        if not _claim_cited(item, rec, sources):
            reasons.append(f"PPE '{item}' is not backed by a verbatim quote from a cited source")
    if reasons:
        return Verdict(Status.REJECTED, reasons)

    if rec.dose is None:
        return Verdict(Status.NO_DOSE, ["no dose supplied: refer the farmer to the extension office"])
    return Verdict(Status.APPROVED)
