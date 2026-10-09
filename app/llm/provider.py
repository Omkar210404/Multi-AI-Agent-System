"""Provider factory, retry wrapper and fallback wrapper. Switching provider is a configuration change, not a code change."""

import asyncio

from app.config import Settings
from app.errors import ConfigError, LLMAuthError, LLMError
from app.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.llm.mock import MockProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.services.logger import get_logger

log = get_logger("llm")

# With a backup provider available, don't wait longer than this for the primary to recover.
FAIL_FAST_SECONDS_WITH_FALLBACK = 2.0


class RetryingProvider(LLMProvider):
    """Retries retryable LLM errors (timeouts, rate limits, 5xx) with exponential backoff.

    `fail_fast_after`: if the required wait (e.g. a long Retry-After) exceeds this many seconds,
    give up immediately instead of sleeping — used when a fallback provider can answer sooner.
    """

    def __init__(self, inner: LLMProvider, max_retries: int = 2, base_delay: float = 1.0,
                 max_delay: float = 20.0, fail_fast_after: float | None = None):
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.fail_fast_after = fail_fast_after

    async def complete(self, request: LLMRequest) -> LLMResponse:
        attempt = 0
        while True:
            try:
                return await self.inner.complete(request)
            except LLMError as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                attempt += 1
                delay = self.base_delay * (2 ** (attempt - 1))
                retry_after = getattr(exc, "retry_after", None)
                if retry_after is not None:
                    delay = max(delay, retry_after)  # the provider says when capacity is back
                if self.fail_fast_after is not None and delay > self.fail_fast_after:
                    raise
                delay = min(delay, self.max_delay)
                log.warning(
                    "retrying LLM call",
                    extra={
                        "event": "llm_retry",
                        "attempt": attempt,
                        "error_type": exc.error_type,
                        "agent": request.metadata.get("agent"),
                    },
                )
                await asyncio.sleep(delay)

    async def aclose(self) -> None:
        await self.inner.aclose()


class FallbackProvider(LLMProvider):
    """Sends each request to the primary provider; if it fails, sends it to the backup provider.

    Auth errors are not hidden behind the fallback: a wrong primary key should be fixed, not masked.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            return await self.primary.complete(request)
        except LLMAuthError:
            raise
        except LLMError as exc:
            log.warning("primary provider failed, using fallback", extra={
                "event": "llm_fallback", "error_type": exc.error_type,
                "agent": request.metadata.get("agent"), "model": self.fallback.model})
            # Per-agent model names belong to the primary provider; the backup uses its own model.
            response = await self.fallback.complete(request.model_copy(update={"model_choice": None}))
            return response.model_copy(update={"fallback": True})

    async def aclose(self) -> None:
        await self.primary.aclose()
        await self.fallback.aclose()


def _build_fallback(settings: Settings) -> LLMProvider | None:
    if not settings.fallback_enabled:
        return None
    problems = settings.fallback_problems()
    if problems:
        log.warning("fallback provider disabled: " + "; ".join(problems),
                    extra={"event": "config_warning", "error_type": "config_error"})
        return None
    return OpenAICompatibleProvider(
        api_key=settings.llm_fallback_api_key.get_secret_value(),  # type: ignore[union-attr]
        model=settings.llm_fallback_model,
        base_url=settings.llm_fallback_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        reasoning_effort=settings.llm_fallback_reasoning_effort,
    )


def get_provider(settings: Settings) -> LLMProvider:
    problems = settings.config_problems()
    if problems:
        raise ConfigError("; ".join(problems))

    if settings.llm_provider == "mock":
        inner: LLMProvider = MockProvider(model=settings.llm_model)
    else:
        inner = OpenAICompatibleProvider(
            api_key=settings.llm_api_key.get_secret_value(),  # type: ignore[union-attr]
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            reasoning_effort=settings.llm_reasoning_effort,
        )

    fallback = _build_fallback(settings)
    if fallback is None:
        return RetryingProvider(inner, max_retries=settings.llm_max_retries)
    return FallbackProvider(
        RetryingProvider(inner, max_retries=settings.llm_max_retries,
                         fail_fast_after=FAIL_FAST_SECONDS_WITH_FALLBACK),
        RetryingProvider(fallback, max_retries=settings.llm_max_retries),
    )
