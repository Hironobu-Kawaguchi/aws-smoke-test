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
DEFAULT_MODEL = "gpt-4.1-mini"


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Retrieve OpenAI API key from SSM Parameter Store and create client."""
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    response = ssm.get_parameter(Name=SSM_PARAMETER_NAME, WithDecryption=True)
    api_key = response["Parameter"]["Value"]
    return OpenAI(api_key=api_key)


class Attachment(BaseModel):
    filename: str
    mimeType: str
    dataBase64: str


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = ""
    attachments: list[Attachment] = Field(default_factory=list)


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str = DEFAULT_MODEL
    systemPrompt: str = ""
    temperature: float = 0.7


class ChatResponse(BaseModel):
    message: str


def _to_response_input(message: Message) -> dict:
    contents: list[dict] = []

    if message.content:
        contents.append({"type": "input_text", "text": message.content})

    for attachment in message.attachments:
        data_url = f"data:{attachment.mimeType};base64,{attachment.dataBase64}"
        if attachment.mimeType.startswith("image/"):
            contents.append({"type": "input_image", "image_url": data_url})
        elif attachment.mimeType == "application/pdf":
            contents.append(
                {
                    "type": "input_file",
                    "filename": attachment.filename,
                    "file_data": data_url,
                }
            )

    if not contents:
        contents.append({"type": "input_text", "text": ""})

    return {
        "role": message.role,
        "content": contents,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Send messages to OpenAI Responses API and return the assistant response."""
    message_count = len(request.messages)
    logger.info("Chat request received", extra={"message_count": message_count})

    client = get_openai_client()
    try:
        start = time.time()
        response = client.responses.create(
            model=request.model,
            temperature=request.temperature,
            input=[_to_response_input(message) for message in request.messages],
            instructions=request.systemPrompt or None,
        )
        duration_ms = int((time.time() - start) * 1000)
        content = response.output_text

        logger.info(
            "Chat response generated",
            extra={
                "openai_duration_ms": duration_ms,
                "model": response.model,
                "usage_prompt_tokens": (
                    response.usage.input_tokens if response.usage else None
                ),
                "usage_completion_tokens": (
                    response.usage.output_tokens if response.usage else None
                ),
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
