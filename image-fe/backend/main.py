import asyncio
import json
import os
import random
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import chat_db
import db
from chat_models import (
    CHAT_DEFAULTS,
    SUMMARY_DEFAULTS,
    ChatSendRequest,
    Character,
    ImpersonateRequest,
    NewConversationRequest,
    Preset,
    SaveSummaryRequest,
    SummarizeRequest,
    UpdateMessageRequest,
    ollama_options,
)
from comfy import ComfyClient
from llm import LLMClient
from models import DEFAULTS, GenerateRequest
from prompt_build import (
    build_impersonation_messages,
    build_messages,
    build_summary_messages,
    estimate_tokens,
)
from workflow import build_workflow, extract_images

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
IMAGES_DIR = DATA_DIR / "images"
AVATARS_DIR = DATA_DIR / "avatars"
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://host.docker.internal:8188")
LLM_URL = os.environ.get("LLM_URL", "http://host.docker.internal:11434")
BACKEND_CLIENT_ID = "image-fe-backend"

FALLBACK_SAMPLERS = [
    "euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
    "lms", "dpmpp_2s_ancestral", "dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde",
    "ddim", "uni_pc",
]
FALLBACK_SCHEDULERS = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]

IMAGE_NAME_RE = re.compile(r"^[a-f0-9]{32}\.png$")
AVATAR_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(png|jpg|jpeg|webp)$")
AVATAR_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

comfy_client = ComfyClient(COMFYUI_URL, BACKEND_CLIENT_ID)
llm_client = LLMClient(LLM_URL)

# prompt_id -> the request params (+ resolved seed) that produced it, so we can
# persist them to history once the image comes back.
pending: dict[str, dict] = {}

# chat stream_id -> {conversation_id, character, messages} needed to run + persist
# a chat turn once the SSE client subscribes.
chat_pending: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db(DATA_DIR / "history.db")
    chat_db.init_db(DATA_DIR / "chat.db")
    await comfy_client.start()
    yield
    await comfy_client.stop()
    await llm_client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/api/defaults")
def get_defaults():
    return DEFAULTS


