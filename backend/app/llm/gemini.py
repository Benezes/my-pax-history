from __future__ import annotations

import asyncio
import logging
import re
import time
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx

from app.constants import (
    GEMINI_ATTEMPT_TIMEOUT_DEFAULT,
    GEMINI_TOTAL_BUDGET_DEFAULT,
    ProviderId,
    env_float,
)
from app.llm.base import LlmProvider, ProviderError
from app.llm.jsonutil import JsonParseError, parse_model
from app.llm.prompts import advisor_prompt, campaign_prompt, estimate_prompt, turn_prompt
from app.models import AdvisorReply, CampaignClassification, GameState, TurnLlmBundle

logger = logging.getLogger("presidencia.llm")

GEMINI_DEFAULT = "gemini-flash-latest"
GEMINI_STALE = frozenset({"gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"})
GEMINI_FALLBACKS = (
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-pro-latest",
    "gemini-3.8-flash",
)
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUSES = {429, 503}
SKIP_STATUSES = {404}
BACKOFF_SECONDS = (0.4, 0.9)
_DURATION_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*s?\s*$", re.IGNORECASE)


def _headers(api_key: str) -> dict[str, str]:
    return {"x-goog-api-key": api_key, "Content-Type": "application/json"}


def _model_id(name: str) -> str:
    text = (name or "").strip()
    if text.startswith("models/"):
        return text.split("/", 1)[1]
    return text


def resolve_gemini_model(raw: str | None) -> str:
    model = _model_id(raw or "") or GEMINI_DEFAULT
    if model in GEMINI_STALE:
        return GEMINI_DEFAULT
    return model


def parse_fallback_list(raw: str | None) -> list[str]:
    if not raw:
        return list(GEMINI_FALLBACKS)
    items = [_model_id(part) for part in raw.split(",") if part.strip()]
    return items or list(GEMINI_FALLBACKS)


def _candidate_models(preferred: str, extras: list[str]) -> list[str]:
    ordered: list[str] = []
    for item in [preferred, *extras, *GEMINI_FALLBACKS]:
        name = _model_id(item)
        if name and name not in ordered:
            ordered.append(name)
    return ordered


async def list_gemini_models(api_key: str, client: httpx.AsyncClient | None = None) -> list[str]:
    key = (api_key or "").strip()
    if not key:
        raise ProviderError("Chave da API Gemini ausente. Informe a chave em Configurações.")
    own = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.get(f"{GEMINI_BASE}/models", headers=_headers(key))
    except httpx.HTTPError as exc:
        raise ProviderError(f"Não foi possível listar os modelos Gemini ({exc.__class__.__name__}).") from exc
    finally:
        if own:
            await http.aclose()
    if response.status_code in {401, 403}:
        raise ProviderError("Chave da API Gemini inválida ou sem permissão. Verifique a chave em Configurações.")
    if response.status_code >= 400:
        raise ProviderError(_pt_http_error(response.status_code, response.text))
    payload = response.json()
    models: list[str] = []
    for item in payload.get("models") or []:
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = _model_id(item.get("name") or "")
        if name:
            models.append(name)
    return models


