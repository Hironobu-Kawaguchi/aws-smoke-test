"""OpenAI provider implementation for chat requests."""

import logging
import time
from collections.abc import Callable
from typing import Any

from langchain_core.runnables import Runnable
from openai import OpenAI

from chat_api.message_mappers import build_openai_content_parts
from chat_api.model_registry import ModelCapability
from chat_api.schemas import ChatRequest

from .base import ProviderResponse

logger = logging.getLogger(__name__)


class OpenAIChatProvider:
    def __init__(
        self,
        get_openai_client: Callable[[], OpenAI],
        get_chat_responses_runnable: Callable[[], Runnable[dict[str, Any], Any]],
    ) -> None:
        self._get_openai_client = get_openai_client
        self._get_chat_responses_runnable = get_chat_responses_runnable

    def invoke(
        self, request: ChatRequest, capability: ModelCapability, message_count: int
    ) -> ProviderResponse:
        input_messages = []
        for message in request.messages:
            content_parts = build_openai_content_parts(message)
            if content_parts:
                input_messages.append({"role": message.role, "content": content_parts})

        self._get_openai_client()
        start = time.time()
        request_params: dict[str, Any] = {
            "model": request.model,
            "instructions": request.system_prompt or None,
            "input": input_messages,
            "max_output_tokens": request.max_output_tokens,
        }
        if capability.supports_temperature and request.temperature is not None:
            request_params["temperature"] = request.temperature
        if capability.supports_reasoning_effort and request.reasoning_effort is not None:
            request_params["reasoning"] = {"effort": request.reasoning_effort}
        if request.web_search_enabled:
            request_params["tools"] = [{"type": "web_search"}]
        if request.previous_response_id:
            request_params["previous_response_id"] = request.previous_response_id

        response = self._get_chat_responses_runnable().invoke(
            request_params,
            config={
                "run_name": "chat_lambda_request",
                "tags": ["chat-api", request.model],
                "metadata": {
                    "message_count": message_count,
                    "web_search_enabled": request.web_search_enabled,
                },
            },
        )
        duration_ms = int((time.time() - start) * 1000)
        content = response.output_text or ""

        logger.info(
            "Chat response generated",
            extra={
                "openai_duration_ms": duration_ms,
                "model": response.model,
                "usage_prompt_tokens": (response.usage.input_tokens if response.usage else None),
                "usage_completion_tokens": (
                    response.usage.output_tokens if response.usage else None
                ),
                "response_length": len(content),
                "response_id": response.id,
            },
        )
        return ProviderResponse(
            message=content,
            response_id=response.id,
            input_tokens=response.usage.input_tokens if response.usage else None,
            output_tokens=response.usage.output_tokens if response.usage else None,
            duration_seconds=round(duration_ms / 1000, 2),
        )