@app.get("/api/options")
async def get_options():
    try:
        ckpt_info = await comfy_client.get_object_info("CheckpointLoaderSimple")
        ksampler_info = await comfy_client.get_object_info("KSampler")
        checkpoints = ckpt_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        samplers = ksampler_info["KSampler"]["input"]["required"]["sampler_name"][0]
        schedulers = ksampler_info["KSampler"]["input"]["required"]["scheduler"][0]
    except Exception:
        checkpoints = [DEFAULTS["model"]]
        samplers = FALLBACK_SAMPLERS
        schedulers = FALLBACK_SCHEDULERS
    try:
        lora_info = await comfy_client.get_object_info("LoraLoader")
        loras = lora_info["LoraLoader"]["input"]["required"]["lora_name"][0]
    except Exception:
        loras = []
    return {
        "checkpoints": checkpoints,
        "samplers": samplers,
        "schedulers": schedulers,
        "loras": loras,
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    seed = req.seed
    if req.randomize_seed or seed <= 0:
        seed = random.randint(0, 2**31 - 1)

    workflow = build_workflow(req, seed)
    try:
        prompt_id = await comfy_client.submit_prompt(workflow)
    except Exception as e:
        raise HTTPException(502, f"Could not reach ComfyUI: {e}")

    pending[prompt_id] = {**req.model_dump(), "seed": seed}
    return {"prompt_id": prompt_id, "seed": seed}


async def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/stream/{prompt_id}")
async def stream(prompt_id: str):
    if prompt_id not in pending:
        raise HTTPException(404, "unknown prompt_id")

    async def gen():
        queue = comfy_client.register(prompt_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield await _sse({"type": "error", "message": "Generation timed out"})
                    return

                if msg["kind"] == "progress":
                    yield await _sse({"type": "progress", "value": msg["value"], "max": msg["max"]})
                elif msg["kind"] == "error":
                    yield await _sse({"type": "error", "message": msg["message"]})
                    return
                elif msg["kind"] == "executing" and msg["node"] is None:
                    break  # ComfyUI signals prompt completion this way

            history = await comfy_client.get_history(prompt_id)
            images_meta = extract_images(history, prompt_id)

            saved = []
            for img in images_meta:
                data = await comfy_client.fetch_image(
                    img["filename"], img.get("subfolder", ""), img.get("type", "output")
                )
                fname = f"{uuid.uuid4().hex}.png"
                (IMAGES_DIR / fname).write_bytes(data)
                saved.append(fname)

            params = pending.pop(prompt_id, {})
            gen_id = db.insert_generation(params, saved)
            yield await _sse(
                {
                    "type": "done",
                    "generation_id": gen_id,
                    "images": [f"/api/images/{f}" for f in saved],
                }
            )
        finally:
            comfy_client.unregister(prompt_id)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/history")
def get_history_list(limit: int = 60, before_id: int | None = None):
    return db.list_generations(limit, before_id)


@app.get("/api/images/{filename}")
def get_image(filename: str):
    if not IMAGE_NAME_RE.match(filename):
        raise HTTPException(404)
    path = IMAGES_DIR / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/png")


@app.delete("/api/history/{gen_id}")
def delete_history_item(gen_id: int):
    images = db.delete_generation(gen_id)
    if images is None:
        raise HTTPException(404, "generation not found")
    for fname in images:
        if IMAGE_NAME_RE.match(fname):
            (IMAGES_DIR / fname).unlink(missing_ok=True)
    return {"ok": True}


# ------------------------------------------------------------- roleplay chat

@app.get("/api/chat/defaults")
def get_chat_defaults():
    return CHAT_DEFAULTS


@app.get("/api/chat/models")
async def get_chat_models():
    try:
        models = await llm_client.list_models()
        if not models:
            raise RuntimeError("no models reported")
    except Exception:
        models = [CHAT_DEFAULTS["model"]]
    return {"models": models}


@app.get("/api/characters")
def list_characters():
    return chat_db.list_characters()


@app.post("/api/characters")
def create_character(char: Character):
    char_id = chat_db.insert_character(char.model_dump())
    return chat_db.get_character(char_id)


@app.get("/api/characters/{char_id}")
def get_character(char_id: int):
    char = chat_db.get_character(char_id)
    if not char:
        raise HTTPException(404, "character not found")
    return char


@app.put("/api/characters/{char_id}")
def update_character(char_id: int, char: Character):
    if not chat_db.update_character(char_id, char.model_dump()):
        raise HTTPException(404, "character not found")
    return chat_db.get_character(char_id)


@app.delete("/api/characters/{char_id}")
def delete_character(char_id: int):
    char = chat_db.get_character(char_id)
    if not chat_db.delete_character(char_id):
        raise HTTPException(404, "character not found")
    if char:
        avatar_fname = (char.get("avatar") or "").rsplit("/", 1)[-1]
        if AVATAR_NAME_RE.match(avatar_fname):
            (AVATARS_DIR / avatar_fname).unlink(missing_ok=True)
    return {"ok": True}


@app.post("/api/characters/{char_id}/avatar")
async def upload_character_avatar(char_id: int, file: UploadFile = File(...)):
    char = chat_db.get_character(char_id)
    if not char:
        raise HTTPException(404, "character not found")
    ext = AVATAR_CONTENT_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, "unsupported image type (use png, jpeg, or webp)")

    data = await file.read()
    fname = f"{uuid.uuid4().hex}.{ext}"
    (AVATARS_DIR / fname).write_bytes(data)

    old_fname = (char.get("avatar") or "").rsplit("/", 1)[-1]

    char["avatar"] = f"/api/avatars/{fname}"
    chat_db.update_character(char_id, char)

    if AVATAR_NAME_RE.match(old_fname):
        (AVATARS_DIR / old_fname).unlink(missing_ok=True)

    return chat_db.get_character(char_id)


@app.get("/api/avatars/{filename}")
def get_avatar(filename: str):
    if not AVATAR_NAME_RE.match(filename):
        raise HTTPException(404)
    path = AVATARS_DIR / filename
    if not path.is_file():
        raise HTTPException(404)
    ext = filename.rsplit(".", 1)[-1]
    media_type = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    return FileResponse(path, media_type=media_type)


def _character_from_card(card: dict) -> Character:
    """Accepts a SillyTavern/Chub v2 character card ({"spec": "chara_card_v2",
    "data": {...}}) or a flat v1-style card ({"name": ..., ...})."""
    data = card.get("data", card) if isinstance(card, dict) else {}
    return Character(
        name=data.get("name") or "Imported Character",
        description=data.get("description", ""),
        personality=data.get("personality", ""),
        scenario=data.get("scenario", ""),
        first_mes=data.get("first_mes", ""),
        mes_example=data.get("mes_example", ""),
        avatar=data.get("avatar", "") if isinstance(data.get("avatar"), str) else "",
    )


@app.post("/api/characters/import")
def import_character(card: dict):
    char = _character_from_card(card)
    char_id = chat_db.insert_character(char.model_dump())
    return chat_db.get_character(char_id)


@app.get("/api/presets")
def list_presets():
    return chat_db.list_presets()


@app.post("/api/presets")
def create_preset(preset: Preset):
    preset_id = chat_db.insert_preset(preset.model_dump())
    return chat_db.get_preset(preset_id)


@app.get("/api/presets/{preset_id}")
def get_preset(preset_id: int):
    preset = chat_db.get_preset(preset_id)
    if not preset:
        raise HTTPException(404, "preset not found")
    return preset


@app.put("/api/presets/{preset_id}")
def update_preset(preset_id: int, preset: Preset):
    if not chat_db.update_preset(preset_id, preset.model_dump()):
        raise HTTPException(404, "preset not found")
    return chat_db.get_preset(preset_id)


@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: int):
    if not chat_db.delete_preset(preset_id):
        raise HTTPException(404, "preset not found")
    return {"ok": True}


