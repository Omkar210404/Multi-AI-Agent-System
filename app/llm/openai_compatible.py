"""Provider for any OpenAI-compatible Chat Completions API (OpenAI, Groq, OpenRouter, Together, Ollama, ...)."""

import json
import time

import httpx

from app.errors import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    MalformedOutputError,
)
from app.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.services.logger import get_logger

log = get_logger("llm")


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        reasoning_effort: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def _build_payload(self, request: LLMRequest) -> dict:
        system = request.system
        if request.json_schema is not None:
            system += (
                "\n\nRespond with a single JSON object only, no prose, matching this JSON schema:\n"
                + json.dumps(request.json_schema)
            )
        choice = request.model_choice
        model = choice.model if choice else self.model
        effort = choice.reasoning_effort if choice else self.reasoning_effort
        payload: dict = {
            "model": model,
            "messages": [{"role": "system", "content": system}]
            + [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        if effort:
            # Supported by reasoning models (e.g. gpt-oss, o-series); lowers latency and token use.
            payload["reasoning_effort"] = effort
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        try:
            response = await self._client.post("/chat/completions", json=self._build_payload(request))
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"provider timeout: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"provider connection error: {type(exc).__name__}") from exc

        status = response.status_code
        if status >= 400:
            detail = f"provider returned HTTP {status}: {self._error_message(response)}"
            log.warning(detail, extra={"event": "llm_http_error", "status_code": status,
                                       "agent": request.metadata.get("agent")})
            if status in (401, 403):
                raise LLMAuthError(detail)
            if status == 429:
                raise LLMRateLimitError(detail, retry_after=self._retry_after(response))
            error = LLMProviderError(detail)
            # Other 4xx (bad model name, bad payload, failed JSON validation) won't succeed on retry.
            error.retryable = status >= 500
            raise error

        try:
            body = response.json()
            choice = body["choices"][0]
            text = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise MalformedOutputError("provider response missing choices[0].message.content") from exc
        if not isinstance(text, str) or not text.strip():
            raise MalformedOutputError("provider returned empty content")

        usage = body.get("usage") or None
        if usage:
            usage = {k: v for k, v in usage.items() if isinstance(v, int)}
        return LLMResponse(
            text=text,
            model=body.get("model") or (request.model_choice.model if request.model_choice else self.model),
            provider=self.name,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            usage=usage,
            finish_reason=choice.get("finish_reason"),
        )

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        try:
            return float(response.headers["retry-after"])
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        """Provider's own error text (truncated). Providers do not echo API keys in error bodies."""
        try:
            error = response.json().get("error")
            message = error.get("message") if isinstance(error, dict) else str(error)
        except (ValueError, AttributeError):
            message = response.text
        return (message or "no error message")[:200]

    async def aclose(self) -> None:
        await self._client.aclose()
