import json

import pytest

from app.agents.registry import build_registry
from app.errors import LLMAuthError, LLMProviderError
from app.llm.mock import MockProvider
from app.schemas.routing import RoutingDecision
from app.services.router import Router
from app.services.search import NullSearchService


def make_router(llm) -> Router:
    return Router(build_registry(llm, NullSearchService()), llm)


def decision(**kwargs) -> str:
    base = {"intent": "coding", "agents": ["coding_agent"], "reason": "r", "requires_fact_check": False}
    return json.dumps({**base, **kwargs})


async def test_llm_routing_decision_is_used(trace):
    router = make_router(MockProvider(responses=[decision()]))
    plan = await router.plan("anything", [], trace)
    assert plan.agents == ["coding_agent"]
    assert plan.routing_source == "llm"
    assert plan.intent == "coding"


@pytest.mark.parametrize("message, expected", [
    ("Write Python code to analyze a CSV file", ["coding_agent"]),
    ("Explain why inflation affects purchasing power", ["knowledge_agent", "reasoning_agent"]),
    ("Rewrite this email in a more formal tone", ["communication_agent"]),
    ("What is photosynthesis?", ["knowledge_agent"]),
])
async def test_mock_llm_routing_examples(trace, message, expected):
    plan = await make_router(MockProvider()).plan(message, [], trace)
    assert plan.agents == expected
    assert plan.routing_source == "llm"


async def test_agents_are_ordered_by_stage_and_fact_check_runs_last(trace):
    router = make_router(MockProvider(responses=[decision(
        intent="reasoning", agents=["fact_check_agent", "reasoning_agent", "knowledge_agent"])]))
    plan = await router.plan("x", [], trace)
    assert plan.agents == ["knowledge_agent", "reasoning_agent", "fact_check_agent"]


async def test_fact_check_only_gets_an_answering_agent_first(trace):
    router = make_router(MockProvider(responses=[decision(intent="fact_check", agents=["fact_check_agent"])]))
    plan = await router.plan("Is it true that the Great Wall is visible from space?", [], trace)
    assert plan.agents == ["knowledge_agent", "fact_check_agent"]


async def test_requires_fact_check_appends_fact_check_agent(trace):
    router = make_router(MockProvider(responses=[decision(
        intent="knowledge", agents=["knowledge_agent"], requires_fact_check=True)]))
    plan = await router.plan("x", [], trace)
    assert plan.agents == ["knowledge_agent", "fact_check_agent"]


async def test_unknown_and_unroutable_agents_are_filtered(trace):
    router = make_router(MockProvider(responses=[decision(agents=["hacker_agent", "safety_agent", "coding_agent"])]))
    plan = await router.plan("x", [], trace)
    assert plan.agents == ["coding_agent"]


async def test_only_unknown_agents_falls_back_to_keywords(trace):
    router = make_router(MockProvider(responses=[decision(agents=["made_up_agent"])]))
    plan = await router.plan("debug this python function", [], trace)
    assert plan.routing_source == "fallback"
    assert plan.agents == ["coding_agent"]
    assert any(s.name == "routing_fallback" for s in trace.steps)


async def test_malformed_router_output_falls_back(trace):
    router = make_router(MockProvider(malformed=True))
    plan = await router.plan("Translate this sentence to French", [], trace)
    assert plan.routing_source == "fallback"
    assert plan.agents == ["communication_agent"]
    fallback = next(s for s in trace.steps if s.name == "routing_fallback")
    assert fallback.error_type == "malformed_model_output"


async def test_provider_error_falls_back(trace):
    router = make_router(MockProvider(fail_with=LLMProviderError("500")))
    plan = await router.plan("hello there", [], trace)
    assert plan.routing_source == "fallback"
    assert plan.agents == ["knowledge_agent"]


async def test_auth_error_is_not_swallowed(trace):
    router = make_router(MockProvider(fail_with=LLMAuthError("401")))
    with pytest.raises(LLMAuthError):
        await router.plan("hello", [], trace)


def test_fallback_detects_fact_check_keywords():
    plan = make_router(MockProvider()).fallback("Is it true that bats are blind?")
    assert plan.agents[-1] == "fact_check_agent"
    assert plan.agents[0] == "knowledge_agent"


def test_router_prompt_lists_registry_agents():
    prompt = make_router(MockProvider()).router_prompt()
    for name in ["coding_agent", "knowledge_agent", "reasoning_agent", "communication_agent", "fact_check_agent"]:
        assert name in prompt
    assert "safety_agent" not in prompt


def test_routing_decision_schema_rejects_empty_agents():
    with pytest.raises(ValueError):
        RoutingDecision(intent="x", agents=[], reason="")
