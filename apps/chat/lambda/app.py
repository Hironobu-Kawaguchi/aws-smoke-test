"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import os
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from mangum import Mangum

from chat_api.errors import BadRequestError
from chat_api.infra.runtime import (
    ensure_langsmith_configured,
    flush_langsmith_traces,
    get_bedrock_runnable,
    get_chat_responses_runnable,
    get_openai_client,
)
from chat_api.model_registry import MODEL_CAPABILITIES
from chat_api.orchestration.base import ChatOrchestrator
from chat_api.orchestration.direct import DirectChatOrchestrator
from chat_api.orchestration.langgraph_flow import LangGraphChatOrchestrator
from chat_api.providers.bedrock_provider import BedrockChatProvider
from chat_api.providers.openai_provider import OpenAIChatProvider
from chat_api.schemas import ChatRequest, ChatResponse, ModelMetadata
from chat_api.services.chat_service import ChatService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()
router = APIRouter(prefix="/api")

OrchestratorKind = Literal["direct", "langgraph"]


def _resolve_orchestrator_kind() -> OrchestratorKind:
    value = os.environ.get("CHAT_ORCHESTRATOR", "direct").strip().lower()
    if value in {"direct", "langgraph"}:
        return value

    logger.warning(
        "Unsupported CHAT_ORCHESTRATOR value; falling back to direct",
        extra={"orchestrator": value},
    )
    return "direct"


def _build_orchestrator() -> ChatOrchestrator:
    providers = {
        "openai": OpenAIChatProvider(
            get_openai_client=get_openai_client,
            get_chat_responses_runnable=get_chat_responses_runnable,
        ),
        "bedrock": BedrockChatProvider(get_bedrock_runnable=get_bedrock_runnable),
    }
    if _resolve_orchestrator_kind() == "langgraph":
        return LangGraphChatOrchestrator(providers=providers)
    return DirectChatOrchestrator(providers=providers)


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    orchestrator = _build_orchestrator()
    return ChatService(model_capabilities=MODEL_CAPABILITIES, orchestrator=orchestrator)


@router.get("/models", response_model=list[ModelMetadata])
def models() -> list[ModelMetadata]:
    """List models and their configurable parameters."""
    return [
        ModelMetadata(
            id=model,
            supportsTemperature=capability.supports_temperature,
            supportsReasoningEffort=capability.supports_reasoning_effort,
            reasoningEffortOptions=list(capability.reasoning_effort_options),
            defaultReasoningEffort=capability.default_reasoning_effort,
            supportsWebSearch=capability.supports_web_search,
            supportsPreviousResponse=capability.supports_previous_response,
        )
        for model, capability in MODEL_CAPABILITIES.items()
    ]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI or Bedrock and return the assistant response."""
    capability = MODEL_CAPABILITIES.get(request.model)

    try:
        ensure_langsmith_configured()
        return get_chat_service().handle_chat(request)
    except BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "API call failed",
            extra={"provider": capability.provider if capability else "unknown"},
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        flush_langsmith_traces()


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)


handler = Mangum(app)
