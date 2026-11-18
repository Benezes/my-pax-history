from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from app.constants import LLM_HTTP_TIMEOUT_SECONDS
from app.llm.mock import mock_llm_delay


class LlmTimeoutTests(unittest.IsolatedAsyncioTestCase):
    def test_http_timeout_covers_three_minute_calls(self):
        self.assertGreaterEqual(LLM_HTTP_TIMEOUT_SECONDS, 180.0)

    async def test_mock_delay_is_off_by_default(self):
        with patch.dict(os.environ, {"MOCK_LLM_DELAY_SECONDS": "0"}):
            start = time.monotonic()
            await mock_llm_delay()
            self.assertLess(time.monotonic() - start, 0.2)

    async def test_mock_delay_sleeps_when_set(self):
        with patch.dict(os.environ, {"MOCK_LLM_DELAY_SECONDS": "0.15"}):
            start = time.monotonic()
            await mock_llm_delay()
            self.assertGreaterEqual(time.monotonic() - start, 0.12)


if __name__ == "__main__":
    unittest.main()
