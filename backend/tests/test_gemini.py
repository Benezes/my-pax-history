from __future__ import annotations

import json
import unittest

import httpx

from app.errors import translate_error
from app.llm.base import ProviderError
from app.llm.gemini import (
    GEMINI_FALLBACKS,
    GeminiProvider,
    _candidate_models,
    list_gemini_models,
    retry_after_seconds,
    retry_wait_seconds,
)


def _generate_ok(text: str = '{"interpretation":{"actions":[]},"reactions":[],"events":[],"report":{}}') -> httpx.Response:
    body = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return httpx.Response(200, json=body)


class GeminiHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_models_filters_generate_content(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers.get("x-goog-api-key"), "k")
            self.assertIn("/models", str(request.url))
            self.assertNotIn("key=", str(request.url))
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-flash-latest",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/gemini-3.8-flash",
                            "supportedGenerationMethods": ["generateContent", "countTokens"],
                        },
                        {"name": "models/other", "supportedGenerationMethods": ["embedContent"]},
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            models = await list_gemini_models("k", client=client)
        self.assertEqual(models, ["gemini-flash-latest", "gemini-3.8-flash"])

    async def test_404_falls_through_to_next_model(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers.get("x-goog-api-key"), "k")
            hits.append(str(request.url))
            if "gemini-retired" in str(request.url):
                return httpx.Response(
                    404,
                    json={"error": {"message": "This model models/gemini-retired is no longer available."}},
                )
            if "gemini-flash-latest" in str(request.url):
                return _generate_ok("ok-text")
            return httpx.Response(500, json={"error": {"message": "nope"}})

        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        provider = GeminiProvider(
            api_key="k",
            model="gemini-retired",
            fallbacks=["gemini-flash-latest"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            sleeper=sleeper,
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "ok-text")
        self.assertTrue(any("gemini-retired" in url for url in hits))
        self.assertTrue(any("gemini-flash-latest" in url for url in hits))
        self.assertEqual(sleeps, [])

    async def test_503_retries_then_falls_back(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(str(request.url))
            if "gemini-3.8-flash" in str(request.url):
                return httpx.Response(503, json={"error": {"message": "high demand"}})
            return _generate_ok("later")

        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        provider = GeminiProvider(
            api_key="k",
            model="gemini-3.8-flash",
            fallbacks=["gemini-flash-latest"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            sleeper=sleeper,
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "later")
        self.assertGreaterEqual(sum(1 for url in hits if "gemini-3.8-flash" in url), 2)
        self.assertTrue(any("gemini-flash-latest" in url for url in hits))
        self.assertEqual(sleeps, [0.4, 0.9])

    async def test_timeout_moves_to_next_model(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(str(request.url))
            if "gemini-flash-latest" in str(request.url):
                raise httpx.ReadTimeout("timed out")
            if "gemini-3.1-flash-lite" in str(request.url):
                return _generate_ok("lite-ok")
            return httpx.Response(500, json={"error": {"message": "nope"}})

        provider = GeminiProvider(
            api_key="k",
            model="gemini-flash-latest",
            fallbacks=["gemini-3.1-flash-lite"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "lite-ok")
        self.assertEqual(provider.last_model, "gemini-3.1-flash-lite")
        self.assertTrue(any("gemini-flash-latest" in url for url in hits))
        self.assertTrue(any("gemini-3.1-flash-lite" in url for url in hits))

    async def test_503_on_first_model_falls_to_next(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(str(request.url))
            if "gemini-flash-latest" in str(request.url):
                return httpx.Response(503, json={"error": {"message": "high demand"}})
            return _generate_ok("from-lite")

        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        provider = GeminiProvider(
            api_key="k",
            model="gemini-flash-latest",
            fallbacks=["gemini-3.1-flash-lite"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            sleeper=sleeper,
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "from-lite")
        self.assertEqual(provider.last_model, "gemini-3.1-flash-lite")
        self.assertGreaterEqual(sum(1 for url in hits if "gemini-flash-latest" in url), 2)
        self.assertTrue(any("gemini-3.1-flash-lite" in url for url in hits))
        self.assertEqual(sleeps, [0.4, 0.9])

    async def test_429_respects_retry_after_then_falls_back(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(str(request.url))
            if "gemini-flash-latest" in str(request.url):
                return httpx.Response(
                    429,
                    headers={"Retry-After": "2.5"},
                    json={"error": {"message": "rate limit", "details": [{"retryDelay": "40s"}]}},
                )
            return _generate_ok("after-wait")

        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        provider = GeminiProvider(
            api_key="k",
            model="gemini-flash-latest",
            fallbacks=["gemini-3.1-flash-lite"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            sleeper=sleeper,
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "after-wait")
        self.assertGreaterEqual(sum(1 for url in hits if "gemini-flash-latest" in url), 2)
        self.assertTrue(any("gemini-3.1-flash-lite" in url for url in hits))
        self.assertEqual(sleeps, [2.5, 2.5])

    async def test_429_skips_wait_when_retry_after_exceeds_budget(self):
        hits: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            hits.append(str(request.url))
            if "gemini-flash-latest" in str(request.url):
                return httpx.Response(
                    429,
                    headers={"Retry-After": "60"},
                    json={"error": {"message": "rate limit"}},
                )
            return _generate_ok("next-model")

        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        provider = GeminiProvider(
            api_key="k",
            model="gemini-flash-latest",
            fallbacks=["gemini-3.1-flash-lite"],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            sleeper=sleeper,
            attempt_timeout=5.0,
            total_budget=8.0,
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "next-model")
        self.assertEqual(sum(1 for url in hits if "gemini-flash-latest" in url), 1)
        self.assertTrue(any("gemini-3.1-flash-lite" in url for url in hits))
        self.assertEqual(sleeps, [])

    def test_retry_after_prefers_header_over_json(self):
        response = httpx.Response(
            429,
            headers={"Retry-After": "3"},
            json={"error": {"details": [{"retryDelay": "17s"}]}},
        )
        self.assertEqual(retry_after_seconds(response), 3.0)
        self.assertEqual(retry_wait_seconds(response, 0), 3.0)

    def test_retry_after_reads_json_delay(self):
        response = httpx.Response(
            429,
            json={"error": {"details": [{"retryDelay": "8s"}]}},
        )
        self.assertEqual(retry_after_seconds(response), 8.0)

    async def test_thinking_400_retries_without_thinking_config(self):
        configs: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            config = body.get("generationConfig") or {}
            configs.append(config)
            if "thinkingConfig" in config:
                return httpx.Response(
                    400,
                    json={"error": {"message": "Unknown name 'thinkingConfig' for generationConfig"}},
                )
            return _generate_ok("plain")

        provider = GeminiProvider(
            api_key="k",
            model="gemini-flash-latest",
            fallbacks=[],
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        text = await provider._complete("ping")
        self.assertEqual(text, "plain")
        self.assertEqual(provider.last_model, "gemini-flash-latest")
        self.assertGreaterEqual(len(configs), 2)
        self.assertIn("thinkingConfig", configs[0])
        self.assertNotIn("thinkingConfig", configs[-1])

    def test_fast_models_are_tried_before_38_flash(self):
        ordered = _candidate_models("gemini-flash-latest", list(GEMINI_FALLBACKS))
        self.assertEqual(
            ordered[:3],
            ["gemini-flash-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash"],
        )
        self.assertEqual(ordered[-1], "gemini-3.8-flash")
        self.assertLess(ordered.index("gemini-3.1-flash-lite"), ordered.index("gemini-3.5-flash"))

    def test_validation_message_is_portuguese(self):
        msg = translate_error(
            {"type": "string_too_long", "loc": ("body", "text"), "ctx": {"max_length": 12000}}
        )
        self.assertIn("12000", msg)
        self.assertNotIn("String should", msg)
        self.assertIn("caracteres", msg)


if __name__ == "__main__":
    unittest.main()
