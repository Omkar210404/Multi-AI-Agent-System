import pytest

from app.config import Settings
from app.errors import LLMAuthError, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.llm.base import ChatMessage, LLMRequest
from app.llm.mock import MockProvider
from app.llm.provider import FallbackProvider, RetryingProvider, get_provider


def make_request() -> LLMRequest:
    return LLMRequest(system="s", messages=[ChatMessage(role="user", content="hi")], metadata={"agent": "knowledge_agent"})


@pytest.mark.parametrize("error", [LLMRateLimitError("429"), LLMTimeoutError("slow"), LLMProviderError("500")])
async def test_fallback_answers_when_primary_fails(error):
    primary, backup = MockProvider(fail_with=error), MockProvider(model="backup-model")
    response = await FallbackProvider(primary, backup).complete(make_request())
    assert response.fallback is True
    assert response.model == "backup-model"
    assert len(primary.calls) == 1 and len(backup.calls) == 1


async def test_primary_success_does_not_touch_fallback():
    backup = MockProvider()
    response = await FallbackProvider(MockProvider(), backup).complete(make_request())
    assert response.fallback is False
    assert backup.calls == []


async def test_auth_error_is_not_masked_by_fallback():
    backup = MockProvider()
    with pytest.raises(LLMAuthError):
        await FallbackProvider(MockProvider(fail_with=LLMAuthError("401")), backup).complete(make_request())
    assert backup.calls == []


async def test_both_failing_raises_fallback_error():
    provider = FallbackProvider(MockProvider(fail_with=LLMRateLimitError("429")),
                                MockProvider(fail_with=LLMTimeoutError("slow")))
    with pytest.raises(LLMTimeoutError):
        await provider.complete(make_request())


async def test_long_retry_after_fails_fast_so_fallback_can_answer(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("app.llm.provider.asyncio.sleep", fake_sleep)
    primary = RetryingProvider(MockProvider(fail_with=LLMRateLimitError("429", retry_after=30)),
                               max_retries=2, fail_fast_after=2)
    response = await FallbackProvider(primary, MockProvider()).complete(make_request())
    assert response.fallback is True
    assert waits == []  # did not sleep 30 s waiting for the primary


def _settings(**overrides) -> Settings:
    base = dict(_env_file=None, llm_provider="openai_compatible", llm_api_key="k", llm_model="m",
                llm_base_url="https://primary.test/v1", llm_fallback_provider="openai_compatible",
                llm_fallback_api_key="k2", llm_fallback_model="backup", llm_fallback_base_url="https://backup.test/v1")
    return Settings(**{**base, **overrides})


def test_get_provider_builds_fallback_chain():
    provider = get_provider(_settings())
    assert isinstance(provider, FallbackProvider)
    assert provider.fallback.model == "backup"


def test_misconfigured_fallback_is_disabled_with_warning_not_error():
    settings = _settings(llm_fallback_api_key=None)
    assert settings.fallback_problems() == ["LLM_FALLBACK_API_KEY is not set"]
    assert isinstance(get_provider(settings), RetryingProvider)


def test_health_reports_fallback_model_and_warnings(make_client):
    from app.main import create_app
    from fastapi.testclient import TestClient

    health = TestClient(create_app(_settings())).get("/health").json()
    assert health["fallback_model"] == "backup"
    assert health["warnings"] == []
    health = TestClient(create_app(_settings(llm_fallback_model=""))).get("/health").json()
    assert health["fallback_model"] is None
    assert health["warnings"] == ["backup provider disabled: LLM_FALLBACK_MODEL is not set"]
    assert "k2" not in str(health)