@app.get("/api/conversations")
def list_conversations(character_id: int | None = None):
    return chat_db.list_conversations(character_id)


@app.post("/api/conversations")
def create_conversation(req: NewConversationRequest):
    character = chat_db.get_character(req.character_id)
    if not character:
        raise HTTPException(404, "character not found")
    title = req.title or character["name"]
    conv_id = chat_db.insert_conversation(req.character_id, title, preset_id=req.preset_id)
    if character.get("first_mes"):
        chat_db.insert_message(conv_id, "assistant", character["first_mes"])
    return {
        "conversation": chat_db.get_conversation(conv_id),
        "messages": chat_db.list_messages(conv_id),
    }


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int):
    conv = chat_db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    return {"conversation": conv, "messages": chat_db.list_messages(conv_id)}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    if not chat_db.delete_conversation(conv_id):
        raise HTTPException(404, "conversation not found")
    return {"ok": True}


@app.put("/api/messages/{message_id}")
def edit_message(message_id: int, req: UpdateMessageRequest):
    if not chat_db.update_message_content(message_id, req.content):
        raise HTTPException(404, "message not found")
    return chat_db.get_message(message_id)


@app.delete("/api/messages/{message_id}")
def delete_message(message_id: int):
    if not chat_db.delete_message(message_id):
        raise HTTPException(404, "message not found")
    return {"ok": True}


def _resolve_preset(preset_id: int | None) -> dict | None:
    return chat_db.get_preset(preset_id) if preset_id else None


def _save_conversation_settings(req):
    chat_db.update_conversation_settings(
        req.conversation_id,
        req.preset_id,
        temperature=req.temperature,
        top_p=req.top_p,
        min_p=req.min_p,
        top_k=req.top_k,
        repeat_penalty=req.repeat_penalty,
        repeat_last_n=req.repeat_last_n,
        presence_penalty=req.presence_penalty,
        frequency_penalty=req.frequency_penalty,
        max_tokens=req.max_tokens,
        model=req.model,
        persona=req.persona,
        scene_state=req.scene_state,
        num_ctx=req.num_ctx,
    )


# Safety margin inside num_ctx for chat-template overhead and token-estimate error.
_PROMPT_MARGIN = 256


def _prompt_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(m["content"]) for m in messages)


def _fit_to_context(build, history: list[dict], num_ctx: int, max_tokens: int) -> list[dict]:
    """Message-level context windowing: rebuild the prompt dropping the OLDEST history
    messages until it fits num_ctx (minus the reply budget). Ollama's own overflow
    handling truncates raw tokens from the top of the rendered prompt, which can
    destroy the system prompt / character card entirely -- trimming whole old messages
    ourselves keeps the card and the recent scene intact. The latest message is never
    dropped."""
    budget = num_ctx - max_tokens - _PROMPT_MARGIN
    messages = build(history)
    while len(history) > 1 and _prompt_tokens(messages) > budget:
        history = history[1:]
        messages = build(history)
    return messages


@app.post("/api/chat/send")
def send_chat_message(req: ChatSendRequest):
    conv = chat_db.get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    character = chat_db.get_character(conv["character_id"])
    if not character:
        raise HTTPException(404, "character not found")

    _save_conversation_settings(req)

    preset = _resolve_preset(req.preset_id)
    chat_db.insert_message(req.conversation_id, "user", req.message)
    history = chat_db.list_messages(req.conversation_id, after_id=conv.get("summary_upto_message_id"))
    messages = _fit_to_context(
        lambda h: build_messages(
            character,
            h,
            persona=req.persona,
            preset=preset,
            summary=conv.get("summary"),
            scene_state=req.scene_state,
        ),
        history,
        req.num_ctx,
        req.max_tokens,
    )

    stream_id = uuid.uuid4().hex
    chat_pending[stream_id] = {
        "conversation_id": req.conversation_id,
        "messages": messages,
        "model": req.model,
        "options": ollama_options(req.model_dump()),
        "persist": True,
    }
    return {"stream_id": stream_id}


