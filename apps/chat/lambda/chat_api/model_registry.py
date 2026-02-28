"""Model capability registry."""

from dataclasses import dataclass

from .constants import REASONING_EFFORT_OPTIONS, Provider, ReasoningEffort


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
