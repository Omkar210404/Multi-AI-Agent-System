import json

import pytest

from app.agents.base import AgentContext, BaseAgent
from app.agents.fact_check import FactCheckAgent
from app.agents.registry import AgentRegistry, build_registry
from app.errors import ConfigError, LLMTimeoutError, MalformedOutputError
from app.llm.mock import MockProvider
from app.schemas.chat import AgentOutput
from app.schemas.fact_check import FactCheckResult, Source
from app.services.search import NullSearchService, SearchService

EXPECTED_AGENTS = {"safety_agent", "coding_agent", "knowledge_agent", "reasoning_agent",
                   "communication_agent", "fact_check_agent"}


class FakeSearch(SearchService):
    name = "fake"

    async def search(self, query: str, limit: int = 2) -> list[Source]:
        if "Paris" in query:
            return [Source(title="Paris", url="https://example.org/Paris", snippet="capital of France")]
        return []


def test_registry_creates_all_agents_with_metadata():
    registry = build_registry(MockProvider(), NullSearchService())
    agents = registry.all()
    assert {a.name for a in agents} == EXPECTED_AGENTS
    for agent in agents:
        assert isinstance(agent, BaseAgent)
        assert agent.description and agent.intent
    assert "safety_agent" not in {a.name for a in registry.routable()}


def test_registry_rejects_duplicates():
    registry = AgentRegistry()
    agent = build_registry(MockProvider(), NullSearchService()).get("coding_agent")
    registry.register(agent)
    with pytest.raises(ValueError):
        registry.register(agent)


async def test_agent_run_calls_llm_with_agent_metadata_and_records_trace(trace):
    llm = MockProvider()
    agent = build_registry(llm, NullSearchService()).get("coding_agent")
    output = await agent.run(AgentContext(request_id="r1", message="write a function"), trace)
    assert output.agent == "coding_agent"
    assert output.content.startswith("**Demo answer · coding_agent**")
    assert llm.calls[0].metadata["agent"] == "coding_agent"
    assert "coding_agent" in llm.calls[0].system
    assert [s.name for s in trace.steps] == ["llm_call"]
    assert trace.steps[0].status == "ok"


async def test_agent_receives_history_and_prior_outputs(trace):
    llm = MockProvider()
    agent = build_registry(llm, NullSearchService()).get("reasoning_agent")
    ctx = AgentContext(
        request_id="r1", message="why?",
        prior_outputs=[AgentOutput(agent="knowledge_agent", content="DRAFT ANSWER")],
    )
    await agent.run(ctx, trace)
    sent = llm.calls[0].messages[-1].content
    assert "DRAFT ANSWER" in sent and "why?" in sent


async def test_agent_error_is_raised_and_traced(trace):
    llm = MockProvider(fail_with=LLMTimeoutError("slow"))
    agent = build_registry(llm, NullSearchService()).get("knowledge_agent")
    with pytest.raises(LLMTimeoutError):
        await agent.run(AgentContext(request_id="r1", message="hi"), trace)
    assert trace.steps[-1].status == "error"
    assert trace.steps[-1].error_type == "llm_timeout"


async def test_agent_without_provider_raises_config_error(trace):
    agent = build_registry(None, NullSearchService()).get("knowledge_agent")
    with pytest.raises(ConfigError):
        await agent.run(AgentContext(request_id="r1", message="hi"), trace)


async def test_fact_check_without_search_marks_claims_unverified(trace):
    llm = MockProvider(responses=[json.dumps({"claims": [{"claim": "Paris is the capital of France.", "search_query": "Paris capital"}]})])
    agent = FactCheckAgent(llm, NullSearchService())
    output = await agent.run(AgentContext(request_id="r1", message="x", prior_outputs=[
        AgentOutput(agent="knowledge_agent", content="Paris is the capital of France.")]), trace)
    result = FactCheckResult.model_validate(output.data)
    assert result.search_backend == "none"
    assert [c.status for c in result.claims] == ["unverified"]
    assert "No search backend" in result.notice
    assert llm.calls[0].messages[0].content == "Paris is the capital of France."


async def test_fact_check_with_search_separates_sourced_and_unverified(trace):
    llm = MockProvider(responses=[json.dumps({"claims": [
        {"claim": "Paris is the capital of France.", "search_query": "Paris France capital"},
        {"claim": "The moon is made of cheese.", "search_query": "Moon composition"}]})])
    agent = FactCheckAgent(llm, FakeSearch())
    output = await agent.run(AgentContext(request_id="r1", message="x"), trace)
    result = FactCheckResult.model_validate(output.data)
    assert [c.status for c in result.claims] == ["source_found", "unverified"]
    assert result.claims[0].sources[0].url == "https://example.org/Paris"
    assert "not proof" in result.notice


async def test_fact_check_malformed_output_raises(trace):
    agent = FactCheckAgent(MockProvider(malformed=True), NullSearchService())
    with pytest.raises(MalformedOutputError):
        await agent.run(AgentContext(request_id="r1", message="x"), trace)


async def test_truncated_output_is_labelled(trace):
    class TruncatingProvider(MockProvider):
        async def complete(self, request):
            response = await super().complete(request)
            return response.model_copy(update={"finish_reason": "length"})

    agent = build_registry(TruncatingProvider(), NullSearchService()).get("knowledge_agent")
    output = await agent.run(AgentContext(request_id="r1", message="hi"), trace)
    assert "cut off" in output.content
    assert any(s.name == "output_truncated" for s in trace.steps)


def test_coding_agent_gets_a_larger_token_budget():
    registry = build_registry(MockProvider(), NullSearchService(), max_tokens=800)
    assert registry.get("coding_agent").max_tokens == 2400
    assert registry.get("knowledge_agent").max_tokens == 800
