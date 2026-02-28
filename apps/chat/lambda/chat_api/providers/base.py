"""Provider interfaces and shared response model."""

from dataclasses import dataclass
from typing import Protocol

from chat_api.model_registry import ModelCapability
from chat_api.schemas import ChatRequest


@dataclass(frozen=True)
class ProviderResponse:
    message: str
    response_id: str
    input_tokens: int | None
    output_tokens: int | None
    duration_seconds: float


class ChatProvider(Protocol):
    def invoke(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        """Invoke a provider with normalized chat request data."""
        ...
