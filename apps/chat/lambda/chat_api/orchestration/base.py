"""Orchestration interfaces for chat execution."""

from typing import Protocol

from chat_api.model_registry import ModelCapability
from chat_api.providers.base import ProviderResponse
from chat_api.schemas import ChatRequest


class ChatOrchestrator(Protocol):
    def run(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        """Execute the chat request using the selected orchestration strategy."""
