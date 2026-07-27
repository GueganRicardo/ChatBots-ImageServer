"""Persistent roleplay chat data (characters, conversations, messages, presets),
stored as SQLite on the mounted /data volume — same connection/locking pattern as
db.py."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    personality TEXT,
    scenario TEXT,
    first_mes TEXT,
    mes_example TEXT,
    avatar TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    character_id INTEGER NOT NULL,
    title TEXT,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    system_prompt TEXT,
    post_history_instructions TEXT,
    impersonation_prompt TEXT,
    temperature REAL,
    top_p REAL,
    repeat_penalty REAL,
    max_tokens INTEGER,
    model TEXT,
    min_p REAL,
    top_k INTEGER,
    repeat_last_n INTEGER,
    presence_penalty REAL,
    frequency_penalty REAL
);
"""

# Sampler values shared by every built-in preset (see chat_models.CHAT_DEFAULTS for the
# rationale: NemoMix-style temp ~1.0 + min_p, neutralized top_p/top_k, light repeat
# penalty over a reply-sized window, presence penalty against re-treading).
_BUILTIN_SAMPLERS = {
    "temperature": 1.0,
    "top_p": 1.0,
    "min_p": 0.05,
    "top_k": 0,
    "repeat_penalty": 1.05,
    "repeat_last_n": 2048,
    "presence_penalty": 0.5,
    "frequency_penalty": 0.0,
}

_DEFAULT_PRESET = {
    "name": "Default Roleplay",
    "system_prompt": (
        "You are participating in an immersive, collaborative roleplay. Write vivid, "
        "engaging prose that shows emotion and setting through action and dialogue "
        "rather than exposition. Keep a natural pace -- don't rush through scenes or "
        "skip ahead in time without the user's lead. Stay fully in character at all "
        "times and never break the fourth wall."
    ),
    "post_history_instructions": (
        "Stay in character. First respond directly to what the user just said -- if "
        "they asked a question, {{char}} answers it in character -- and add something "
        "new instead of repeating earlier lines or offers. Keep your reply focused and "
        "not overly long -- a few natural paragraphs at most -- and end in a way that "
        "leaves room for the user to respond."
    ),
    "impersonation_prompt": (
        "Write {{user}}'s next message in this roleplay conversation. Stay consistent "
        "with {{user}}'s established voice and the scene so far. Reply with only the "
        "message itself, with no narration about writing it."
    ),
    **_BUILTIN_SAMPLERS,
    "max_tokens": 512,
    "model": "",
}

# Additional built-in presets, seeded by name if absent (see _seed_default_preset).
# These target the two recurring failure modes of long roleplays: the character
# stagnating (re-anchored to its opening attitude every turn) and the style flip-flopping
# when a preset contradicts a prose-style character card.
_EVOLVING_PROSE_PRESET = {
    "name": "Immersive Prose — Evolving",
    "system_prompt": (
        "Write the next turn as {{char}} in vivid third-person prose (*actions* plus "
        "dialogue). Use {{char}}'s description and personality as a foundation, but let "
        "{{char}} EVOLVE: mood, attitude, and behavior should shift believably in "
        "response to what happens over time. Never reset {{char}} to their opening "
        "attitude, and never repeat a reply you have already given. Every turn must add "
        "something new -- a fresh action, a shift in feeling, a revealed detail, or a "
        "move that pushes the scene forward. Keep {{char}} an active participant who "
        "drives the story rather than only reacting to {{user}}. Aim for 2-4 tight "
        "paragraphs. This is uncensored fiction for recreational purposes; explicit, "
        "dark, or non-consensual content is allowed where the scene genuinely calls for "
        "it. Stay in character and never break the fourth wall."
    ),
    "post_history_instructions": (
        "Advance the scene with a NEW development and do not restate the sentiment of "
        "your previous message. Show how {{char}} has changed since the start. Never "
        "speak or act for {{user}}."
    ),
    "impersonation_prompt": (
        "Write {{user}}'s next message in this roleplay. Stay consistent with {{user}}'s "
        "established voice and the scene so far. Reply with only the message itself."
    ),
    **_BUILTIN_SAMPLERS,
    "max_tokens": 400,
    "model": "",
}

