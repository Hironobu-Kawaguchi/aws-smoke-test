"""Direct provider dispatch orchestration."""

from collections.abc import Mapping

from chat_api.model_registry import ModelCapability
from chat_api.orchestration.base import ChatOrchestrator
from chat_api.providers.base import ChatProvider, ProviderResponse
from chat_api.schemas import ChatRequest


class DirectChatOrchestrator(ChatOrchestrator):
    def __init__(self, providers: Mapping[str, ChatProvider]) -> None:
        self._providers = providers

    def run(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        provider = self._providers.get(capability.provider)
        if provider is None:
            raise RuntimeError(f"Unsupported provider: {capability.provider}")
        return provider.invoke(request=request, capability=capability, message_count=message_count)
