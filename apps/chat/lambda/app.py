"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import os
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import boto3
from fastapi import APIRouter, FastAPI, HTTPException
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langsmith import traceable
from langsmith.run_trees import get_cached_client
from mangum import Mangum
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()
router = APIRouter(prefix="/api")

OPENAI_API_KEY_PARAMETER_NAME = "/chat-app/openai-api-key"
LANGSMITH_API_KEY_PARAMETER_NAME = "/chat-app/langsmith-api-key"
AWS_REGION = "ap-northeast-1"
LANGSMITH_PROJECT = "aws-smoke-test"
DEFAULT_MODEL = "gpt-4.1-mini"
IMAGE_ATTACHMENT_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PDF_ATTACHMENT_MIME_TYPE = "application/pdf"
ALLOWED_ATTACHMENT_MIME_TYPES = IMAGE_ATTACHMENT_MIME_TYPES | {PDF_ATTACHMENT_MIME_TYPE}
MAX_ATTACHMENT_BASE64_LENGTH = 2_800_000
MAX_REQUEST_ATTACHMENT_BASE64_LENGTH = 5_600_000
DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[-.\w+/]+);base64,(?P<payload>[A-Za-z0-9+/=]+)$")
DEFAULT_TEMPERATURE = 0.7
REASONING_EFFORT_OPTIONS = ("low", "medium", "high")

ReasoningEffort = Literal["low", "medium", "high"]
Provider = Literal["openai", "bedrock"]


@dataclass(frozen=True)
class ModelCapability:
    provider: Provider
    supports_temperature: bool
    supports_reasoning_effort: bool
    supports_web_search: bool = True
    supports_previous_response: bool = True
    reasoning_effort_options: tuple[ReasoningEffort, ...] = ()
    default_reasoning_effort: ReasoningEffort | None = None


MODEL_CAPABILITIES: dict[str, ModelCapability] = {
    # --- OpenAI models ---
    "gpt-4.1": ModelCapability(
        provider="openai", supports_temperature=True, supports_reasoning_effort=False
    ),
    "gpt-4.1-mini": ModelCapability(
        provider="openai", supports_temperature=True, supports_reasoning_effort=False
    ),
    "gpt-5": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-mini": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-nano": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-chat-latest": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5.2": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5.2-pro": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o4-mini": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o3-deep-research": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o4-mini-deep-research": ModelCapability(
        provider="openai",
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    # --- Bedrock (Claude) models ---
    "global.anthropic.claude-opus-4-6-v1": ModelCapability(
        provider="bedrock",
        supports_temperature=True,
        supports_reasoning_effort=False,
        supports_web_search=False,
        supports_previous_response=False,
    ),
    "global.anthropic.claude-sonnet-4-6": ModelCapability(
        provider="bedrock",
        supports_temperature=True,
        supports_reasoning_effort=False,
        supports_web_search=False,
        supports_previous_response=False,
    ),
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": ModelCapability(
        provider="bedrock",
        supports_temperature=True,
        supports_reasoning_effort=False,
        supports_web_search=False,
        supports_previous_response=False,
    ),
}
ALLOWED_MODELS = set(MODEL_CAPABILITIES)


def _parse_data_url(data_url: str) -> tuple[str, str]:
    match = DATA_URL_PATTERN.fullmatch(data_url)
    if not match:
        raise ValueError("dataUrl must be a base64 data URL")
    return match.group("mime"), match.group("payload")


@dataclass(frozen=True)
class ApiCredentials:
    openai_api_key: str
    langsmith_api_key: str | None


def _get_secure_parameter(ssm_client: Any, parameter_name: str) -> str:
    result = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
    value = result["Parameter"].get("Value")
    if not value:
        raise RuntimeError(f"SSM parameter {parameter_name} has no value")
    return value


