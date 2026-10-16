"""The three model callables the pipeline needs. No heavy imports here, so the server can load this without PyTorch."""

from dataclasses import dataclass
from typing import Callable

from PIL import Image

from app.pipeline import Prediction


@dataclass
class Components:
    gate: Callable[[Image.Image], float]
    classifier: Callable[[Image.Image], Prediction]
    severity: Callable[[Image.Image], float | None]
    crop_hint: Callable[[Image.Image], tuple[str, float]] | None = None   # names the crop; used only when the classifier abstains
