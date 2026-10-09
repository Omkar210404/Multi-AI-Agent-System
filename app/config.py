"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm.base import ModelChoice


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore",
                                      env_ignore_empty=True)

    # LLM provider
    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    llm_api_key: SecretStr | None = None
    llm_model: str = "mock-model"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_tokens: int = Field(default=1200, gt=0)
    # Optional, for reasoning models only (e.g. openai/gpt-oss-*). Leave unset for other models.
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = None
    # Optional per-agent models on the primary provider, as JSON, e.g.
    # {"router": {"model": "openai/gpt-oss-20b", "reasoning_effort": "low"}, "coding_agent": {"model": "..."}}
    # Agents not listed use LLM_MODEL.
    llm_agent_models: dict[str, ModelChoice] = Field(default_factory=dict)

    # Optional backup provider, used when the primary one is rate-limited or failing
    llm_fallback_provider: Literal["none", "openai_compatible"] = "none"
    llm_fallback_api_key: SecretStr | None = None
    llm_fallback_model: str = ""
    llm_fallback_base_url: str = ""
    llm_fallback_reasoning_effort: Literal["low", "medium", "high"] | None = None

    # Search backend used by the fact-checking agent
    search_provider: Literal["none", "wikipedia"] = "none"
    search_timeout_seconds: float = Field(default=8.0, gt=0)
    # Wikimedia requires a descriptive User-Agent with contact info (https://w.wiki/4wJS)
    search_user_agent: str = (
        "multi-ai-agent-system/0.1 (https://github.com/Omkar210404/Multi-AI-Agent-System; portfolio project)"
    )

    # Runtime limits
    memory_max_messages: int = Field(default=10, ge=0)
    trace_store_size: int = Field(default=500, gt=0)
    log_level: str = "INFO"

    @field_validator("llm_reasoning_effort", "llm_fallback_reasoning_effort", mode="before")
    @classmethod
    def empty_as_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def fallback_enabled(self) -> bool:
        return self.llm_provider != "mock" and self.llm_fallback_provider != "none"

    def fallback_problems(self) -> list[str]:
        """Problems with the optional backup provider. These disable the backup but don't block the app."""
        if not self.fallback_enabled:
            return []
        problems: list[str] = []
        if self.llm_fallback_api_key is None or not self.llm_fallback_api_key.get_secret_value().strip():
            problems.append("LLM_FALLBACK_API_KEY is not set")
        if not self.llm_fallback_model:
            problems.append("LLM_FALLBACK_MODEL is not set")
        if not self.llm_fallback_base_url:
            problems.append("LLM_FALLBACK_BASE_URL is not set")
        return problems

    def config_problems(self) -> list[str]:
        """Return human-readable configuration problems (never includes secret values)."""
        problems: list[str] = []
        if self.llm_provider != "mock":
            if self.llm_api_key is None or not self.llm_api_key.get_secret_value().strip():
                problems.append("LLM_API_KEY is not set")
            if not self.llm_model or self.llm_model == "mock-model":
                problems.append("LLM_MODEL is not set")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