def _parse_duration_seconds(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return max(0.0, float(raw))
    if isinstance(raw, dict):
        seconds = raw.get("seconds")
        if seconds is None:
            return None
        nanos = float(raw.get("nanos") or 0) / 1_000_000_000
        try:
            return max(0.0, float(seconds) + nanos)
        except (TypeError, ValueError):
            return None
    match = _DURATION_RE.match(str(raw))
    if not match:
        return None
    return max(0.0, float(match.group(1)))


def retry_after_seconds(response: httpx.Response) -> float | None:
    header = (response.headers.get("retry-after") or response.headers.get("Retry-After") or "").strip()
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            try:
                when = parsedate_to_datetime(header)
                return max(0.0, when.timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass
    try:
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    details = error.get("details") or payload.get("details") or []
    if isinstance(details, dict):
        details = [details]
    for item in details:
        if not isinstance(item, dict):
            continue
        parsed = _parse_duration_seconds(item.get("retryDelay") or item.get("retry_delay"))
        if parsed is not None:
            return parsed
    return _parse_duration_seconds(
        error.get("retryDelay") or error.get("retry_delay") or payload.get("retryDelay")
    )


def retry_wait_seconds(response: httpx.Response, attempt: int) -> float:
    parsed = retry_after_seconds(response)
    if parsed is not None:
        return parsed
    if 0 <= attempt < len(BACKOFF_SECONDS):
        return BACKOFF_SECONDS[attempt]
    return BACKOFF_SECONDS[-1]


def _pt_http_error(status: int, body: str) -> str:
    lowered = (body or "").lower()
    if status == 404 or "no longer available" in lowered:
        return "Este modelo Gemini não está mais disponível. Escolha outro em Configurações."
    if status == 429:
        return "O Gemini recusou a requisição por limite de uso. Aguarde um momento e tente de novo."
    if status == 503 or "high demand" in lowered:
        return "O Gemini está com demanda alta no momento. Tentando outro modelo."
    if status in {401, 403}:
        return "Chave da API Gemini inválida ou sem permissão. Verifique a chave em Configurações."
    return f"O Gemini retornou um erro (HTTP {status})."


def _generation_config(with_thinking: bool) -> dict[str, Any]:
    config: dict[str, Any] = {
        "temperature": 0.4,
        "responseMimeType": "application/json",
    }
    if with_thinking:
        config["thinkingConfig"] = {
            "thinkingBudget": 256,
            "thinkingLevel": "LOW",
        }
    return config


def _uses_thinking(model: str) -> bool:
    return "flash" in (model or "").lower()


class GeminiProvider(LlmProvider):
    provider_id = ProviderId.GEMINI

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        fallbacks: list[str] | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        sleeper: Callable[[float], Any] | None = None,
        attempt_timeout: float | None = None,
        total_budget: float | None = None,
    ):
        self.api_key = (api_key or "").strip()
        self.model = resolve_gemini_model(model)
        self.fallbacks = fallbacks if fallbacks is not None else list(GEMINI_FALLBACKS)
        self._client_factory = client_factory
        self._sleeper = sleeper or asyncio.sleep
        self.attempt_timeout = (
            attempt_timeout
            if attempt_timeout is not None
            else env_float("GEMINI_ATTEMPT_TIMEOUT_SECONDS", GEMINI_ATTEMPT_TIMEOUT_DEFAULT)
        )
        self.total_budget = (
            total_budget
            if total_budget is not None
            else env_float("GEMINI_TOTAL_BUDGET_SECONDS", GEMINI_TOTAL_BUDGET_DEFAULT)
        )
        self.last_model = ""

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
        models = _candidate_models(self.model, self.fallbacks)
        last_error = "Falha ao contatar o Gemini."
        deadline = time.monotonic() + self.total_budget
        client = (
            self._client_factory()
            if self._client_factory
            else httpx.AsyncClient(timeout=httpx.Timeout(self.total_budget, connect=20.0))
        )
        try:
            for model in models:
                remaining = deadline - time.monotonic()
                if remaining < 4:
                    last_error = (
                        "Nenhum modelo Gemini respondeu a tempo. Tente de novo ou use o modo offline."
                    )
                    break
                thinking = _uses_thinking(model)
                for attempt in range(1 + len(BACKOFF_SECONDS)):
                    remaining = deadline - time.monotonic()
                    if remaining < 4:
                        break
                    url = f"{GEMINI_BASE}/models/{model}:generateContent"
                    request_timeout = min(self.attempt_timeout, remaining)
                    started = time.monotonic()
                    try:
                        response = await client.post(
                            url,
                            headers=_headers(self.api_key),
                            timeout=request_timeout,
                            json={
                                "contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": _generation_config(thinking),
                            },
                        )
                    except httpx.TimeoutException:
                        elapsed = time.monotonic() - started
                        logger.warning("gemini model=%s outcome=timeout duration=%.1fs", model, elapsed)
                        last_error = f"O modelo {model} não respondeu a tempo. Tentando outro."
                        break
                    except httpx.HTTPError as exc:
                        elapsed = time.monotonic() - started
                        logger.warning(
                            "gemini model=%s outcome=http_error duration=%.1fs error=%s",
                            model,
                            elapsed,
                            exc.__class__.__name__,
                        )
                        last_error = f"Não foi possível alcançar o Gemini ({exc.__class__.__name__})."
                        break
                    elapsed = time.monotonic() - started
                    if response.status_code in {401, 403}:
                        raise ProviderError(
                            "Chave da API Gemini inválida ou sem permissão. Verifique a chave em Configurações."
                        )
                    if (
                        response.status_code == 400
                        and thinking
                        and "thinking" in (response.text or "").lower()
                    ):
                        logger.info(
                            "gemini model=%s outcome=thinking_rejected duration=%.1fs",
                            model,
                            elapsed,
                        )
                        thinking = False
                        last_error = _pt_http_error(response.status_code, response.text)
                        continue
                    if response.status_code in SKIP_STATUSES:
                        logger.warning(
                            "gemini model=%s outcome=skip status=%s duration=%.1fs",
                            model,
                            response.status_code,
                            elapsed,
                        )
                        last_error = _pt_http_error(response.status_code, response.text)
                        break
                    if response.status_code in RETRY_STATUSES:
                        last_error = _pt_http_error(response.status_code, response.text)
                        wait = retry_wait_seconds(response, attempt)
                        remaining = deadline - time.monotonic()
                        logger.warning(
                            "gemini model=%s outcome=retry status=%s duration=%.1fs wait=%.1fs remaining=%.1fs",
                            model,
                            response.status_code,
                            elapsed,
                            wait,
                            remaining,
                        )
                        if attempt >= len(BACKOFF_SECONDS) or remaining < 4:
                            break
                        if wait > max(0.0, remaining - 4.0):
                            break
                        await self._sleeper(wait)
                        continue
                    if response.status_code >= 400:
                        last_error = _pt_http_error(response.status_code, response.text)
                        logger.warning(
                            "gemini model=%s outcome=error status=%s duration=%.1fs",
                            model,
                            response.status_code,
                            elapsed,
                        )
                        break
                    payload = response.json()
                    try:
                        text = payload["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError, TypeError):
                        last_error = "Resposta vazia do Gemini."
                        logger.warning("gemini model=%s outcome=empty duration=%.1fs", model, elapsed)
                        break
                    self.last_model = model
                    logger.info("gemini model=%s outcome=ok duration=%.1fs", model, elapsed)
                    return text
        finally:
            await client.aclose()
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

    async def classify_campaign(self, texts: list[str]) -> CampaignClassification:
        raw = await self._complete(campaign_prompt(texts))
        try:
            parsed = parse_model(raw, CampaignClassification)
        except JsonParseError as exc:
            raise ProviderError(
                "A IA não classificou a campanha em JSON válido. Tente de novo ou use o modo offline."
            ) from exc
        assert isinstance(parsed, CampaignClassification)
        return parsed
