"""Choose which model backend the server uses. Imports are lazy so the ONNX path never imports PyTorch.

DEHQAN_BACKEND=onnx   ONNX Runtime (default when the ONNX files exist; what the deployed server uses)
DEHQAN_BACKEND=torch  PyTorch (development)
"""

import os

from app.components import Components


def load_components() -> Components:
    from app import onnx_models

    choice = os.environ.get("DEHQAN_BACKEND", "auto")
    if choice == "onnx" or (choice == "auto" and not onnx_models.missing_files()):
        return onnx_models.load_components()
    if choice not in ("auto", "torch"):
        raise ValueError(f"DEHQAN_BACKEND must be onnx, torch or auto, not {choice!r}")
    from app import models_torch

    return models_torch.load_components()
