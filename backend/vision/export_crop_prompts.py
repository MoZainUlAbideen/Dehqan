"""Compute the CLIP text embeddings of vision/crop_id.CROP_PROMPTS once and save them (vision/crop_prompts.npz).

Run (from backend/, needs the train group and the local CLIP copy):  uv run --group train python -m vision.export_crop_prompts
"""

import numpy as np
import torch
from transformers import CLIPModel, CLIPTokenizer

from vision.crop_gate import MODEL_ID
from vision.crop_id import CROP_PROMPTS, PROMPTS_FILE

clip = CLIPModel.from_pretrained(MODEL_ID).eval()
tok = CLIPTokenizer.from_pretrained(MODEL_ID)
with torch.no_grad():
    t = clip.text_projection(clip.text_model(**tok(list(CROP_PROMPTS.values()), padding=True, return_tensors="pt")).pooler_output)
    t = t / t.norm(dim=-1, keepdim=True)
    scale = float(clip.logit_scale.exp())
np.savez(PROMPTS_FILE, text=t.numpy().astype(np.float32), scale=np.float32(scale), labels=np.array(list(CROP_PROMPTS)))
print("wrote", PROMPTS_FILE, t.shape)
