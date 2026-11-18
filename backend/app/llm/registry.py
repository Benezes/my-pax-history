from __future__ import annotations

from typing import Any

from app.constants import ProviderId
from app.llm.base import LlmProvider, ProviderError
from app.llm.gemini import GeminiProvider, parse_fallback_list, resolve_gemini_model
from app.llm.mock import MockProvider
from app.llm.ollama import OllamaProvider

__all__ = ["get_provider", "provider_status", "ProviderError"]


def get_provider(provider_id: ProviderId, settings: dict[str, Any], api_key: str | None = None) -> LlmProvider:
    if provider_id == ProviderId.MOCK:
        return MockProvider()
    if provider_id == ProviderId.GEMINI:
        key = (api_key or settings.get("gemini_api_key") or "").strip()
        model = resolve_gemini_model(settings.get("gemini_model"))
        return GeminiProvider(
            api_key=key,
            model=model,
            fallbacks=parse_fallback_list(settings.get("gemini_fallback_models")),
        )
    if provider_id == ProviderId.OLLAMA:
        return OllamaProvider(
            base_url=settings.get("ollama_base_url") or "http://127.0.0.1:11434",
            model=settings.get("ollama_model") or "llama3.2",
        )
    raise ProviderError(
        f"Provedor '{provider_id}' ainda não está habilitado. A arquitetura aceita novos provedores "
        "(OpenRouter, OpenAI) registrando uma classe em app/llm/registry.py."
    )


async def provider_status(settings: dict[str, Any]) -> dict[str, Any]:
    mock = MockProvider()
    gemini = GeminiProvider(
        api_key=settings.get("gemini_api_key") or "",
        model=resolve_gemini_model(settings.get("gemini_model")),
    )
    ollama = OllamaProvider(
        base_url=settings.get("ollama_base_url") or "http://127.0.0.1:11434",
        model=settings.get("ollama_model") or "llama3.2",
    )
    return {
        "mock": await mock.health(),
        "gemini": await gemini.health(),
        "ollama": await ollama.health(),
    }
