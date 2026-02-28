"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import time
from functools import lru_cache
from typing import Any, Literal

import boto3
from fastapi import APIRouter, FastAPI, HTTPException
from mangum import Mangum
from openai import OpenAI
from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()
router = APIRouter(prefix="/api")

SSM_PARAMETER_NAME = "/chat-app/openai-api-key"
AWS_REGION = "ap-northeast-1"


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Retrieve OpenAI API key from SSM Parameter Store and create client."""
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    response = ssm.get_parameter(Name=SSM_PARAMETER_NAME, WithDecryption=True)
    api_key = response["Parameter"]["Value"]
    return OpenAI(api_key=api_key)


ALLOWED_MODELS = {
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o4-mini",
}

ALLOWED_CONTENT_TYPES = {"input_text", "input_image", "input_file", "output_text"}

# 5 MB per file (base64 ≈ 4/3× original, so ~3.75 MB original)
MAX_FILE_DATA_LENGTH = 5 * 1024 * 1024


class ContentItem(BaseModel):
    type: str
    text: str | None = None
    image_url: str | None = None
    filename: str | None = None
    file_data: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_CONTENT_TYPES:
            msg = f"Unsupported content type: {v}"
            raise ValueError(msg)
        return v

    @field_validator("file_data")
    @classmethod
    def validate_file_data(cls, v: str | None) -> str | None:
        if v is not None and len(v) > MAX_FILE_DATA_LENGTH:
            msg = "File data exceeds maximum size (5 MB)"
            raise ValueError(msg)
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str | None) -> str | None:
        if v is not None:
            if not v.startswith("data:image/"):
                msg = "image_url must be a data:image/* URI"
                raise ValueError(msg)
            if len(v) > MAX_FILE_DATA_LENGTH:
                msg = "image_url data exceeds maximum size (5 MB)"
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_fields_per_type(self) -> "ContentItem":
        if self.type == "input_text" and not self.text:
            msg = "input_text requires 'text' field"
            raise ValueError(msg)
        if self.type == "input_image" and not self.image_url:
            msg = "input_image requires 'image_url' field"
            raise ValueError(msg)
        if self.type == "input_file" and not self.file_data:
            msg = "input_file requires 'file_data' field"
            raise ValueError(msg)
        return self


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[ContentItem]


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = "gpt-4o-mini"
    instructions: str | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in ALLOWED_MODELS:
            msg = f"Model not allowed: {v}. Allowed: {', '.join(sorted(ALLOWED_MODELS))}"
            raise ValueError(msg)
        return v


class ChatResponse(BaseModel):
    message: str


def build_input(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert messages to OpenAI Responses API input format."""
    result: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m.content, str):
            result.append({"role": m.role, "content": m.content})
        else:
            items = [item.model_dump(exclude_none=True) for item in m.content]
            result.append({"role": m.role, "content": items})
    return result


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI Responses API and return the assistant response."""
    message_count = len(request.messages)
    logger.info(
        "Chat request received",
        extra={"message_count": message_count, "model": request.model},
    )

    client = get_openai_client()
    try:
        start = time.time()
        kwargs: dict[str, Any] = {
            "model": request.model,
            "input": build_input(request.messages),
        }
        if request.instructions:
            kwargs["instructions"] = request.instructions

        response = client.responses.create(**kwargs)
        duration_ms = int((time.time() - start) * 1000)
        content = response.output_text

        logger.info(
            "Chat response generated",
            extra={
                "openai_duration_ms": duration_ms,
                "model": response.model,
                "usage_input_tokens": (response.usage.input_tokens if response.usage else None),
                "usage_output_tokens": (response.usage.output_tokens if response.usage else None),
                "response_length": len(content),
            },
        )
        return ChatResponse(message=content)
    except Exception as e:
        logger.exception("OpenAI API call failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


app.include_router(router)


handler = Mangum(app)
