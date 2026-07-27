"""Request models and default form values.

Defaults follow the WAI-Illustrious-SDXL model card (Euler a, ~28 steps,
SDXL portrait bucket 832x1216) so the web form is pre-filled with values
suited to the default checkpoint. CFG 4.0 was kept from the hires-fix era
(it produced output closest to the reference site in testing); the model
card suggests 5-7 if results look too washed out with the single pass.
"""

from pydantic import BaseModel

DEFAULT_MODEL = "waiIllustriousSDXL_v170.safetensors"

DEFAULTS = {
    "prompt": "",
    "negative_prompt": "",
    "width": 832,
    "height": 1216,
    "steps": 28,
    "cfg": 4.0,
    "sampler_name": "euler_ancestral",
    "scheduler": "normal",
    "denoise": 1.0,
    "batch_size": 1,
    "seed": 0,
    "randomize_seed": True,
    "model": DEFAULT_MODEL,
    "loras": [],
}


class LoraSelection(BaseModel):
    name: str
    strength: float = 1.0


class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = 832
    height: int = 1216
    steps: int = 28
    cfg: float = 4.0
    sampler_name: str = "euler_ancestral"
    scheduler: str = "normal"
    denoise: float = 1.0
    batch_size: int = 1
    seed: int = 0
    randomize_seed: bool = True
    model: str = DEFAULT_MODEL
    loras: list[LoraSelection] = []
