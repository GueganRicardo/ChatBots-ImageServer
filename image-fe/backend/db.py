"""Persistent generation history, stored as SQLite on the mounted /data volume."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    width INTEGER,
    height INTEGER,
    steps INTEGER,
    cfg REAL,
    sampler_name TEXT,
    scheduler TEXT,
    denoise REAL,
    batch_size INTEGER,
    seed INTEGER,
    model TEXT,
    loras TEXT,
    images TEXT NOT NULL
);
"""


def init_db(db_path: Path):
    global _conn
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute(_SCHEMA)
    # migrate pre-existing databases created before the loras column
    cols = {row["name"] for row in _conn.execute("PRAGMA table_info(generations)")}
    if "loras" not in cols:
        _conn.execute("ALTER TABLE generations ADD COLUMN loras TEXT")
    _conn.commit()


def insert_generation(params: dict, images: list[str]) -> int:
    with _lock:
        cur = _conn.execute(
            """INSERT INTO generations
               (created_at, prompt, negative_prompt, width, height, steps, cfg,
                sampler_name, scheduler, denoise, batch_size, seed, model, loras, images)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                params.get("prompt", ""),
                params.get("negative_prompt", ""),
                params.get("width"),
                params.get("height"),
                params.get("steps"),
                params.get("cfg"),
                params.get("sampler_name"),
                params.get("scheduler"),
                params.get("denoise"),
                params.get("batch_size"),
                params.get("seed"),
                params.get("model"),
                json.dumps(params.get("loras") or []),
                json.dumps(images),
            ),
        )
        _conn.commit()
        return cur.lastrowid


def list_generations(limit: int = 60, before_id: int | None = None) -> list[dict]:
    """Newest first. `before_id` is a cursor: only rows older than that id are
    returned, so pagination stays stable while new generations are inserted."""
    query = "SELECT * FROM generations"
    params: list = []
    if before_id is not None:
        query += " WHERE id < ?"
        params.append(before_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _lock:
        rows = _conn.execute(query, params).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["images"] = [f"/api/images/{name}" for name in json.loads(d["images"])]
        d["loras"] = json.loads(d["loras"]) if d.get("loras") else []
        result.append(d)
    return result


def delete_generation(gen_id: int) -> list[str] | None:
    """Deletes the row and returns the raw (unprefixed) image filenames that were
    associated with it, so the caller can remove them from disk. Returns None if
    the generation didn't exist."""
    with _lock:
        row = _conn.execute(
            "SELECT images FROM generations WHERE id=?", (gen_id,)
        ).fetchone()
        if not row:
            return None
        _conn.execute("DELETE FROM generations WHERE id=?", (gen_id,))
        _conn.commit()
    return json.loads(row["images"])
