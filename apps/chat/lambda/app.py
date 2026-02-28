"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import time
from functools import lru_cache
from typing import Any

import boto3
from fastapi import APIRouter, FastAPI, HTTPException
from mangum import Mangum
from openai import OpenAI
from pydantic import BaseModel

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


class ContentItem(BaseModel):
    type: str
    text: str | None = None
    image_url: str | None = None
    filename: str | None = None
    file_data: str | None = None


class Message(BaseModel):
    role: str
    content: str | list[ContentItem]


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = "gpt-4o-mini"
    instructions: str | None = None


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
