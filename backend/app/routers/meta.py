from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config_loader import ConfigError, parse_brazil, parse_world
from app.constants import DIFFICULTY_LABELS, PROVIDER_LABELS, Difficulty, ProviderId
from app.llm.registry import provider_status
from app.models import SettingsUpdate
from app.settings_load import env_gemini_key, merged_settings
from app.store import put_setting, settings_public

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/meta")
async def meta():
    settings = merged_settings()
    status = await provider_status(settings)
    return {
        "providers": [
            {"id": item.value, "label": PROVIDER_LABELS[item], "status": status.get(item.value)}
            for item in ProviderId
        ],
        "difficulties": [
            {
                "id": item.value,
                "label": DIFFICULTY_LABELS[item],
                "blurb": {
                    Difficulty.MEDIO: "Desafios coerentes, oposição realista, sem cerco permanente.",
                    Difficulty.DIFICIL: "Agentes antecipam, exploram falhas e criam problemas secundários.",
                    Difficulty.IMPOSSIVEL: "Cada movimento encontra reação calculada — um xadrez hostil.",
                }[item],
            }
            for item in Difficulty
        ],
        "settings": settings_public(settings, bool(env_gemini_key())),
    }


@router.get("/config/preview")
async def preview():
    try:
        brazil = parse_brazil()
        world = parse_world()
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "indicators": brazil["indicators"],
        "budget": brazil["budget"].model_dump(),
        "problems": [item.model_dump() for item in brazil["problems"]],
        "powers": [item.model_dump() for item in world["powers"].values()],
    }


@router.post("/settings")
async def update_settings(body: SettingsUpdate):
    mapping = {
        "gemini_api_key": body.gemini_api_key,
        "gemini_model": body.gemini_model,
        "ollama_base_url": body.ollama_base_url,
        "ollama_model": body.ollama_model,
        "default_provider": body.default_provider,
    }
    if body.default_provider is not None and body.default_provider not in {item.value for item in ProviderId}:
        raise HTTPException(status_code=400, detail="Provedor padrão inválido.")
    for key, value in mapping.items():
        if value is not None:
            put_setting(key, value.strip())
    settings = merged_settings()
    return settings_public(settings, bool(env_gemini_key()))
