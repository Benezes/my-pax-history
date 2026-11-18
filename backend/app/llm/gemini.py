from __future__ import annotations

from typing import Any

import httpx

from app.constants import ProviderId
from app.llm.base import LlmProvider, ProviderError
from app.llm.jsonutil import JsonParseError, parse_model
from app.llm.prompts import advisor_prompt, estimate_prompt, turn_prompt
from app.models import AdvisorReply, GameState, TurnLlmBundle

GEMINI_MODELS = ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash")


class GeminiProvider(LlmProvider):
    provider_id = ProviderId.GEMINI

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = (api_key or "").strip()
        self.model = (model or GEMINI_MODELS[0]).strip()

    async def health(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "provider": self.provider_id,
                "message": "Chave da API Gemini ausente. Defina GEMINI_API_KEY no .env ou em Configurações.",
            }
        return {"ok": True, "provider": self.provider_id, "model": self.model}

    async def _complete(self, prompt: str) -> str:
        if not self.api_key:
            raise ProviderError(
                "Chave da API Gemini ausente ou inválida. Defina GEMINI_API_KEY no arquivo .env "
                "ou informe a chave em Configurações (fica só neste computador)."
            )
        models = [self.model, *[item for item in GEMINI_MODELS if item != self.model]]
        last_error = "Falha ao contatar o Gemini."
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model in models:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent"
                )
                try:
                    response = await client.post(
                        url,
                        params={"key": self.api_key},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "temperature": 0.4,
                                "responseMimeType": "application/json",
                            },
                        },
                    )
                except httpx.HTTPError as exc:
                    last_error = f"Não foi possível alcançar o Gemini ({exc.__class__.__name__})."
                    continue
                if response.status_code in {401, 403}:
                    raise ProviderError(
                        "Chave da API Gemini inválida ou sem permissão. Verifique a chave em Configurações."
                    )
                if response.status_code >= 400:
                    last_error = f"Gemini retornou HTTP {response.status_code}."
                    continue
                payload = response.json()
                try:
                    return payload["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, TypeError):
                    last_error = "Resposta vazia do Gemini."
                    continue
        raise ProviderError(last_error)

    async def _bundle(self, prompt: str) -> TurnLlmBundle:
        raw = await self._complete(prompt)
        try:
            parsed = parse_model(raw, TurnLlmBundle)
        except JsonParseError:
            repair = await self._complete(
                "Corrija o JSON abaixo para o schema pedido. Devolva SOMENTE JSON válido.\n" + raw[:8000]
            )
            try:
                parsed = parse_model(repair, TurnLlmBundle)
            except JsonParseError as exc:
                raise ProviderError(
                    "A IA devolveu JSON inválido mesmo após correção. Tente de novo ou use o modo offline."
                ) from exc
        assert isinstance(parsed, TurnLlmBundle)
        return parsed

    async def interpret_turn(self, state: GameState, pending_texts: list[str]) -> TurnLlmBundle:
        return await self._bundle(turn_prompt(state, pending_texts))

    async def estimate_action(self, state: GameState, text: str) -> TurnLlmBundle:
        return await self._bundle(estimate_prompt(state, text))

    async def advise(self, state: GameState, message: str) -> AdvisorReply:
        raw = await self._complete(advisor_prompt(state, message))
        try:
            parsed = parse_model(raw, AdvisorReply)
        except JsonParseError:
            return AdvisorReply(reply=raw.strip()[:2000], disagrees=False, risk_level="moderado")
        assert isinstance(parsed, AdvisorReply)
        return parsed
