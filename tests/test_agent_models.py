import json

import httpx
from fastapi.testclient import TestClient

from app.agents.base import AgentContext
from app.agents.registry import build_registry
from app.config import Settings
from app.errors import LLMRateLimitError
from app.llm.base import ChatMessage, LLMRequest, ModelChoice
from app.llm.mock import MockProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.provider import FallbackProvider
from app.main import create_app
from app.services.search import NullSearchService

AGENT_MODELS = {
    "router": {"model": "small-model", "reasoning_effort": "low"},
    "coding_agent": {"model": "big-model", "reasoning_effort": "low"},
    "communication_agent": {"model": "fast-model"},
}


def capture_provider(effort="medium"):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAICompatibleProvider(api_key="k", model="default-model", base_url="https://llm.test/v1",
                                        reasoning_effort=effort, transport=httpx.MockTransport(handler))
    return provider, bodies


async def test_model_choice_overrides_model_and_reasoning_effort():
    provider, bodies = capture_provider()
    request = LLMRequest(system="s", messages=[ChatMessage(role="user", content="hi")])
    await provider.complete(request)
    await provider.complete(request.model_copy(update={"model_choice": ModelChoice(model="fast-model")}))
    await provider.complete(request.model_copy(update={
        "model_choice": ModelChoice(model="big-model", reasoning_effort="low")}))
    assert [(b["model"], b.get("reasoning_effort")) for b in bodies] == [
        ("default-model", "medium"),  # provider defaults
        ("fast-model", None),         # per-agent model without reasoning effort: none sent
        ("big-model", "low"),
    ]


async def test_registry_assigns_models_and_agents_send_them(trace):
    provider, bodies = capture_provider(effort=None)
    choices = {k: ModelChoice(**v) for k, v in AGENT_MODELS.items()}
    choices["safety_agent"] = ModelChoice(model="ignored")
    registry = build_registry(provider, NullSearchService(), agent_models=choices)
    assert registry.get("coding_agent").model_name == "big-model"
    assert registry.get("knowledge_agent").model_name == "default-model"
    assert registry.get("safety_agent").model_name is None  # rule-based, never calls the LLM
    await registry.get("communication_agent").run(AgentContext(request_id="r", message="rewrite this"), trace)
    assert bodies[-1]["model"] == "fast-model"


async def test_fallback_drops_primary_model_choice():
    backup = MockProvider(model="backup-model")
    request = LLMRequest(system="s", messages=[ChatMessage(role="user", content="hi")],
                         model_choice=ModelChoice(model="primary-only-model"))
    await FallbackProvider(MockProvider(fail_with=LLMRateLimitError("429")), backup).complete(request)
    assert backup.calls[0].model_choice is None


def test_agent_models_parsed_from_env_json(monkeypatch):
    monkeypatch.setenv("LLM_AGENT_MODELS", json.dumps(AGENT_MODELS))
    settings = Settings(_env_file=None)
    assert settings.llm_agent_models["router"] == ModelChoice(model="small-model", reasoning_effort="low")
    assert settings.llm_agent_models["communication_agent"].reasoning_effort is None


def test_health_and_agents_show_per_agent_models():
    settings = Settings(_env_file=None, llm_provider="openai_compatible", llm_api_key="k", llm_model="default-model",
                        llm_agent_models={**AGENT_MODELS, "typo_agent": {"model": "x"}})
    client = TestClient(create_app(settings))
    health = client.get("/health").json()
    assert health["router_model"] == "small-model"
    assert health["warnings"] == ["LLM_AGENT_MODELS: unknown agent 'typo_agent' ignored"]
    models = {a["name"]: a["model"] for a in client.get("/agents").json()}
    assert models == {"safety_agent": None, "coding_agent": "big-model", "knowledge_agent": "default-model",
                      "reasoning_agent": "default-model", "communication_agent": "fast-model",
                      "fact_check_agent": "default-model"}


def test_agent_models_are_ignored_in_mock_mode():
    settings = Settings(_env_file=None, llm_agent_models=AGENT_MODELS)
    client = TestClient(create_app(settings))
    assert client.get("/health").json()["router_model"] == "mock-model"
    assert {a["model"] for a in client.get("/agents").json()} == {None, "mock-model"}
