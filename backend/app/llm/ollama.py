from __future__ import annotations

from typing import Any

import httpx

from app.constants import LLM_HTTP_TIMEOUT_SECONDS, ProviderId
from app.llm.base import LlmProvider, ProviderError
from app.llm.jsonutil import JsonParseError, parse_model
from app.llm.prompts import advisor_prompt, estimate_prompt, turn_prompt
from app.models import AdvisorReply, GameState, TurnLlmBundle


class OllamaProvider(LlmProvider):
    provider_id = ProviderId.OLLAMA

    def __init__(self, base_url: str, model: str):
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or "llama3.2"

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return {
                    "ok": False,
                    "provider": self.provider_id,
                    "message": "Ollama respondeu com erro. Confira se o serviço está no ar.",
                }
            names = [item.get("name", "") for item in response.json().get("models", [])]
            return {
                "ok": True,
                "provider": self.provider_id,
                "model": self.model,
                "models": names,
            }
        except httpx.HTTPError:
            return {
                "ok": False,
                "provider": self.provider_id,
                "message": (
                    "Ollama não está em execução. No macOS, abra o app Ollama e rode "
                    f"`ollama pull {self.model}` (sugestão: llama3.2)."
                ),
            }

    async def _complete(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_HTTP_TIMEOUT_SECONDS, connect=20.0)) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "format": "json",
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Ollama não está em execução ou não respondeu. Inicie o Ollama e baixe um modelo, "
                f"por exemplo: ollama pull {self.model}."
            ) from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"Ollama retornou HTTP {response.status_code}. Verifique se o modelo {self.model} está instalado."
            )
        payload = response.json()
        content = (payload.get("message") or {}).get("content") or payload.get("response") or ""
        if not content:
            raise ProviderError("Ollama devolveu resposta vazia.")
        return content

    async def _bundle(self, prompt: str) -> TurnLlmBundle:
        raw = await self._complete(prompt)
        try:
            parsed = parse_model(raw, TurnLlmBundle)
        except JsonParseError:
            repair = await self._complete(
                "Corrija e devolva SOMENTE JSON válido no schema combinado:\n" + raw[:8000]
            )
            try:
                parsed = parse_model(repair, TurnLlmBundle)
            except JsonParseError as exc:
                raise ProviderError(
                    "O modelo local devolveu JSON inválido mesmo após correção. Troque o modelo ou use o modo offline."
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