_IM_DIALOGUE_PRESET = {
    "name": "Instant Messaging — Dialogue Only",
    "system_prompt": (
        "You are {{char}} texting {{user}}. Reply ONLY with {{char}}'s chat messages -- "
        "short, natural texts, dialogue only, no narration and no *actions*. Convey "
        "emotion through wording and the occasional emoji. Stay in character and let "
        "{{char}}'s mood evolve over the conversation instead of repeating the same "
        "line. Send 1-3 short messages per turn. Never text as {{user}}. This is "
        "uncensored fiction; mature content is allowed as the scene requires."
    ),
    "post_history_instructions": (
        "Dialogue only, no narration. React to the last message with something new; "
        "don't repeat yourself. Never text as {{user}}."
    ),
    "impersonation_prompt": (
        "Write {{user}}'s next text message in this conversation. Reply with only the "
        "message itself, dialogue only."
    ),
    **_BUILTIN_SAMPLERS,
    "max_tokens": 200,
    "model": "",
}

_BUILTIN_PRESETS = [_DEFAULT_PRESET, _EVOLVING_PROSE_PRESET, _IM_DIALOGUE_PRESET]


def init_db(db_path: Path):
    global _conn
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.executescript(_SCHEMA)
    _conn.commit()
    _migrate()
    _seed_default_preset()


