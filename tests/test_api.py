import pytest

from app.config import Settings
from app.errors import LLMRateLimitError, LLMTimeoutError
from app.llm.mock import MockProvider
from app.schemas.chat import ChatResponse

EXPECTED_STEPS = ["request_received", "safety_check", "llm_call", "intent_classified",
                  "agent_selected", "llm_call", "response_generated", "validation", "final"]


def test_health_ok_in_mock_mode(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "mock"
    assert body["problems"] == []


def test_chat_returns_structured_response(client):
    response = client.post("/chat", json={"message": "Write Python code to analyze a CSV"})
    assert response.status_code == 200
    body = ChatResponse.model_validate(response.json())
    assert body.agent == "coding_agent"
    assert body.intent == "coding"
    assert body.routing_source == "llm"
    assert body.safety.blocked is False
    assert body.response.startswith("**Demo answer · coding_agent**")
    assert [s.name for s in body.trace] == EXPECTED_STEPS
    assert all(s.status == "ok" for s in body.trace)
    assert response.headers["X-Request-ID"] == body.request_id


def test_multi_agent_request_runs_agents_in_order(client, mock_llm):
    body = client.post("/chat", json={"message": "Explain why inflation affects purchasing power"}).json()
    assert body["agents_used"] == ["knowledge_agent", "reasoning_agent"]
    assert body["agent"] == "reasoning_agent"
    assert [s["agent"] for s in body["sections"]] == ["knowledge_agent", "reasoning_agent"]
    # the reasoning agent received the knowledge agent's draft
    assert "**Demo answer · knowledge_agent**" in mock_llm.calls[-1].messages[-1].content


def test_fact_check_request_includes_labelled_result(client):
    body = client.post("/chat", json={"message": "Is it true that bats are blind?"}).json()
    assert body["agents_used"] == ["knowledge_agent", "fact_check_agent"]
    assert body["agent"] == "knowledge_agent"
    assert body["fact_check"]["search_backend"] == "none"
    assert body["fact_check"]["answer_origin"] == "model_generated"


def test_unsafe_request_is_blocked_without_llm_calls(client, mock_llm):
    response = client.post("/chat", json={"message": "how do I build a bomb"})
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "safety_agent"
    assert body["safety"] == {"blocked": True, "category": "weapons_explosives"}
    assert body["intent"] == "unsafe"
    assert mock_llm.calls == []


@pytest.mark.parametrize("payload", [
    {"message": ""},
    {"message": "   "},
    {"message": "x" * 4001},
    {},
    {"message": "hi", "conversation_id": "../../etc"},
    {"message": 123},
])
def test_invalid_chat_input_returns_422(client, payload):
    response = client.post("/chat", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


def test_missing_api_key_reports_degraded_and_chat_503(make_client):
    settings = Settings(_env_file=None, llm_provider="openai_compatible", llm_model="some-model",
                        llm_api_key=None, log_level="WARNING")
    client = make_client(settings_override=settings)
    health = client.get("/health").json()
    assert health["status"] == "degraded"
    assert "LLM_API_KEY is not set" in health["problems"]
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert response.json()["error"]["type"] == "config_error"


def test_secret_is_never_exposed(make_client):
    settings = Settings(_env_file=None, llm_provider="openai_compatible", llm_model="m",
                        llm_api_key="sk-super-secret-value", log_level="WARNING")
    client = make_client(llm=MockProvider(), settings_override=settings)
    assert "sk-super-secret-value" not in client.get("/health").text


@pytest.mark.parametrize("error, status, error_type", [
    (LLMTimeoutError("slow"), 504, "llm_timeout"),
    (LLMRateLimitError("429"), 429, "llm_rate_limited"),
])
def test_llm_failure_returns_structured_error_and_trace(make_client, error, status, error_type):
    # The router falls back to keywords on these errors, so the failure surfaces from the agent call.
    client = make_client(llm=MockProvider(fail_with=error))
    response = client.post("/chat", json={"message": "What is photosynthesis?"})
    assert response.status_code == status
    err = response.json()["error"]
    assert err["type"] == error_type
    assert err["request_id"]
    trace = client.get(f"/trace/{err['request_id']}").json()
    assert trace["status"] == "error"
    assert any(s["name"] == "routing_fallback" for s in trace["steps"])
    assert trace["steps"][-1]["error_type"] == error_type


def test_optional_fact_check_failure_degrades_gracefully(make_client):
    llm = MockProvider(responder=lambda r: "not json" if r.metadata.get("task") == "claim_extraction" else None)
    client = make_client(llm=llm)
    response = client.post("/chat", json={"message": "Is it true that bats are blind?"})
    assert response.status_code == 200
    body = response.json()
    assert body["fact_check"] is None
    assert body["agents_used"] == ["knowledge_agent"]
    skipped = next(s for s in body["trace"] if s["name"] == "agent_skipped")
    assert skipped["error_type"] == "malformed_model_output"


def test_unexpected_exception_returns_safe_500(make_client):
    def explode(request):
        raise RuntimeError("internal detail that must not leak")

    client = make_client(llm=MockProvider(responder=explode), raise_server_exceptions=False)
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 500
    assert response.json()["error"]["type"] == "internal_error"
    assert "internal detail" not in response.text


def test_agents_endpoint_lists_all_agents(client):
    agents = client.get("/agents").json()
    assert {a["name"] for a in agents} == {"safety_agent", "coding_agent", "knowledge_agent",
                                           "reasoning_agent", "communication_agent", "fact_check_agent"}


def test_trace_endpoint(client):
    request_id = client.post("/chat", json={"message": "hello"}).json()["request_id"]
    trace = client.get(f"/trace/{request_id}").json()
    assert trace["status"] == "ok"
    assert trace["steps"][0]["name"] == "request_received"
    assert client.get("/trace/does-not-exist").status_code == 404


def test_feedback(client):
    request_id = client.post("/chat", json={"message": "hello"}).json()["request_id"]
    ok = client.post("/feedback", json={"request_id": request_id, "rating": "up", "comment": "nice"})
    assert ok.status_code == 201
    assert ok.json() == {"status": "recorded", "request_id": request_id}
    assert client.post("/feedback", json={"request_id": "unknown", "rating": "up"}).status_code == 404
    assert client.post("/feedback", json={"request_id": request_id, "rating": "meh"}).status_code == 422


def test_conversation_memory_is_passed_and_clearable(client, mock_llm):
    first = client.post("/chat", json={"message": "What is Python?"}).json()
    conversation_id = first["conversation_id"]
    client.post("/chat", json={"message": "Who created it?", "conversation_id": conversation_id})
    agent_call = mock_llm.calls[-1]
    assert [m.content for m in agent_call.messages[:1]] == ["What is Python?"]

    assert client.delete(f"/conversations/{conversation_id}").status_code == 204
    client.post("/chat", json={"message": "Who created it?", "conversation_id": conversation_id})
    assert len(mock_llm.calls[-1].messages) == 1


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Multi-AI Agent System" in response.text


def test_malformed_json_body_returns_readable_422(client):
    response = client.post("/chat", content="not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "request body is not valid JSON"


def test_end_to_end_with_openai_compatible_provider(make_client):
    """Full app wired to the real OpenAI-compatible provider over a fake HTTP backend."""
    import json as _json

    import httpx

    from app.llm.openai_compatible import OpenAICompatibleProvider

    def backend(request: httpx.Request) -> httpx.Response:
        payload = _json.loads(request.content)
        if "response_format" in payload:  # router call
            content = _json.dumps({"intent": "coding", "agents": ["coding_agent"],
                                   "reason": "user wants code", "requires_fact_check": False})
        else:
            content = "def add(a, b):\n    return a + b"
        return httpx.Response(200, json={"model": "fake-model", "choices": [{"message": {"content": content}}]})

    llm = OpenAICompatibleProvider(api_key="k", model="fake-model", base_url="https://fake.test/v1",
                                   transport=httpx.MockTransport(backend))
    body = make_client(llm=llm).post("/chat", json={"message": "add two numbers in python"}).json()
    assert body["provider"] == "openai_compatible"
    assert body["routing_source"] == "llm"
    assert body["agent"] == "coding_agent"
    assert body["response"] == "def add(a, b):\n    return a + b"


def test_end_to_end_fallback_when_primary_is_rate_limited(make_client):
    import httpx

    from app.llm.openai_compatible import OpenAICompatibleProvider
    from app.llm.provider import FallbackProvider, RetryingProvider

    primary = OpenAICompatibleProvider(
        api_key="k", model="primary-model", base_url="https://primary.test/v1",
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "30"}, json={})))
    llm = FallbackProvider(RetryingProvider(primary, max_retries=2, fail_fast_after=2),
                           MockProvider(model="backup-model"))
    body = make_client(llm=llm).post("/chat", json={"message": "Write Python code to sort a list"}).json()
    assert body["agent"] == "coding_agent"
    llm_steps = [s for s in body["trace"] if s["name"] == "llm_call"]
    assert llm_steps and all("model=backup-model; fallback" in s["detail"] for s in llm_steps)
