"""Application service for chat requests."""

import logging
from collections.abc import Mapping

from chat_api.model_registry import ModelCapability
from chat_api.orchestration.base import ChatOrchestrator
from chat_api.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        model_capabilities: Mapping[str, ModelCapability],
        orchestrator: ChatOrchestrator,
    ) -> None:
        self._model_capabilities = model_capabilities
        self._orchestrator = orchestrator

    def handle_chat(self, request: ChatRequest) -> ChatResponse:
        message_count = len(request.messages)
        logger.info("Chat request received", extra={"message_count": message_count})

        capability = self._model_capabilities[request.model]
        response = self._orchestrator.run(request, capability, message_count)
        return ChatResponse(
            message=response.message,
            response_id=response.response_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_seconds=response.duration_seconds,
        )