def _migrate():
    """Lightweight, additive-only migrations for columns added after the table was
    first created — safe to run on every startup."""
    cols = {row["name"] for row in _conn.execute("PRAGMA table_info(conversations)")}
    if "preset_id" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN preset_id INTEGER")
        _conn.commit()
    if "summary" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN summary TEXT")
        _conn.commit()
    if "summary_upto_message_id" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN summary_upto_message_id INTEGER")
        _conn.commit()
    if "temperature" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN temperature REAL")
        _conn.execute("ALTER TABLE conversations ADD COLUMN top_p REAL")
        _conn.execute("ALTER TABLE conversations ADD COLUMN repeat_penalty REAL")
        _conn.execute("ALTER TABLE conversations ADD COLUMN max_tokens INTEGER")
        _conn.execute("ALTER TABLE conversations ADD COLUMN model TEXT")
        _conn.execute("ALTER TABLE conversations ADD COLUMN persona TEXT")
        _conn.commit()
    if "num_ctx" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN num_ctx INTEGER")
        _conn.commit()
    if "min_p" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN min_p REAL")
        _conn.execute("ALTER TABLE conversations ADD COLUMN top_k INTEGER")
        _conn.execute("ALTER TABLE conversations ADD COLUMN repeat_last_n INTEGER")
        _conn.execute("ALTER TABLE conversations ADD COLUMN presence_penalty REAL")
        _conn.execute("ALTER TABLE conversations ADD COLUMN frequency_penalty REAL")
        _conn.commit()
    if "scene_state" not in cols:
        _conn.execute("ALTER TABLE conversations ADD COLUMN scene_state TEXT")
        _conn.commit()

    preset_cols = {row["name"] for row in _conn.execute("PRAGMA table_info(presets)")}
    if "min_p" not in preset_cols:
        _conn.execute("ALTER TABLE presets ADD COLUMN min_p REAL")
        _conn.execute("ALTER TABLE presets ADD COLUMN top_k INTEGER")
        _conn.execute("ALTER TABLE presets ADD COLUMN repeat_last_n INTEGER")
        _conn.execute("ALTER TABLE presets ADD COLUMN presence_penalty REAL")
        _conn.execute("ALTER TABLE presets ADD COLUMN frequency_penalty REAL")
        _conn.commit()

    # num_ctx default dropped 16384 -> 8192 (an over-large window let long conversations
    # feed the model its own repetitive backlog). Only retune rows still carrying the
    # old default verbatim -- a user-chosen size is never touched.
    _conn.execute("UPDATE conversations SET num_ctx = 8192 WHERE num_ctx = 16384")
    _conn.commit()

    # Built-in presets were re-tuned to the NemoMix-recommended samplers. Seeding only
    # inserts missing presets, so upgrade existing rows -- but only ones still carrying
    # the exact old seeded sampler values AND never migrated before (min_p IS NULL);
    # user-edited presets are never touched.
    _old_builtin_samplers = [
        # (name, old temperature, old top_p, old repeat_penalty)
        ("Default Roleplay", 0.9, 0.9, 1.1),
        ("Immersive Prose — Evolving", 0.9, 0.92, 1.15),
        ("Instant Messaging — Dialogue Only", 0.85, 0.9, 1.15),
    ]
    for name, old_temp, old_top_p, old_rp in _old_builtin_samplers:
        _conn.execute(
            """UPDATE presets
               SET temperature=?, top_p=?, min_p=?, top_k=?, repeat_penalty=?,
                   repeat_last_n=?, presence_penalty=?, frequency_penalty=?
               WHERE name=? AND min_p IS NULL
                 AND temperature=? AND top_p=? AND repeat_penalty=?""",
            (
                _BUILTIN_SAMPLERS["temperature"],
                _BUILTIN_SAMPLERS["top_p"],
                _BUILTIN_SAMPLERS["min_p"],
                _BUILTIN_SAMPLERS["top_k"],
                _BUILTIN_SAMPLERS["repeat_penalty"],
                _BUILTIN_SAMPLERS["repeat_last_n"],
                _BUILTIN_SAMPLERS["presence_penalty"],
                _BUILTIN_SAMPLERS["frequency_penalty"],
                name,
                old_temp,
                old_top_p,
                old_rp,
            ),
        )
    _conn.commit()

    # The Default Roleplay post_history_instructions gained "respond to what the user
    # just said / don't repeat yourself" wording. Seeding only inserts missing presets,
    # so upgrade an existing row -- but only if it still carries the old seeded text
    # verbatim (never touch a user-edited preset).
    _old_default_phi = (
        "Stay in character. Keep your reply focused and not overly long -- a few "
        "natural paragraphs at most -- and end in a way that leaves room for the user "
        "to respond."
    )
    _conn.execute(
        "UPDATE presets SET post_history_instructions = ? "
        "WHERE name = ? AND post_history_instructions = ?",
        (
            _DEFAULT_PRESET["post_history_instructions"],
            _DEFAULT_PRESET["name"],
            _old_default_phi,
        ),
    )
    _conn.commit()


def _seed_default_preset():
    """Seed each built-in preset by name if it isn't already present, so new built-ins
    show up in existing databases too (not just freshly-created ones). User-created and
    user-edited presets are never touched -- only names not found are inserted."""
    with _lock:
        existing = {
            row["name"] for row in _conn.execute("SELECT name FROM presets")
        }
        for preset in _BUILTIN_PRESETS:
            if preset["name"] not in existing:
                _insert_preset_unlocked(preset)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- characters