def _get_optional_secure_parameter(ssm_client: Any, parameter_name: str) -> str | None:
    try:
        return _get_secure_parameter(ssm_client, parameter_name)
    except Exception:
        logger.warning(
            "Optional SSM parameter is unavailable; disabling dependent feature",
            extra={"parameter_name": parameter_name},
            exc_info=True,
        )
        return None


@lru_cache(maxsize=1)
def get_api_credentials() -> ApiCredentials:
    ssm_client = boto3.client("ssm", region_name=AWS_REGION)
    return ApiCredentials(
        openai_api_key=_get_secure_parameter(ssm_client, OPENAI_API_KEY_PARAMETER_NAME),
        langsmith_api_key=_get_optional_secure_parameter(
            ssm_client, LANGSMITH_API_KEY_PARAMETER_NAME
        ),
    )


def _configure_langsmith(langsmith_api_key: str | None) -> None:
    if not langsmith_api_key:
        os.environ.pop("LANGSMITH_TRACING", None)
        os.environ.pop("LANGSMITH_API_KEY", None)
        logger.info("LangSmith tracing disabled because API key is unavailable")
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)


def _flush_langsmith_traces() -> None:
    if os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        return
    if not os.environ.get("LANGSMITH_API_KEY"):
        return
    try:
        get_cached_client().flush()
    except Exception:
        logger.warning("Failed to flush LangSmith traces", exc_info=True)


