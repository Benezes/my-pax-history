from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from app.paths import ENV_PATH
from app.store import get_settings

load_dotenv(ENV_PATH)


@lru_cache(maxsize=1)
def env_gemini_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def merged_settings(api_key_override: str | None = None) -> dict[str, str]:
    stored = get_settings()
    if env_gemini_key() and not stored.get("gemini_api_key"):
        stored["gemini_api_key"] = env_gemini_key()
    if os.getenv("GEMINI_MODEL") and not stored.get("gemini_model"):
        stored["gemini_model"] = os.getenv("GEMINI_MODEL") or ""
    if os.getenv("OLLAMA_BASE_URL") and not stored.get("ollama_base_url"):
        stored["ollama_base_url"] = os.getenv("OLLAMA_BASE_URL") or ""
    if os.getenv("OLLAMA_MODEL") and not stored.get("ollama_model"):
        stored["ollama_model"] = os.getenv("OLLAMA_MODEL") or ""
    if api_key_override:
        stored["gemini_api_key"] = api_key_override.strip()
    return stored
