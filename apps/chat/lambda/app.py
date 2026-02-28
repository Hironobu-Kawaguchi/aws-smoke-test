"""Chat API backend using FastAPI + Mangum for AWS Lambda."""

import logging
import time
from functools import lru_cache
from typing import Literal

import boto3
from fastapi import APIRouter, FastAPI, HTTPException
from mangum import Mangum
from openai import OpenAI
from pydantic import BaseModel, Field

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


class Message(BaseModel):
    role: str
    content: str


class Attachment(BaseModel):
    filename: str
    mime_type: str
    data_base64: str
    kind: Literal["image", "pdf"]


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = "gpt-4.1-mini"
    system_prompt: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)


class ChatResponse(BaseModel):
    message: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI API and return the assistant response."""
    message_count = len(request.messages)
    logger.info(
        "Chat request received",
        extra={
            "message_count": message_count,
            "model": request.model,
            "attachment_count": len(request.attachments),
        },
    )

    client = get_openai_client()
    try:
        start = time.time()
        input_messages: list[dict] = []
        for index, message in enumerate(request.messages):
            content_items: list[dict] = [{"type": "input_text", "text": message.content}]
            if index == len(request.messages) - 1:
                for attachment in request.attachments:
                    if attachment.kind == "image":
                        content_items.append(
                            {
                                "type": "input_image",
                                "image_url": f"data:{attachment.mime_type};base64,{attachment.data_base64}",
                            }
                        )
                    elif attachment.kind == "pdf":
                        content_items.append(
                            {
                                "type": "input_file",
                                "filename": attachment.filename,
                                "file_data": f"data:{attachment.mime_type};base64,{attachment.data_base64}",
                            }
                        )

            input_messages.append({"role": message.role, "content": content_items})

        response = client.responses.create(
            model=request.model,
            instructions=request.system_prompt or None,
            input=input_messages,
        )
        duration_ms = int((time.time() - start) * 1000)
        content = response.output_text or ""

        logger.info(
            "Chat response generated",
            extra={
                "openai_duration_ms": duration_ms,
                "model": response.model,
                "usage_input_tokens": response.usage.input_tokens if response.usage else None,
                "usage_output_tokens": response.usage.output_tokens if response.usage else None,
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
