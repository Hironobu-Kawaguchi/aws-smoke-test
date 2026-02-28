"""Bedrock provider implementation for chat requests."""

import logging
import time
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

from chat_api.message_mappers import build_bedrock_messages
from chat_api.model_registry import ModelCapability
from chat_api.schemas import ChatRequest

from .base import ProviderResponse

logger = logging.getLogger(__name__)


class BedrockChatProvider:
    def __init__(
        self,
        get_bedrock_runnable: Callable[[], Runnable[dict[str, Any], AIMessage]],
    ) -> None:
        self._get_bedrock_runnable = get_bedrock_runnable

    def invoke(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        lc_messages = build_bedrock_messages(request.messages, request.system_prompt)

        start = time.time()
        params: dict[str, Any] = {
            "model_id": request.model,
            "messages": lc_messages,
            "max_tokens": request.max_output_tokens,
        }
        if capability.supports_temperature and request.temperature is not None:
            params["temperature"] = request.temperature

        response = self._get_bedrock_runnable().invoke(
            params,
            config={
                "run_name": "chat_lambda_request",
                "tags": ["chat-api", request.model],
                "metadata": {"message_count": message_count},
            },
        )
        duration_ms = int((time.time() - start) * 1000)

        content = ""
        if isinstance(response.content, str):
            content = response.content
        elif isinstance(response.content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in response.content
            )

        usage = response.usage_metadata
        input_tokens = usage.get("input_tokens") if usage else None
        output_tokens = usage.get("output_tokens") if usage else None

        response_metadata = response.response_metadata or {}
        request_id = (
            response_metadata.get("ResponseMetadata", {}).get("RequestId", "") or response.id or ""
        )

        logger.info(
            "Chat response generated",
            extra={
                "bedrock_duration_ms": duration_ms,
                "model": request.model,
                "usage_prompt_tokens": input_tokens,
                "usage_completion_tokens": output_tokens,
                "response_length": len(content),
                "response_id": request_id,
            },
        )
        return ProviderResponse(
            message=content,
            response_id=request_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=round(duration_ms / 1000, 2),
        )
