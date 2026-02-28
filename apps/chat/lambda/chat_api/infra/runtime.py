"""Runtime infrastructure helpers for credentials, tracing, and provider runnables."""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langsmith import traceable
from langsmith.run_trees import get_cached_client
from openai import OpenAI

from chat_api.constants import (
    AWS_REGION,
    LANGSMITH_API_KEY_PARAMETER_NAME,
    LANGSMITH_PROJECT,
    OPENAI_API_KEY_PARAMETER_NAME,
)

logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def ensure_langsmith_configured() -> None:
    """Configure LangSmith environment variables (called once via lru_cache)."""
    credentials = get_api_credentials()
    _configure_langsmith(credentials.langsmith_api_key)


def flush_langsmith_traces() -> None:
    if os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        return
    if not os.environ.get("LANGSMITH_API_KEY"):
        return
    try:
        get_cached_client().flush()
    except Exception:
        logger.warning("Failed to flush LangSmith traces", exc_info=True)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Create an OpenAI client with LangSmith tracing configuration."""
    ensure_langsmith_configured()
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
