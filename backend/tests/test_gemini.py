from __future__ import annotations

import unittest

import httpx

from app.errors import translate_error
from app.llm.base import ProviderError
from app.llm.gemini import GeminiProvider, list_gemini_models


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

    def test_validation_message_is_portuguese(self):
        msg = translate_error(
            {"type": "string_too_long", "loc": ("body", "text"), "ctx": {"max_length": 12000}}
        )
        self.assertIn("12000", msg)
        self.assertNotIn("String should", msg)
        self.assertIn("caracteres", msg)


if __name__ == "__main__":
    unittest.main()
