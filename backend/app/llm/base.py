from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.constants import ProviderId
from app.models import AdvisorReply, CampaignClassification, GameState, TurnLlmBundle


class ProviderError(RuntimeError):
    def __init__(self, message_pt: str):
        super().__init__(message_pt)
        self.message_pt = message_pt


class LlmProvider(ABC):
    provider_id: ProviderId
    last_model: str = ""

    @abstractmethod
    async def interpret_turn(self, state: GameState, pending_texts: list[str]) -> TurnLlmBundle:
        raise NotImplementedError

    @abstractmethod
    async def advise(self, state: GameState, message: str) -> AdvisorReply:
        raise NotImplementedError

    @abstractmethod
    async def estimate_action(self, state: GameState, text: str) -> TurnLlmBundle:
        raise NotImplementedError

    async def classify_campaign(self, texts: list[str]) -> CampaignClassification:
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        return {"ok": True, "provider": self.provider_id}
