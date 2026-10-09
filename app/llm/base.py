"""Provider-agnostic LLM interface. The rest of the app depends only on this module."""

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ModelChoice(BaseModel):
    """Per-call model selection, used to give each agent its own model on the same provider."""

    model: str = Field(min_length=1)
    reasoning_effort: Literal["low", "medium", "high"] | None = None


class LLMRequest(BaseModel):
    system: str
    messages: list[ChatMessage]
    temperature: float = 0.3
    max_tokens: int = 800
    # When set, the caller expects a JSON object matching this schema.
    json_schema: dict[str, Any] | None = None
    # Overrides the provider's default model (and reasoning effort) for this call.
    model_choice: ModelChoice | None = None
    # Operational metadata only (agent name, request id) — used by logging and the mock.
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def last_user_message(self) -> str:
        for message in reversed(self.messages):
            if message.role == "user":
                return message.content
        return ""


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    latency_ms: float
    usage: dict[str, int] | None = None
    # "length" means the output was cut off at max_tokens.
    finish_reason: str | None = None
    # True when the backup provider answered because the primary failed.
    fallback: bool = False


class LLMProvider(ABC):
    """Every provider implements one async method. Errors must be raised as `app.errors.LLMError` subclasses."""

    name: str = "base"
    model: str = "unknown"

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None