@app.post("/api/chat/impersonate")
def impersonate(req: ImpersonateRequest):
    conv = chat_db.get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    character = chat_db.get_character(conv["character_id"])
    if not character:
        raise HTTPException(404, "character not found")

    _save_conversation_settings(req)

    preset = _resolve_preset(req.preset_id)
    history = chat_db.list_messages(req.conversation_id, after_id=conv.get("summary_upto_message_id"))
    messages = _fit_to_context(
        lambda h: build_impersonation_messages(
            character,
            h,
            persona=req.persona,
            preset=preset,
            summary=conv.get("summary"),
            scene_state=req.scene_state,
        ),
        history,
        req.num_ctx,
        req.max_tokens,
    )

    stream_id = uuid.uuid4().hex
    chat_pending[stream_id] = {
        "conversation_id": req.conversation_id,
        "messages": messages,
        "model": req.model,
        "options": ollama_options(req.model_dump()),
        "persist": False,
    }
    return {"stream_id": stream_id}


@app.post("/api/chat/summarize")
def summarize_conversation(req: SummarizeRequest):
    conv = chat_db.get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    character = chat_db.get_character(conv["character_id"])
    if not character:
        raise HTTPException(404, "character not found")

    history = chat_db.list_messages(req.conversation_id, after_id=conv.get("summary_upto_message_id"))
    if not history:
        raise HTTPException(400, "nothing new to summarize")

    # Fit the transcript into the summary context budget by taking only the OLDEST
    # chunk that fits (unlike chat, which keeps the newest): a partial summary must
    # cover the oldest turns so summary_upto_message_id can walk forward through the
    # backlog on repeated passes without leaving a gap.
    budget = (
        SUMMARY_DEFAULTS["num_ctx"]
        - SUMMARY_DEFAULTS["max_tokens"]
        - _PROMPT_MARGIN
        - estimate_tokens(conv.get("summary") or "")
    )
    chunk, used = [], 0
    for m in history:
        used += estimate_tokens(m["content"])
        if chunk and used > budget:
            break
        chunk.append(m)
    partial = len(chunk) < len(history)
    upto_message_id = chunk[-1]["id"]
    messages = build_summary_messages(character, chunk, existing_summary=conv.get("summary"))

    stream_id = uuid.uuid4().hex
    chat_pending[stream_id] = {
        "conversation_id": req.conversation_id,
        "messages": messages,
        "model": req.model,
        "options": ollama_options(SUMMARY_DEFAULTS),
        "persist": False,
    }
    return {"stream_id": stream_id, "upto_message_id": upto_message_id, "partial": partial}


@app.post("/api/conversations/{conv_id}/summary")
def save_conversation_summary(conv_id: int, req: SaveSummaryRequest):
    conv = chat_db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    chat_db.update_conversation_summary(conv_id, req.summary, req.upto_message_id)
    return chat_db.get_conversation(conv_id)


@app.get("/api/chat/stream/{stream_id}")
async def chat_stream(stream_id: str):
    entry = chat_pending.get(stream_id)
    if entry is None:
        raise HTTPException(404, "unknown stream_id")

    async def gen():
        full_reply = ""
        done_chunk = {}
        try:
            async for chunk in llm_client.stream_chat(
                entry["model"], entry["messages"], entry["options"]
            ):
                if "content" in chunk:
                    full_reply += chunk["content"]
                    yield await _sse({"type": "token", "content": chunk["content"]})
                elif chunk.get("error"):
                    yield await _sse({"type": "error", "message": chunk["error"]})
                    return
                elif chunk.get("done"):
                    done_chunk = chunk
                    break

            msg_id = None
            if entry.get("persist", True) and full_reply.strip():
                msg_id = chat_db.insert_message(
                    entry["conversation_id"], "assistant", full_reply
                )
            yield await _sse(
                {
                    "type": "done",
                    "message_id": msg_id,
                    "prompt_eval_count": done_chunk.get("prompt_eval_count"),
                    "eval_count": done_chunk.get("eval_count"),
                    "num_ctx": entry["options"].get("num_ctx"),
                }
            )
        finally:
            chat_pending.pop(stream_id, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve the built React app. Must be mounted last so it doesn't shadow /api/*.
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    # Client-side routes (e.g. /chat) aren't real files, so a direct navigation or
    # page refresh would 404 against the static mount above. Fall back to index.html
    # for any non-API path so React Router can take over.
    @app.exception_handler(404)
    async def spa_fallback(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "Not Found"}, status_code=404)
