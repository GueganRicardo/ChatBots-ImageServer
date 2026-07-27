"""Build a ComfyUI API-format prompt from a GenerateRequest.

The template (workflow_template.json) is the API-format twin of
comfyui-rocm/user/default/workflows/First-images.json (single sampling
pass), with clip skip 2 added. Node ids:
  4 CheckpointLoaderSimple  -> ckpt_name
  10 CLIPSetLastLayer       -> clip skip 2 (stop_at_clip_layer -2), feeds 6/7
  6 CLIPTextEncode          -> positive prompt text
  7 CLIPTextEncode          -> negative prompt text
  5 EmptyLatentImage        -> width / height / batch_size
  3 KSampler                -> seed / steps / cfg / sampler_name / scheduler / denoise
  8 VAEDecode, 9 SaveImage  -> unchanged, output node
  20+ LoraLoader            -> added at build time, one per requested LoRA,
                               chained between the checkpoint and the
                               KSampler (model) / CLIPSetLastLayer (clip)
"""

import copy
import json
from pathlib import Path

from models import GenerateRequest

_TEMPLATE_PATH = Path(__file__).parent / "workflow_template.json"
_TEMPLATE = json.loads(_TEMPLATE_PATH.read_text())

# Always prefixed onto every generation's prompt/negative prompt, regardless of
# what the form contains.
POSITIVE_PREFIX = "masterpiece,best quality,newest,absurdres,highres"
NEGATIVE_PREFIX = (
    "(low quality, worst quality:1.5),(bad anatomy),lowres,bad composition,"
    "fewer digits,text,username,logo,inaccurate eyes,extra digits,"
    "extra arms,disfigured,missing arms,too many fingers,fused fingers,missing fingers"
)


def _with_prefix(prefix: str, text: str) -> str:
    text = text.strip()
    return f"{prefix},{text}" if text else prefix


def build_workflow(req: GenerateRequest, seed: int) -> dict:
    wf = copy.deepcopy(_TEMPLATE)
    wf["4"]["inputs"]["ckpt_name"] = req.model
    wf["6"]["inputs"]["text"] = _with_prefix(POSITIVE_PREFIX, req.prompt)
    wf["7"]["inputs"]["text"] = _with_prefix(NEGATIVE_PREFIX, req.negative_prompt)
    wf["5"]["inputs"]["width"] = req.width
    wf["5"]["inputs"]["height"] = req.height
    wf["5"]["inputs"]["batch_size"] = req.batch_size
    wf["3"]["inputs"]["seed"] = seed
    wf["3"]["inputs"]["steps"] = req.steps
    wf["3"]["inputs"]["cfg"] = req.cfg
    wf["3"]["inputs"]["sampler_name"] = req.sampler_name
    wf["3"]["inputs"]["scheduler"] = req.scheduler
    wf["3"]["inputs"]["denoise"] = req.denoise
    wf["9"]["inputs"]["filename_prefix"] = "FE"

    model_out, clip_out = ["4", 0], ["4", 1]
    for i, lora in enumerate(req.loras):
        node_id = str(20 + i)
        wf[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora.name,
                "strength_model": lora.strength,
                "strength_clip": lora.strength,
                "model": model_out,
                "clip": clip_out,
            },
        }
        model_out, clip_out = [node_id, 0], [node_id, 1]
    wf["3"]["inputs"]["model"] = model_out
    wf["10"]["inputs"]["clip"] = clip_out
    return wf


def extract_images(history_response: dict, prompt_id: str) -> list[dict]:
    """Pull the [{filename, subfolder, type}, ...] list out of /history/{id}."""
    entry = history_response.get(prompt_id)
    if not entry:
        return []
    outputs = entry.get("outputs", {})
    images: list[dict] = []
    for node_output in outputs.values():
        images.extend(node_output.get("images", []))
    return images
