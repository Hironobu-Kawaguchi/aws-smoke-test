"""Conversion helpers between API messages and provider-specific formats."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .constants import IMAGE_ATTACHMENT_MIME_TYPES, PDF_ATTACHMENT_MIME_TYPE
from .data_urls import parse_data_url
from .errors import BadRequestError
from .schemas import Message


def build_bedrock_messages(
    messages: list[Message],
    system_prompt: str | None,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """Convert internal Message objects to LangChain message format for Bedrock."""
    lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []

    if system_prompt:
        lc_messages.append(SystemMessage(content=system_prompt))

    for message in messages:
        if message.role == "assistant":
            lc_messages.append(AIMessage(content=message.content))
            continue

        parts: list[str | dict[str, Any]] = []
        if message.content.strip():
            parts.append({"type": "text", "text": message.content})

        for attachment in message.attachments:
            _, payload = parse_data_url(attachment.data_url)
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
                            "media_type": PDF_ATTACHMENT_MIME_TYPE,
                            "data": payload,
                        },
                    }
                )

        lc_messages.append(HumanMessage(content=parts or message.content))

    return lc_messages


def build_openai_content_parts(message: Message) -> list[dict[str, Any]]:
    """Build OpenAI Responses API content parts from an internal Message."""
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
            raise BadRequestError(f"Unsupported attachment mimeType: {attachment.mime_type}")

    return parts
