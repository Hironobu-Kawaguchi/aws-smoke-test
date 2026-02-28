"""Pydantic schemas for chat API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import (
    ALLOWED_ATTACHMENT_MIME_TYPES,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    MAX_ATTACHMENT_BASE64_LENGTH,
    MAX_REQUEST_ATTACHMENT_BASE64_LENGTH,
    ReasoningEffort,
)
from .data_urls import parse_data_url
from .model_registry import ALLOWED_MODELS, MODEL_CAPABILITIES


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
        data_url_mime, payload = parse_data_url(self.data_url)
        if data_url_mime != self.mime_type:
            raise ValueError("mimeType must match dataUrl content type")
        if len(payload) > MAX_ATTACHMENT_BASE64_LENGTH:
            raise ValueError(
                "Attachment dataUrl is too large: "
                f"limit is {MAX_ATTACHMENT_BASE64_LENGTH} base64 chars"
            )
        return self

    def payload_size(self) -> int:
        _, payload = parse_data_url(self.data_url)
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

        # Gracefully disable unsupported features for Bedrock models.
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
