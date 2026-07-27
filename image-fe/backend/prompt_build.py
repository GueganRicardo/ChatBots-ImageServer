"""Assemble the messages array sent to Ollama's /api/chat for a roleplay turn.

Mirrors the role workflow.py plays for image generation: a small pure function that
turns our stored data (character card + conversation history + preset) into exactly
what the downstream API expects.

Preset fields (see chat_models.Preset), modeled on Chub.ai's Presets:
  system_prompt              "pre-history instructions": global tone/genre/style
                              rules, prepended ahead of the character-specific block.
  post_history_instructions  reinforcement, folded onto the *latest user message*
                              (not sent as a separate system turn) so it stays
                              maximally recent regardless of which model/template
                              Ollama is using underneath -- more portable than relying
                              on a model-specific "insert after history" mechanism.
  impersonation_prompt       template for the Impersonate feature; supports simple
                              {{user}}/{{char}} placeholders.

Conversations can additionally carry a scene_state ("Author's Note"): a short
description of where the story currently stands. It is folded onto the latest user
message (before the preset's post-history instructions) so that recency lets it
override the character card's static opening scenario — the mechanism that lets a
character actually progress past their card's initial attitude on small models.
"""


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~3.5 chars/token for English prose) used to fit prompts
    into num_ctx without a real tokenizer. Deliberately errs on the high side."""
    return max(1, int(len(text) / 3.5))


def _system_prompt(
    character: dict, persona: str, preset: dict | None, summary: str | None = None
) -> str:
    name = character.get("name", "the character")
    parts = []

    # Every text field below may contain {{char}}/{{user}} placeholders (character cards
    # and presets are authored in the SillyTavern/Chub convention); render them so the
    # model never sees a literal "{{user}}". See _render_template.
    def r(text: str) -> str:
        return _render_template(text, character, persona)

    if preset and preset.get("system_prompt"):
        parts.append(r(preset["system_prompt"]))

    parts.append(
        f"You are {name}. Stay in character at all times and never break the fourth "
        f"wall or acknowledge being an AI."
    )
    if character.get("description"):
        parts.append(f"Description: {r(character['description'])}")
    if character.get("personality"):
        parts.append(f"Personality: {r(character['personality'])}")
    # Example dialogue goes BEFORE scenario/summary: it is only a voice reference, and
    # small models treat whatever sits closest to the live conversation as script to
    # replay -- keep the actual story state (scenario, summary) most recent instead.
    if character.get("mes_example"):
        parts.append(
            "Example dialogue (voice and style reference only -- these exchanges are "
            "hypothetical and are NOT part of the story; never copy or repeat their "
            f"lines or offers):\n{r(character['mes_example'])}"
        )
    if character.get("scenario"):
        parts.append(f"Scenario: {r(character['scenario'])}")
    if summary:
        parts.append(f"Story so far (summary of earlier events): {r(summary)}")
    if persona:
        parts.append(f"The user you are talking to can be described as: {persona}")
    return "\n\n".join(parts)


def _render_template(template: str, character: dict, persona: str) -> str:
    name = character.get("name", "the character")
    user = persona.strip() or "the user"
    return template.replace("{{char}}", name).replace("{{user}}", user)


def build_messages(
    character: dict,
    history: list[dict],
    persona: str = "",
    preset: dict | None = None,
    summary: str | None = None,
    scene_state: str = "",
) -> list[dict]:
    """history: list of {"role": "user"|"assistant", "content": str}, oldest first.
    Does NOT include the character's first_mes if history already starts with it —
    the caller is responsible for seeding first_mes into stored messages once, when
    the conversation is created. If `summary` is set, `history` is expected to only
    contain messages *after* the summarized point — the caller (main.py) is
    responsible for that filtering via chat_db.list_messages(after_id=...).
    """
    messages = [
        {"role": "system", "content": _system_prompt(character, persona, preset, summary)}
    ]
    # Stored history may contain {{char}}/{{user}} placeholders too (the seeded
    # first_mes comes straight off the character card); render at build time so a
    # later persona change re-renders correctly while stored data stays canonical.
    messages.extend(
        {"role": m["role"], "content": _render_template(m["content"], character, persona)}
        for m in history
    )

    # Recency-weighted folds onto the latest user message: scene state first (story
    # facts), then post-history instructions (behavioral rules) closest to generation.
    folds = []
    if scene_state and scene_state.strip():
        folds.append(f"[Current scene: {_render_template(scene_state, character, persona)}]")
    phi = preset.get("post_history_instructions") if preset else None
    if phi:
        folds.append(f"[Instructions: {_render_template(phi, character, persona)}]")
    if folds and messages and messages[-1]["role"] == "user":
        last = messages[-1]
        messages[-1] = {**last, "content": "\n\n".join([last["content"], *folds])}

    return messages


def build_impersonation_messages(
    character: dict,
    history: list[dict],
    persona: str = "",
    preset: dict | None = None,
    summary: str | None = None,
    scene_state: str = "",
) -> list[dict]:
    """Like build_messages, but instead of expecting a real user turn to reply to,
    appends a synthetic user-role instruction asking the model to draft the user's
    next line. The result is meant to be shown as an editable suggestion, never
    persisted as a real message."""
    messages = [
        {"role": "system", "content": _system_prompt(character, persona, preset, summary)}
    ]
    messages.extend(
        {"role": m["role"], "content": _render_template(m["content"], character, persona)}
        for m in history
    )

    template = (preset or {}).get("impersonation_prompt") or (
        "Write {{user}}'s next message in this conversation, staying consistent with "
        "the established voice and scene so far. Reply with only the message itself."
    )
    instruction = _render_template(template, character, persona)
    if scene_state and scene_state.strip():
        scene = _render_template(scene_state, character, persona)
        instruction = f"[Current scene: {scene}]\n\n{instruction}"
    messages.append({"role": "user", "content": instruction})
    return messages


def build_summary_messages(
    character: dict,
    history: list[dict],
    existing_summary: str | None = None,
) -> list[dict]:
    """Builds a one-shot prompt asking the model to produce an updated summary of the
    conversation so far, folding in any existing_summary plus the not-yet-summarized
    history. Meant to be sent with low-temperature sampler settings (see
    chat_models.SUMMARY_DEFAULTS) since this wants a factual recap, not creative
    prose. Result is never persisted directly -- the caller shows it to the user for
    review/editing first.

    The summarize instruction is restated AFTER the transcript: with only a top-of-
    prompt instruction, small RP-tuned models handed thousands of tokens of story
    simply continue the story instead of summarizing (observed live). The instruction
    closest to the generation point is the one that wins."""
    name = character.get("name", "the character")
    instructions = (
        f"You are a summarizer. Summarize the roleplay conversation transcript below "
        f"between the user and {name}. Write a concise, third-person recap that "
        "preserves important facts, relationship/emotional developments, established "
        "scene or setting details, and any unresolved plot threads -- enough for the "
        "roleplay to continue seamlessly without the full transcript. Do not write "
        "dialogue or continue the scene; only summarize what has already happened."
    )
    if existing_summary:
        instructions += (
            f"\n\nHere is the summary of everything before this transcript:\n{existing_summary}\n\n"
            "Fold that together with the new transcript below into a single, updated summary."
        )

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else name}: "
        f"{_render_template(m['content'], character, '')}"
        for m in history
    )
    reminder = (
        "END OF TRANSCRIPT. Now write the concise third-person summary described "
        "above. Summarize only -- do not write dialogue, do not add new events, and "
        "do not continue the story."
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": f"{transcript}\n\n---\n\n{reminder}"},
    ]
