import json

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.errors import (
    ConfigError,
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    MalformedOutputError,
)
from app.llm.base import ChatMessage, LLMRequest
from app.llm.mock import MockProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.provider import RetryingProvider, get_provider
from app.llm.structured import parse_model_output


def make_request(json_schema=None, **metadata) -> LLMRequest:
    return LLMRequest(
        system="sys",
        messages=[ChatMessage(role="user", content="hello")],
        json_schema=json_schema,
        metadata=metadata,
    )


def provider_with(handler) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="test-key", model="test-model", base_url="https://llm.test/v1",
        transport=httpx.MockTransport(handler),
    )


async def test_openai_compatible_success_sends_auth_and_parses_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "test-model",
            "choices": [{"message": {"content": "hi there"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        })

    response = await provider_with(handler).complete(make_request(json_schema={"type": "object"}))
    assert response.text == "hi there"
    assert response.usage == {"prompt_tokens": 3, "completion_tokens": 2}
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][0]["role"] == "system"


@pytest.mark.parametrize("status, error", [
    (401, LLMAuthError), (403, LLMAuthError), (429, LLMRateLimitError),
    (500, LLMProviderError), (503, LLMProviderError), (400, LLMProviderError),
])
async def test_openai_compatible_maps_http_errors(status, error):
    provider = provider_with(lambda request: httpx.Response(status, json={"error": "x"}))
    with pytest.raises(error):
        await provider.complete(make_request())


async def test_openai_compatible_client_error_is_not_retryable():
    provider = provider_with(lambda request: httpx.Response(400, json={}))
    with pytest.raises(LLMProviderError) as info:
        await provider.complete(make_request())
    assert info.value.retryable is False


async def test_openai_compatible_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMTimeoutError):
        await provider_with(handler).complete(make_request())


async def test_openai_compatible_malformed_body():
    provider = provider_with(lambda request: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(MalformedOutputError):
        await provider.complete(make_request())


async def test_retrying_provider_retries_then_succeeds():
    inner = MockProvider(fail_with=LLMRateLimitError("429"), fail_times=2)
    provider = RetryingProvider(inner, max_retries=2, base_delay=0)
    response = await provider.complete(make_request(agent="knowledge_agent"))
    assert response.text.startswith("**Demo answer")
    assert len(inner.calls) == 3


async def test_retrying_provider_gives_up_after_max_retries():
    inner = MockProvider(fail_with=LLMTimeoutError("slow"))
    provider = RetryingProvider(inner, max_retries=2, base_delay=0)
    with pytest.raises(LLMTimeoutError):
        await provider.complete(make_request())
    assert len(inner.calls) == 3


async def test_retrying_provider_does_not_retry_auth_errors():
    inner = MockProvider(fail_with=LLMAuthError("401"))
    provider = RetryingProvider(inner, max_retries=3, base_delay=0)
    with pytest.raises(LLMAuthError):
        await provider.complete(make_request())
    assert len(inner.calls) == 1


async def test_mock_structured_routing_output_is_valid_json():
    response = await MockProvider().complete(LLMRequest(
        system="route", messages=[ChatMessage(role="user", content="Write Python code to parse a CSV")],
        json_schema={"type": "object"}, metadata={"task": "routing"},
    ))
    data = json.loads(response.text)
    assert data["agents"][0] == "coding_agent"


def test_get_provider_missing_api_key_raises_config_error():
    settings = Settings(_env_file=None, llm_provider="openai_compatible", llm_model="gpt-x", llm_api_key=None)
    with pytest.raises(ConfigError) as info:
        get_provider(settings)
    assert "LLM_API_KEY" in str(info.value)


def test_get_provider_defaults_to_mock():
    provider = get_provider(Settings(_env_file=None))
    assert provider.name == "mock"


class _Model(BaseModel):
    value: int


@pytest.mark.parametrize("text", ['{"value": 1}', '```json\n{"value": 1}\n```', 'Here you go: {"value": 1} thanks'])
def test_parse_model_output_tolerates_wrapping(text):
    assert parse_model_output(text, _Model).value == 1


@pytest.mark.parametrize("text", ["not json at all", '{"value": "abc"}', "[1, 2]"])
def test_parse_model_output_rejects_bad_output(text):
    with pytest.raises(MalformedOutputError):
        parse_model_output(text, _Model)


async def test_rate_limit_error_carries_retry_after_header():
    provider = provider_with(lambda request: httpx.Response(429, headers={"retry-after": "7"}, json={}))
    with pytest.raises(LLMRateLimitError) as info:
        await provider.complete(make_request())
    assert info.value.retry_after == 7.0


async def test_retrying_provider_waits_for_retry_after(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("app.llm.provider.asyncio.sleep", fake_sleep)
    inner = MockProvider(fail_with=LLMRateLimitError("429", retry_after=5), fail_times=1)
    await RetryingProvider(inner, max_retries=2, base_delay=1, max_delay=20).complete(make_request())
    assert waits == [5]


async def test_reasoning_effort_is_sent_only_when_configured():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "length"}]})

    for effort in ("low", None):
        provider = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://llm.test/v1",
                                            reasoning_effort=effort, transport=httpx.MockTransport(handler))
        response = await provider.complete(make_request())
        assert response.finish_reason == "length"
    assert bodies[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in bodies[1]


def test_empty_reasoning_effort_env_value_means_unset(monkeypatch):
    monkeypatch.setenv("LLM_REASONING_EFFORT", "")
    assert Settings(_env_file=None).llm_reasoning_effort is None
