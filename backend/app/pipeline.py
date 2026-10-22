"""The diagnosis pipeline: crop gate -> classifier -> abstention -> severity.

The components are passed in as plain functions, so this logic is tested with fakes and never needs
torch. Real implementations live in app/models.py.

Every result carries `limitations`: honest caveats the farmer-facing UI must show.
"""

from dataclasses import dataclass, field
from typing import Callable, Protocol

from vision.crop_id import COVERED_CROPS, MIN_PROB

GATE_THRESHOLD = 0.5

# Measured on held-out PlantDoc field photos (evals/field_tuned.json). Picking the threshold on the same
# data makes these numbers optimistic.
ABSTAIN_THRESHOLD = 0.9
ABSTAIN_THRESHOLD_NOTE = "At this threshold the model answered 56% of held-out field photos and was right on 81% of those."

KNOWN_CROPS = "apple, blueberry, cherry, maize, grape, peach, bell pepper, potato, raspberry, soybean, squash, strawberry and tomato"
EXTENSION_ADVICE = "Please show the plant to your local agriculture extension office."


class Image(Protocol):  # a PIL image in practice; anything the components accept
    ...


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float


@dataclass
class DiagnosisResult:
    status: str                         # "not_a_crop" | "uncertain" | "diagnosis"
    message: str
    crop_score: float | None = None
    label: str | None = None
    confidence: float | None = None
    is_healthy: bool | None = None
    severity: float | None = None       # 0..1, share of leaf covered by spots
    severity_grade: str | None = None
    limitations: list[str] = field(default_factory=list)
    detected_crop: str | None = None    # set only when the classifier abstained and a crop we do not cover was recognised


BASE_LIMITATIONS = [
    "Preliminary AI guess, not a confirmed diagnosis.",
    "The classifier knows 27 disease/healthy classes across 13 crops. Wheat and cotton are NOT covered.",
    "Treatment advice exists only for cotton pests (copied from the Punjab Agriculture Department bulletin) and is not checked against the national registered-pesticide list.",
]
SEVERITY_LIMITATION = "Severity was trained on apple, soybean and wheat photos only; treat it as rough."


def is_healthy_label(label: str) -> bool:
    return label.lower().endswith("healthy")


def diagnose(
    image: Image,
    gate: Callable[[Image], float],
    classifier: Callable[[Image], Prediction],
    severity: Callable[[Image], float | None],
    grade: Callable[[float], str],
    gate_threshold: float = GATE_THRESHOLD,
    abstain_threshold: float = ABSTAIN_THRESHOLD,
    crop_hint: Callable[[Image], tuple[str, float]] | None = None,
) -> DiagnosisResult:
    score = gate(image)
    if score < gate_threshold:
        return DiagnosisResult(
            status="not_a_crop", crop_score=score,
            message="This does not look like a plant leaf. Please send a clear, close photo of one leaf.",
        )

    pred = classifier(image)
    if pred.confidence < abstain_threshold:
        hint = crop_hint(image) if crop_hint else None
        if hint and hint[1] >= MIN_PROB and hint[0] not in COVERED_CROPS and hint[0] != "other":
            return DiagnosisResult(
                status="uncertain", crop_score=score, confidence=pred.confidence, detected_crop=hint[0],
                message=f"This might be {hint[0]}. I cannot diagnose that crop yet, so I will not guess. {EXTENSION_ADVICE}",
                limitations=list(BASE_LIMITATIONS),
            )
        return DiagnosisResult(
            status="uncertain", crop_score=score, confidence=pred.confidence,
            message=f"I am not sure what this is. I only know {KNOWN_CROPS}, and a leaf from another plant, a dried or autumn leaf, or a blurry photo will get this answer. {EXTENSION_ADVICE}",
            limitations=list(BASE_LIMITATIONS),
        )

    healthy = is_healthy_label(pred.label)
    sev = None if healthy else severity(image)
    limitations = list(BASE_LIMITATIONS) + ([SEVERITY_LIMITATION] if sev is not None else [])
    return DiagnosisResult(
        status="diagnosis", crop_score=score, label=pred.label, confidence=pred.confidence,
        is_healthy=healthy, severity=sev, severity_grade=None if sev is None else grade(sev),
        message=("The leaf looks healthy." if healthy else f"Possible diagnosis: {pred.label}.")
        + " This is preliminary. " + EXTENSION_ADVICE,
        limitations=limitations,
    )
