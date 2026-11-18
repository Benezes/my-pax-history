from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.engine.newgame import create_new_game
from app.engine.turn import advance_months, queue_action
from app.engine.whatif import build_what_if
from app.llm.base import ProviderError
from app.llm.mock import MockProvider
from app.llm.registry import get_provider
from app.models import (
    ActionProposal,
    AdvisorRequest,
    AdvanceRequest,
    ChatMessage,
    NewGameRequest,
    QueueActionRequest,
    SaveRequest,
    TurnLlmBundle,
    WhatIfRequest,
)
from app.present import public_state, public_what_if
from app.settings_load import merged_settings
from app.store import list_games, load_game, put_setting, save_game, snapshot

router = APIRouter(prefix="/api")


def _get(game_id: str):
    state = load_game(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Partida não encontrada.")
    return state


def _provider(state, api_key: str | None = None):
    settings = merged_settings(api_key)
    if state.provider == "gemini" and state.provider_model:
        settings["gemini_model"] = state.provider_model
    if state.provider == "ollama" and state.provider_model:
        settings["ollama_model"] = state.provider_model
    return get_provider(state.provider, settings, api_key)


async def _safe_turn(state, texts: list[str]) -> TurnLlmBundle:
    provider = _provider(state)
    try:
        return await provider.interpret_turn(state, texts)
    except ProviderError as exc:
        if state.provider != "mock" and "JSON" in exc.message_pt:
            return await MockProvider().interpret_turn(state, texts)
        raise
    except Exception as exc:
        if state.provider == "mock":
            raise ProviderError("Falha no provedor offline.") from exc
        return await MockProvider().interpret_turn(state, texts)


@router.post("/games")
async def new_game(body: NewGameRequest):
    settings = merged_settings(body.api_key)
    model = ""
    if body.provider == "gemini":
        model = body.gemini_model or settings.get("gemini_model") or "gemini-2.0-flash"
        settings["gemini_model"] = model
        if body.api_key:
            settings["gemini_api_key"] = body.api_key
            put_setting("gemini_api_key", body.api_key.strip())
    if body.provider == "ollama":
        model = body.ollama_model or settings.get("ollama_model") or "llama3.2"
        settings["ollama_model"] = model
    provider = get_provider(body.provider, settings, body.api_key)
    health = await provider.health()
    if not health.get("ok"):
        raise HTTPException(status_code=400, detail=health.get("message") or "Provedor indisponível.")
    try:
        state = create_new_game(body.difficulty, body.provider, model, body.name)
        save_game(state, kind="active")
        return public_state(state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/games")
async def games():
    return {"active": list_games("active"), "saves": list_games("save")}


@router.get("/games/{game_id}")
async def get_game(game_id: str):
    return public_state(_get(game_id))


@router.post("/games/{game_id}/actions")
async def add_action(game_id: str, body: QueueActionRequest):
    state = _get(game_id)
    if state.status != "playing":
        raise HTTPException(status_code=400, detail="A partida já terminou.")
    queue_action(state, body.text)
    save_game(state)
    return public_state(state)


@router.post("/games/{game_id}/advance")
async def advance(game_id: str, body: AdvanceRequest):
    state = _get(game_id)
    if state.status != "playing":
        raise HTTPException(status_code=400, detail="A partida já terminou.")
    try:
        for _ in range(body.months):
            texts = [item.text for item in state.pending_actions]
            bundle = await _safe_turn(state, texts)
            advance_months(state, [bundle])
            save_game(state)
            if state.status != "playing":
                break
        return public_state(state)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.message_pt) from exc


@router.post("/games/{game_id}/what-if")
async def what_if(game_id: str, body: WhatIfRequest):
    state = _get(game_id)
    before = state.model_dump_json()
    try:
        provider = _provider(state)
        try:
            bundle = await provider.estimate_action(state, body.text)
        except ProviderError:
            raise
        except Exception:
            bundle = await MockProvider().estimate_action(state, body.text)
        proposal: ActionProposal
        if bundle.interpretation.actions:
            proposal = bundle.interpretation.actions[0]
        else:
            proposal = ActionProposal(title="Ação", summary=body.text, category="other", scope="medium")
        commentary = bundle.interpretation.advisor_warning or ""
        disagrees = bool(bundle.interpretation.advisor_warning)
        if not commentary:
            commentary = (
                "Estimativa do assessor com base no estado atual. Nada foi alterado na partida."
            )
        result = build_what_if(state, proposal, body.text, commentary, disagrees, bundle.reactions)
        after = state.model_dump_json()
        if after != before:
            raise HTTPException(status_code=500, detail="A simulação 'E se?' tentou alterar o estado e foi abortada.")
        return public_what_if(result)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.message_pt) from exc


@router.post("/games/{game_id}/advisor")
async def advisor(game_id: str, body: AdvisorRequest):
    state = _get(game_id)
    try:
        provider = _provider(state)
        try:
            reply = await provider.advise(state, body.message)
        except ProviderError:
            raise
        except Exception:
            reply = await MockProvider().advise(state, body.message)
        state.advisor_log.append(
            ChatMessage(role="user", content=body.message, at_month_index=state.date.month_index())
        )
        state.advisor_log.append(
            ChatMessage(
                role="advisor",
                content=reply.reply,
                disagrees=reply.disagrees,
                at_month_index=state.date.month_index(),
            )
        )
        state.advisor_log = state.advisor_log[-40:]
        save_game(state)
        payload = public_state(state)
        payload["advisor_reply"] = reply.model_dump()
        return payload
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=exc.message_pt) from exc


@router.post("/games/{game_id}/save")
async def save(game_id: str, body: SaveRequest):
    state = _get(game_id)
    clone = snapshot(state, body.name)
    return {
        "save": {
            "id": clone.id,
            "name": body.name,
            "game_name": clone.name,
            "updated_at": clone.updated_at,
        }
    }


@router.post("/games/{save_id}/load")
async def load_save(save_id: str):
    source = _get(save_id)
    clone = source.model_copy(deep=True)
    clone.id = source.id.split("-save-")[0] if "-save-" in source.id else source.id
    save_game(clone, kind="active")
    return public_state(clone)