@lru_cache(maxsize=1)
def _ensure_langsmith_configured() -> None:
    """Configure LangSmith environment variables (called once via lru_cache)."""
    credentials = get_api_credentials()
    _configure_langsmith(credentials.langsmith_api_key)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Create an OpenAI client with LangSmith tracing configuration."""
    _ensure_langsmith_configured()
    credentials = get_api_credentials()
    return OpenAI(api_key=credentials.openai_api_key)


@traceable(run_type="llm", name="openai.responses.create")
def _invoke_openai_responses(request_params: dict[str, Any]) -> Any:
    client = get_openai_client()
    return client.responses.create(**request_params)


@lru_cache(maxsize=1)
def get_chat_responses_runnable() -> Runnable[dict[str, Any], Any]:
    return RunnableLambda(_invoke_openai_responses).with_config(
        {"run_name": "chat_lambda_openai_responses"}
    )


def _build_langchain_messages(
    messages: list["Message"],
    system_prompt: str | None,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """Convert internal Message objects to LangChain message format for Bedrock."""
    lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []

    if system_prompt:
        lc_messages.append(SystemMessage(content=system_prompt))

    for msg in messages:
        if msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
            continue

        # Build content parts for user messages
        parts: list[str | dict[str, Any]] = []
        if msg.content.strip():
            parts.append({"type": "text", "text": msg.content})

        for attachment in msg.attachments:
            _, payload = _parse_data_url(attachment.data_url)
            if attachment.mime_type in IMAGE_ATTACHMENT_MIME_TYPES:
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": attachment.mime_type,
                            "data": payload,
                        },
                    }
                )
            elif attachment.mime_type == PDF_ATTACHMENT_MIME_TYPE:
                parts.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": payload,
                        },
                    }
                )

        lc_messages.append(HumanMessage(content=parts or msg.content))

    return lc_messages


def _invoke_bedrock_converse(params: dict[str, Any]) -> AIMessage:
    model = ChatBedrockConverse(
        model=params["model_id"],
        region_name=AWS_REGION,
        max_tokens=params["max_tokens"],
        **({"temperature": params["temperature"]} if "temperature" in params else {}),
    )
    return model.invoke(params["messages"])


@lru_cache(maxsize=1)
def get_bedrock_runnable() -> Runnable[dict[str, Any], AIMessage]:
    return RunnableLambda(_invoke_bedrock_converse).with_config(
        {"run_name": "chat_lambda_bedrock_converse"}
    )


class Attachment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    mime_type: str = Field(alias="mimeType")
    data_url: str = Field(alias="dataUrl")

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, mime_type: str) -> str:
        if mime_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise ValueError(f"Unsupported attachment mimeType: {mime_type}")
        return mime_type

    @model_validator(mode="after")
    def validate_data_url(self) -> "Attachment":
        data_url_mime, payload = _parse_data_url(self.data_url)
        if data_url_mime != self.mime_type:
            raise ValueError("mimeType must match dataUrl content type")
        if len(payload) > MAX_ATTACHMENT_BASE64_LENGTH:
            raise ValueError(
                "Attachment dataUrl is too large: "
                f"limit is {MAX_ATTACHMENT_BASE64_LENGTH} base64 chars"
            )
        return self

    def payload_size(self) -> int:
        _, payload = _parse_data_url(self.data_url)
        return len(payload)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    attachments: list[Attachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_attachments(self) -> "Message":
        if self.attachments and self.role != "user":
            raise ValueError("Attachments are only supported for user messages")
        return self


class ModelMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    supports_temperature: bool = Field(alias="supportsTemperature")
    supports_reasoning_effort: bool = Field(alias="supportsReasoningEffort")
    reasoning_effort_options: list[ReasoningEffort] = Field(alias="reasoningEffortOptions")
    default_reasoning_effort: ReasoningEffort | None = Field(
        default=None, alias="defaultReasoningEffort"
    )
    supports_web_search: bool = Field(default=True, alias="supportsWebSearch")
    supports_previous_response: bool = Field(default=True, alias="supportsPreviousResponse")


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    messages: list[Message]
    model: str = DEFAULT_MODEL
    system_prompt: str | None = Field(default=None, alias="systemPrompt")
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: ReasoningEffort | None = Field(default=None, alias="reasoningEffort")
    web_search_enabled: bool = Field(default=True, alias="webSearchEnabled")
    max_output_tokens: int = Field(default=1000, alias="maxOutputTokens", ge=1, le=4096)
    previous_response_id: str | None = Field(default=None, alias="previousResponseId")

    @field_validator("model")
    @classmethod
    def validate_model(cls, model: str) -> str:
        if model not in ALLOWED_MODELS:
            raise ValueError(
                f"Unsupported model: {model}. Allowed models: {', '.join(sorted(ALLOWED_MODELS))}"
            )
        return model

    @model_validator(mode="after")
    def validate_model_parameters(self) -> "ChatRequest":
        capability = MODEL_CAPABILITIES[self.model]

        if capability.supports_temperature:
            if self.temperature is None:
                self.temperature = DEFAULT_TEMPERATURE
        elif self.temperature is not None:
            raise ValueError(f"temperature is not supported for model: {self.model}")

        if capability.supports_reasoning_effort:
            if self.reasoning_effort is None:
                self.reasoning_effort = capability.default_reasoning_effort
            elif self.reasoning_effort not in capability.reasoning_effort_options:
                options = ", ".join(capability.reasoning_effort_options)
                raise ValueError(
                    f"Invalid reasoningEffort for model {self.model}: {self.reasoning_effort}. "
                    f"Supported options: {options}"
                )
        elif self.reasoning_effort is not None:
            raise ValueError(f"reasoningEffort is not supported for model: {self.model}")

        # Gracefully disable unsupported features for Bedrock models
        if not capability.supports_web_search:
            self.web_search_enabled = False
        if not capability.supports_previous_response:
            self.previous_response_id = None

        return self

    @model_validator(mode="after")
    def validate_total_request_attachment_size(self) -> "ChatRequest":
        total_payload_size = sum(
            attachment.payload_size()
            for message in self.messages
            for attachment in message.attachments
        )
        if total_payload_size > MAX_REQUEST_ATTACHMENT_BASE64_LENGTH:
            raise ValueError(
                "Total request attachment payload is too large: "
                f"limit is {MAX_REQUEST_ATTACHMENT_BASE64_LENGTH} base64 chars"
            )
        return self


class ChatResponse(BaseModel):
    message: str
    response_id: str = Field(serialization_alias="responseId")
    input_tokens: int | None = Field(default=None, serialization_alias="inputTokens")
    output_tokens: int | None = Field(default=None, serialization_alias="outputTokens")
    duration_seconds: float = Field(serialization_alias="durationSeconds")


def _build_content_parts(message: Message) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if message.content.strip():
        parts.append({"type": "input_text", "text": message.content})

    for attachment in message.attachments:
        if attachment.mime_type in IMAGE_ATTACHMENT_MIME_TYPES:
            parts.append({"type": "input_image", "image_url": attachment.data_url})
        elif attachment.mime_type == PDF_ATTACHMENT_MIME_TYPE:
            parts.append(
                {
                    "type": "input_file",
                    "filename": attachment.name,
                    "file_data": attachment.data_url,
                }
            )
        else:
            logger.warning(
                "Unsupported attachment mime_type",
                extra={"mime_type": attachment.mime_type, "attachment_name": attachment.name},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment mimeType: {attachment.mime_type}",
            )
    return parts


@router.get("/models", response_model=list[ModelMetadata])
def models() -> list[ModelMetadata]:
    """List web-search capable models and their configurable parameters."""
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


def _handle_openai_chat(
    request: ChatRequest, capability: ModelCapability, message_count: int
) -> ChatResponse:
    """Handle chat request via OpenAI Responses API."""
    input_messages = []
    for message in request.messages:
        content_parts = _build_content_parts(message)
        if content_parts:
            input_messages.append({"role": message.role, "content": content_parts})

    get_openai_client()
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

    response = get_chat_responses_runnable().invoke(
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
            "usage_completion_tokens": (response.usage.output_tokens if response.usage else None),
            "response_length": len(content),
            "response_id": response.id,
        },
    )
    return ChatResponse(
        message=content,
        response_id=response.id,
        input_tokens=response.usage.input_tokens if response.usage else None,
        output_tokens=response.usage.output_tokens if response.usage else None,
        duration_seconds=round(duration_ms / 1000, 2),
    )


def _handle_bedrock_chat(
    request: ChatRequest, capability: ModelCapability, message_count: int
) -> ChatResponse:
    """Handle chat request via Amazon Bedrock Converse API."""
    lc_messages = _build_langchain_messages(request.messages, request.system_prompt)

    start = time.time()
    params: dict[str, Any] = {
        "model_id": request.model,
        "messages": lc_messages,
        "max_tokens": request.max_output_tokens,
    }
    if capability.supports_temperature and request.temperature is not None:
        params["temperature"] = request.temperature

    response = get_bedrock_runnable().invoke(
        params,
        config={
            "run_name": "chat_lambda_request",
            "tags": ["chat-api", request.model],
            "metadata": {"message_count": message_count},
        },
    )
    duration_ms = int((time.time() - start) * 1000)

    # Extract text content from AIMessage
    content = ""
    if isinstance(response.content, str):
        content = response.content
    elif isinstance(response.content, list):
        content = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )

    # Extract usage metadata
    usage = response.usage_metadata
    input_tokens = usage.get("input_tokens") if usage else None
    output_tokens = usage.get("output_tokens") if usage else None

    # Extract request ID for response_id
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
    return ChatResponse(
        message=content,
        response_id=request_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_seconds=round(duration_ms / 1000, 2),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI or Bedrock and return the assistant response."""
    message_count = len(request.messages)
    logger.info("Chat request received", extra={"message_count": message_count})

    _ensure_langsmith_configured()
    capability = MODEL_CAPABILITIES[request.model]

    try:
        if capability.provider == "openai":
            return _handle_openai_chat(request, capability, message_count)
        return _handle_bedrock_chat(request, capability, message_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("API call failed", extra={"provider": capability.provider})
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        _flush_langsmith_traces()


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)


handler = Mangum(app)