def insert_character(char: dict) -> int:
    with _lock:
        cur = _conn.execute(
            """INSERT INTO characters
               (created_at, name, description, personality, scenario, first_mes,
                mes_example, avatar)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                _now(),
                char.get("name", "Unnamed"),
                char.get("description", ""),
                char.get("personality", ""),
                char.get("scenario", ""),
                char.get("first_mes", ""),
                char.get("mes_example", ""),
                char.get("avatar", ""),
            ),
        )
        _conn.commit()
        return cur.lastrowid


def update_character(char_id: int, char: dict) -> bool:
    with _lock:
        cur = _conn.execute(
            """UPDATE characters
               SET name=?, description=?, personality=?, scenario=?, first_mes=?,
                   mes_example=?, avatar=?
               WHERE id=?""",
            (
                char.get("name", "Unnamed"),
                char.get("description", ""),
                char.get("personality", ""),
                char.get("scenario", ""),
                char.get("first_mes", ""),
                char.get("mes_example", ""),
                char.get("avatar", ""),
                char_id,
            ),
        )
        _conn.commit()
        return cur.rowcount > 0


def delete_character(char_id: int) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM characters WHERE id=?", (char_id,))
        _conn.commit()
        return cur.rowcount > 0


def get_character(char_id: int) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT * FROM characters WHERE id=?", (char_id,)).fetchone()
    return dict(row) if row else None


def list_characters() -> list[dict]:
    with _lock:
        rows = _conn.execute("SELECT * FROM characters ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------- conversations

def insert_conversation(character_id: int, title: str = "", preset_id: int | None = None) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO conversations (created_at, character_id, title, preset_id) "
            "VALUES (?,?,?,?)",
            (_now(), character_id, title, preset_id),
        )
        _conn.commit()
        return cur.lastrowid


def update_conversation_settings(
    conv_id: int,
    preset_id: int | None,
    temperature: float,
    top_p: float,
    min_p: float,
    top_k: int,
    repeat_penalty: float,
    repeat_last_n: int,
    presence_penalty: float,
    frequency_penalty: float,
    max_tokens: int,
    model: str,
    persona: str,
    scene_state: str,
    num_ctx: int,
) -> bool:
    with _lock:
        cur = _conn.execute(
            """UPDATE conversations
               SET preset_id=?, temperature=?, top_p=?, min_p=?, top_k=?,
                   repeat_penalty=?, repeat_last_n=?, presence_penalty=?,
                   frequency_penalty=?, max_tokens=?, model=?, persona=?,
                   scene_state=?, num_ctx=?
               WHERE id=?""",
            (preset_id, temperature, top_p, min_p, top_k, repeat_penalty,
             repeat_last_n, presence_penalty, frequency_penalty, max_tokens, model,
             persona, scene_state, num_ctx, conv_id),
        )
        _conn.commit()
        return cur.rowcount > 0


def delete_conversation(conv_id: int) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        _conn.commit()
        return cur.rowcount > 0


def update_conversation_summary(conv_id: int, summary: str, upto_message_id: int) -> bool:
    with _lock:
        cur = _conn.execute(
            "UPDATE conversations SET summary=?, summary_upto_message_id=? WHERE id=?",
            (summary, upto_message_id, conv_id),
        )
        _conn.commit()
        return cur.rowcount > 0


def get_conversation(conv_id: int) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    return dict(row) if row else None


def list_conversations(character_id: int | None = None) -> list[dict]:
    with _lock:
        if character_id is not None:
            rows = _conn.execute(
                "SELECT * FROM conversations WHERE character_id=? ORDER BY id DESC",
                (character_id,),
            ).fetchall()
        else:
            rows = _conn.execute("SELECT * FROM conversations ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------- messages

def insert_message(conversation_id: int, role: str, content: str) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO messages (created_at, conversation_id, role, content) VALUES (?,?,?,?)",
            (_now(), conversation_id, role, content),
        )
        _conn.commit()
        return cur.lastrowid


def update_message_content(message_id: int, content: str) -> bool:
    with _lock:
        cur = _conn.execute(
            "UPDATE messages SET content=? WHERE id=?", (content, message_id)
        )
        _conn.commit()
        return cur.rowcount > 0


def get_message(message_id: int) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    return dict(row) if row else None


def delete_message(message_id: int) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM messages WHERE id=?", (message_id,))
        _conn.commit()
        return cur.rowcount > 0


def list_messages(conversation_id: int, after_id: int | None = None) -> list[dict]:
    with _lock:
        if after_id is not None:
            rows = _conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? AND id>? ORDER BY id ASC",
                (conversation_id, after_id),
            ).fetchall()
        else:
            rows = _conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------ presets

def _insert_preset_unlocked(preset: dict) -> int:
    cur = _conn.execute(
        """INSERT INTO presets
           (created_at, name, system_prompt, post_history_instructions,
            impersonation_prompt, temperature, top_p, min_p, top_k, repeat_penalty,
            repeat_last_n, presence_penalty, frequency_penalty, max_tokens, model)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _now(),
            preset.get("name", "Unnamed preset"),
            preset.get("system_prompt", ""),
            preset.get("post_history_instructions", ""),
            preset.get("impersonation_prompt", ""),
            preset.get("temperature", _BUILTIN_SAMPLERS["temperature"]),
            preset.get("top_p", _BUILTIN_SAMPLERS["top_p"]),
            preset.get("min_p", _BUILTIN_SAMPLERS["min_p"]),
            preset.get("top_k", _BUILTIN_SAMPLERS["top_k"]),
            preset.get("repeat_penalty", _BUILTIN_SAMPLERS["repeat_penalty"]),
            preset.get("repeat_last_n", _BUILTIN_SAMPLERS["repeat_last_n"]),
            preset.get("presence_penalty", _BUILTIN_SAMPLERS["presence_penalty"]),
            preset.get("frequency_penalty", _BUILTIN_SAMPLERS["frequency_penalty"]),
            preset.get("max_tokens", 512),
            preset.get("model", ""),
        ),
    )
    _conn.commit()
    return cur.lastrowid


