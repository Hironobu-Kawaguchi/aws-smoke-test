"""LangGraph-based orchestration strategy for chat execution."""

from collections.abc import Mapping
from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from chat_api.model_registry import ModelCapability
from chat_api.providers.base import ChatProvider, ProviderResponse
from chat_api.schemas import ChatRequest

from .base import ChatOrchestrator


class ChatGraphState(TypedDict):
    request: ChatRequest
    capability: ModelCapability
    message_count: int
    response: NotRequired[ProviderResponse]


class LangGraphChatOrchestrator(ChatOrchestrator):
    def __init__(self, providers: Mapping[str, ChatProvider]) -> None:
        self._providers = providers
        graph = StateGraph(ChatGraphState)
        graph.add_node("invoke_provider", self._invoke_provider)
        graph.add_edge(START, "invoke_provider")
        graph.add_edge("invoke_provider", END)
        self._graph = graph.compile()

    def _invoke_provider(self, state: ChatGraphState) -> dict[str, ProviderResponse]:
        capability = state["capability"]
        provider = self._providers.get(capability.provider)
        if provider is None:
            raise RuntimeError(f"Unsupported provider: {capability.provider}")

        return {
            "response": provider.invoke(
                request=state["request"],
                capability=capability,
                message_count=state["message_count"],
            )
        }

    def run(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        initial_state: ChatGraphState = {
            "request": request,
            "capability": capability,
            "message_count": message_count,
        }
        result = cast("ChatGraphState", self._graph.invoke(initial_state))
        response = result.get("response")
        if response is None:
            raise RuntimeError("LangGraph execution did not return a provider response")
        return response
