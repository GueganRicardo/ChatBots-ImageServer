"""Request/response models and default values for the roleplay chat feature."""

import os

from pydantic import BaseModel

DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "nemomix-unleashed-12b")

DEFAULT_NUM_CTX = 8192

CHAT_DEFAULTS = {
    "model": DEFAULT_LLM_MODEL,
    # Default persona: substituted for {{user}} in character cards and shown to the
    # model as the user's description; the per-conversation persona box overrides it.
    "persona": os.environ.get("CHAT_PERSONA", "Ricardo"),
    # Preset auto-applied on page load (must match a seeded preset name in chat_db).
    "default_preset": "Immersive Prose — Evolving",
    # Sampler defaults follow the NemoMix-Unleashed author's recommendation: temp ~1.0
    # with min_p doing the tail-cutting, top_p/top_k neutralized (1.0 / 0 = disabled),
    # and only a light repeat penalty -- but applied over a window (repeat_last_n) large
    # enough to cover whole replies, plus a presence penalty to discourage the model
    # from re-treading earlier phrasing.
    "temperature": 1.0,
    "top_p": 1.0,
    "min_p": 0.05,
    "top_k": 0,
    "repeat_penalty": 1.05,
    "repeat_last_n": 2048,
    "presence_penalty": 0.5,
    "frequency_penalty": 0.0,
    "max_tokens": 512,
    "num_ctx": DEFAULT_NUM_CTX,
}

# Dedicated sampler settings for the Summarize feature: factual recap, not creative
# roleplay sampling, so temperature/penalties are tuned lower/tighter than CHAT_DEFAULTS.
SUMMARY_DEFAULTS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "min_p": 0.0,
    "top_k": 0,
    "repeat_penalty": 1.1,
    "repeat_last_n": 256,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "max_tokens": 600,
    # Match the chat default so summarizing a long unsummarized backlog doesn't silently
    # truncate the transcript it's meant to condense (which would produce a lossy summary).
    "num_ctx": DEFAULT_NUM_CTX,
}


def ollama_options(src: dict) -> dict:
    """Map our sampler settings (dict or pydantic .model_dump()) onto the `options`
    payload Ollama's /api/chat expects."""
    return {
        "temperature": src["temperature"],
        "top_p": src["top_p"],
        "min_p": src["min_p"],
        "top_k": src["top_k"],
        "repeat_penalty": src["repeat_penalty"],
        "repeat_last_n": src["repeat_last_n"],
        "presence_penalty": src["presence_penalty"],
        "frequency_penalty": src["frequency_penalty"],
        "num_predict": src["max_tokens"],
        "num_ctx": src["num_ctx"],
    }


class Character(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    avatar: str = ""


class Preset(BaseModel):
    """A reusable bundle of prompt-engineering instructions + generation defaults,
    akin to Chub's Presets: pre-history instructions (system_prompt), post-history
    instructions (reinforced right before generation), and an impersonation prompt
    template, plus the sampler settings to go with them."""

    name: str
    system_prompt: str = ""
    post_history_instructions: str = ""
    impersonation_prompt: str = ""
    temperature: float = CHAT_DEFAULTS["temperature"]
    top_p: float = CHAT_DEFAULTS["top_p"]
    min_p: float = CHAT_DEFAULTS["min_p"]
    top_k: int = CHAT_DEFAULTS["top_k"]
    repeat_penalty: float = CHAT_DEFAULTS["repeat_penalty"]
    repeat_last_n: int = CHAT_DEFAULTS["repeat_last_n"]
    presence_penalty: float = CHAT_DEFAULTS["presence_penalty"]
    frequency_penalty: float = CHAT_DEFAULTS["frequency_penalty"]
    max_tokens: int = CHAT_DEFAULTS["max_tokens"]
    model: str = ""


class NewConversationRequest(BaseModel):
    character_id: int
    title: str = ""
    preset_id: int | None = None


class _GenerationRequest(BaseModel):
    """Shared sampler/context fields for the send and impersonate requests."""

    conversation_id: int
    persona: str = ""
    # Scene state ("Author's Note"): a per-conversation description of where the story
    # currently stands, injected right before generation so it outweighs the character
    # card's static opening scenario.
    scene_state: str = ""
    preset_id: int | None = None
    model: str = DEFAULT_LLM_MODEL
    temperature: float = CHAT_DEFAULTS["temperature"]
    top_p: float = CHAT_DEFAULTS["top_p"]
    min_p: float = CHAT_DEFAULTS["min_p"]
    top_k: int = CHAT_DEFAULTS["top_k"]
    repeat_penalty: float = CHAT_DEFAULTS["repeat_penalty"]
    repeat_last_n: int = CHAT_DEFAULTS["repeat_last_n"]
    presence_penalty: float = CHAT_DEFAULTS["presence_penalty"]
    frequency_penalty: float = CHAT_DEFAULTS["frequency_penalty"]
    max_tokens: int = CHAT_DEFAULTS["max_tokens"]
    num_ctx: int = DEFAULT_NUM_CTX


class ChatSendRequest(_GenerationRequest):
    message: str


class ImpersonateRequest(_GenerationRequest):
    pass


class SummarizeRequest(BaseModel):
    conversation_id: int
    model: str = DEFAULT_LLM_MODEL


class SaveSummaryRequest(BaseModel):
    summary: str
    upto_message_id: int


class UpdateMessageRequest(BaseModel):
    content: str