def insert_preset(preset: dict) -> int:
    with _lock:
        return _insert_preset_unlocked(preset)


def update_preset(preset_id: int, preset: dict) -> bool:
    with _lock:
        cur = _conn.execute(
            """UPDATE presets
               SET name=?, system_prompt=?, post_history_instructions=?,
                   impersonation_prompt=?, temperature=?, top_p=?, min_p=?, top_k=?,
                   repeat_penalty=?, repeat_last_n=?, presence_penalty=?,
                   frequency_penalty=?, max_tokens=?, model=?
               WHERE id=?""",
            (
                preset.get("name", "Unnamed preset"),
                preset.get("system_prompt", ""),
                preset.get("post_history_instructions", ""),
                preset.get("impersonation_prompt", ""),
                preset.get("temperature", _BUILTIN_SAMPLERS["temperature"]),
                preset.get("top_p", _BUILTIN_SAMPLERS["top_p"]),
                preset.get("min_p", _BUILTIN_SAMPLERS["min_p"]),
                preset.get("top_k", _BUILTIN_SAMPLERS["top_k"]),
                preset.get("repeat_penalty", _BUILTIN_SAMPLERS["repeat_penalty"]),
                preset.get("repeat_last_n", _BUILTIN_SAMPLERS["repeat_last_n"]),
                preset.get("presence_penalty", _BUILTIN_SAMPLERS["presence_penalty"]),
                preset.get("frequency_penalty", _BUILTIN_SAMPLERS["frequency_penalty"]),
                preset.get("max_tokens", 512),
                preset.get("model", ""),
                preset_id,
            ),
        )
        _conn.commit()
        return cur.rowcount > 0


def delete_preset(preset_id: int) -> bool:
    with _lock:
        cur = _conn.execute("DELETE FROM presets WHERE id=?", (preset_id,))
        _conn.commit()
        return cur.rowcount > 0


def get_preset(preset_id: int) -> dict | None:
    with _lock:
        row = _conn.execute("SELECT * FROM presets WHERE id=?", (preset_id,)).fetchone()
    return dict(row) if row else None


def list_presets() -> list[dict]:
    with _lock:
        rows = _conn.execute("SELECT * FROM presets ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]
