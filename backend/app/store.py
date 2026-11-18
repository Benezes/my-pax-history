from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.models import GameState
from app.paths import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(SCHEMA)


def save_game(state: GameState, kind: str = "active") -> None:
    state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = state.model_dump_json()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO games (id, kind, name, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                name = excluded.name,
                updated_at = excluded.updated_at,
                state_json = excluded.state_json
            """,
            (state.id, kind, state.name, state.updated_at, payload),
        )


def load_game(game_id: str) -> GameState | None:
    with _connect() as connection:
        row = connection.execute("SELECT state_json FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return None
    return GameState.model_validate_json(row["state_json"])


def delete_game(game_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM games WHERE id = ?", (game_id,))


def list_games(kind: str | None = None) -> list[dict]:
    sql = "SELECT id, kind, name, updated_at FROM games"
    params: tuple = ()
    if kind:
        sql += " WHERE kind = ?"
        params = (kind,)
    sql += " ORDER BY updated_at DESC"
    with _connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def snapshot(state: GameState, name: str) -> GameState:
    clone = state.model_copy(deep=True)
    clone.id = state.id + "-save-" + datetime.now(timezone.utc).strftime("%H%M%S") + clone.id[:4]
    clone.name = name
    save_game(clone, kind="save")
    return clone


def get_settings() -> dict[str, str]:
    with _connect() as connection:
        rows = connection.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def put_setting(key: str, value: str) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def settings_public(raw: dict[str, str], env_key_present: bool) -> dict:
    gemini = raw.get("gemini_api_key") or ""
    return {
        "gemini_api_key_set": bool(gemini) or env_key_present,
        "gemini_model": raw.get("gemini_model") or "gemini-2.0-flash",
        "ollama_base_url": raw.get("ollama_base_url") or "http://127.0.0.1:11434",
        "ollama_model": raw.get("ollama_model") or "llama3.2",
    }
