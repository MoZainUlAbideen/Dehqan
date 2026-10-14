"""The diagnosis pipeline: crop gate -> classifier -> abstention -> severity.

The components are passed in as plain functions, so this logic is tested with fakes and never needs
torch. Real implementations live in app/models.py.

Every result carries `limitations`: honest caveats the farmer-facing UI must show.
"""

from dataclasses import dataclass, field
from typing import Callable, Protocol

GATE_THRESHOLD = 0.5

# Measured on held-out PlantDoc field photos (evals/field_tuned.json). Picking the threshold on the same
# data makes these numbers optimistic.
ABSTAIN_THRESHOLD = 0.9
ABSTAIN_THRESHOLD_NOTE = "At this threshold the model answered 24% of held-out field photos and was right on 79% of those."

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


BASE_LIMITATIONS = [
    "Preliminary AI guess, not a confirmed diagnosis.",
    "The classifier knows 27 disease/healthy classes across 14 crops. Wheat and cotton are NOT covered.",
    "Treatment advice is not available yet: official pesticide lists and advisories are not loaded.",
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
) -> DiagnosisResult:
    score = gate(image)
    if score < gate_threshold:
        return DiagnosisResult(
            status="not_a_crop", crop_score=score,
            message="This does not look like a plant leaf. Please send a clear, close photo of one leaf.",
        )

    pred = classifier(image)
    if pred.confidence < abstain_threshold:
        return DiagnosisResult(
            status="uncertain", crop_score=score, confidence=pred.confidence,
            message=f"I am not sure what this is. {EXTENSION_ADVICE}",
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
