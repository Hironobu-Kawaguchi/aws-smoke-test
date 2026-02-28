"""Shared constants and literal types for chat Lambda."""

import re
from typing import Literal

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
