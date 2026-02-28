"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import boto3
from fastapi import APIRouter, FastAPI, HTTPException
from mangum import Mangum
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()
router = APIRouter(prefix="/api")

SSM_PARAMETER_NAME = "/chat-app/openai-api-key"
AWS_REGION = "ap-northeast-1"
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


@dataclass(frozen=True)
class ModelCapability:
    supports_temperature: bool
    supports_reasoning_effort: bool
    reasoning_effort_options: tuple[ReasoningEffort, ...] = ()
    default_reasoning_effort: ReasoningEffort | None = None


# Web search-compatible models in the Responses API.
MODEL_CAPABILITIES: dict[str, ModelCapability] = {
    "gpt-4.1": ModelCapability(supports_temperature=True, supports_reasoning_effort=False),
    "gpt-4.1-mini": ModelCapability(supports_temperature=True, supports_reasoning_effort=False),
    "gpt-5": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-mini": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-nano": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5-chat-latest": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5.2": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "gpt-5.2-pro": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o4-mini": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o3-deep-research": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
    "o4-mini-deep-research": ModelCapability(
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_options=REASONING_EFFORT_OPTIONS,
        default_reasoning_effort="low",
    ),
}
ALLOWED_MODELS = set(MODEL_CAPABILITIES)


def _parse_data_url(data_url: str) -> tuple[str, str]:
    match = DATA_URL_PATTERN.fullmatch(data_url)
    if not match:
        raise ValueError("dataUrl must be a base64 data URL")
    return match.group("mime"), match.group("payload")


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Retrieve OpenAI API key from SSM Parameter Store and create client."""
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    result = ssm.get_parameter(Name=SSM_PARAMETER_NAME, WithDecryption=True)
    api_key = result["Parameter"].get("Value")
    if not api_key:
        raise RuntimeError(f"SSM parameter {SSM_PARAMETER_NAME} has no value")
    return OpenAI(api_key=api_key)


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
        )
        for model, capability in MODEL_CAPABILITIES.items()
    ]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI Responses API and return the assistant response."""
    message_count = len(request.messages)
    logger.info("Chat request received", extra={"message_count": message_count})

    input_messages = []
    for message in request.messages:
        content_parts = _build_content_parts(message)
        if content_parts:
            input_messages.append({"role": message.role, "content": content_parts})

    client = get_openai_client()
    try:
        start = time.time()
        capability = MODEL_CAPABILITIES[request.model]
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

        response = client.responses.create(**request_params)
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
        return ChatResponse(
            message=content,
            response_id=response.id,
            input_tokens=response.usage.input_tokens if response.usage else None,
            output_tokens=response.usage.output_tokens if response.usage else None,
            duration_seconds=round(duration_ms / 1000, 2),
        )
    except Exception as e:
        logger.exception("OpenAI API call failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)


handler = Mangum(app)
