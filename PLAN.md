# PLAN — Multi-AI Agent System

Status: **approved and implemented** (2026-10-09). Decisions taken: D1 plain HTML/CSS/JS UI; D2 tested with a real model (Groq `openai/gpt-oss-120b`) plus an optional backup provider (Gemini); D3 optional Wikipedia search backend added. The README is the up-to-date description; this file records the original plan.

## 1. Environment (inspected 2026-10-09)

| Item | Finding | Consequence |
|---|---|---|
| Python | 3.11.9 (Microsoft Store build) | Meets 3.11+. Use a project `.venv`. |
| Global packages | fastapi 0.95, **pydantic 1.10**, uvicorn 0.22 | Too old (Pydantic v1). Ignore them and install current versions into `.venv`. |
| Node / npm | 22.16 / 10.9 | React+Vite is possible (see decision D1). |
| git | 2.49, global identity configured | Repo initialised in `multi-ai-agent-system/` on `main`. |
| Docker | **not installed** | I can write the Dockerfile and compose file but can't build or run them here. |
| Internet | PyPI and npm reachable | Dependencies can be installed. |
| LLM keys | none in env, no local Ollama | All development and tests run on the mock provider. Testing a real provider needs a key from you (D2). |
| GPU | RTX 3050 Laptop | Not needed. The project makes no local model calls. |

## 2. Architecture

```
Browser UI ──HTTP──▶ FastAPI (api/routes.py)
                        │  request_id + TraceRecorder created per request
                        ▼
                   Orchestrator
   1. SafetyAgent.check(message)  ── unsafe ──▶ structured refusal (no LLM call to other agents)
   2. Router.decide(message, history) ──▶ RoutingDecision (Pydantic)
         • LLM classification with JSON output, validated against the schema + agent registry
         • fallback: rule-based scorer over each agent's declared keywords (if LLM output malformed)
   3. ExecutionPlan: ordered agents, e.g. [knowledge, reasoning] (+ fact_check if requires_fact_check)
   4. Run agents sequentially; each gets the message, recent memory, and prior agents' outputs
   5. Combine into ChatResponse (final answer + per-agent sections + fact-check block)
                        │
        ┌───────────────┼────────────────┬──────────────┐
        ▼               ▼                ▼              ▼
   LLMProvider     ConversationMemory  TraceStore   SearchService
   (mock | openai-  (in-process, last  (bounded,    (interface; Null impl
    compatible)      N msgs per conv)   in-memory)   by default → "unverified")
```

**Key design choices**
- **Agent registry, not if/else.** Each agent subclasses `BaseAgent` and declares `name`, `description`, `system_prompt`, and `routing_keywords`. The registry produces the router's prompt (the list of available agents) and the fallback scorer's keyword table. A new agent is one new file plus one registry line.
- **The router's output is untrusted.** It's parsed into `RoutingDecision`. Unknown agent names are dropped, an empty agent list falls back to `knowledge_agent`, and the fallback is recorded in the trace.
- **Safety runs first, as rules.** Regex/keyword categories: weapons/explosives, malware, self-harm, sexual content involving minors, violent harm. Self-harm gets a supportive response that points to help resources, not a flat refusal. The Coding agent writes code but **never executes it**.
- **Fact-checking is labeled honestly.** `FactCheckResult` keeps three lists apart: `model_generated`, `sourced` (each with a URL), and `unverified`. With no search backend configured (the default), every claim lands in `unverified` with an explicit notice. No citations are invented.
- **Trace = operational metadata only.** Each step records name, agent, status, started_at, duration_ms and error_type. It stores no prompts, no model reasoning and no secrets. Steps: received → safety_check → intent_classified → agent_selected → llm_call (per agent) → response_generated → validation → final.
- **Errors map to a typed hierarchy:** `ConfigError`, `LLMAuthError`, `LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError`, `MalformedOutputError`. Timeouts, 429s and 5xx responses are retried with exponential backoff (bounded). FastAPI handlers turn every error into `{"error": {"type", "message", "request_id"}}` with the right status code (400/422/429/502/503/504/500). Stack traces and keys never reach the client.
- **Logging:** stdlib `logging` with a JSON formatter and a `request_id` held in a contextvar. Each log line records the event, agent, duration, status and error type. Message bodies and keys are never logged; only message length is.
- **Config:** `pydantic-settings`. A missing key with a real provider does **not** crash startup: `/health` reports `degraded` and `/chat` returns a 503 `ConfigError`.

## 3. Mock LLM provider (how it works)

`LLMProvider` (ABC in `llm/base.py`):
```python
async def complete(self, request: LLMRequest) -> LLMResponse
# LLMRequest: system, messages, temperature, max_tokens, json_schema | None, metadata{agent, request_id}
# LLMResponse: text, model, provider, latency_ms, usage | None
```
Implementations in `llm/`:
- **`MockProvider`**: deterministic, makes no network calls, and is the default (`LLM_PROVIDER=mock`).
  - When `json_schema` is set (router, fact-check claim extraction), it returns **valid JSON** built from simple keyword heuristics on the last user message. This exercises the real parse and validate path.
  - For free-text agent calls, it returns templated text tagged by agent, e.g. `"[mock · coding_agent] Here is a sketch…"`. Mock output is therefore always visibly labeled as mock, in the API and in the UI (a "mock mode" badge, plus `provider: "mock"` in `/health`).
  - **Test hooks**, set in the constructor and never in production config: a `responses` queue or `responder` callable to script outputs; `fail_with=<exception>` to inject timeout, rate-limit or provider errors; `malformed=True` to return broken JSON; `latency_ms`; and a `calls` list recording each request, so tests can check which agents ran.
- **`OpenAICompatibleProvider`**: raw `httpx` POST to `{LLM_BASE_URL}/chat/completions`. It covers OpenAI, Groq, OpenRouter, Together and Ollama without vendor SDKs. HTTP statuses map to the error hierarchy. Tests use `httpx.MockTransport`, so 401, 429, 500, timeout and malformed bodies are all checked without a network.
- `llm/provider.py`: `get_provider(settings)` factory. Changing provider means changing env vars, not code.

Env vars: `LLM_PROVIDER` (mock|openai_compatible), `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `MEMORY_MAX_MESSAGES`, `LOG_LEVEL`.

## 4. File list

```
multi-ai-agent-system/
├── app/
│   ├── main.py                 # app factory, exception handlers, static frontend mount
│   ├── config.py               # Settings (pydantic-settings)
│   ├── errors.py               # error hierarchy + HTTP mapping
│   ├── agents/
│   │   ├── base.py             # BaseAgent: run(), prompt building, LLM call, timing, trace, errors
│   │   ├── registry.py         # AgentRegistry
│   │   ├── orchestrator.py     # Orchestrator (safety → route → plan → execute → combine)
│   │   ├── coding.py  knowledge.py  reasoning.py
│   │   ├── fact_check.py  communication.py  safety.py
│   ├── llm/
│   │   ├── base.py             # LLMProvider ABC, LLMRequest/LLMResponse
│   │   ├── provider.py         # get_provider() factory
│   │   ├── mock.py             # MockProvider
│   │   └── openai_compatible.py
│   ├── schemas/
│   │   ├── chat.py             # ChatRequest, ChatResponse, AgentOutput, ErrorResponse
│   │   ├── routing.py          # RoutingDecision, ExecutionPlan
│   │   ├── fact_check.py       # FactCheckResult, Claim
│   │   ├── trace.py            # TraceStep, Trace
│   │   └── feedback.py
│   ├── services/
│   │   ├── router.py           # LLM router + keyword fallback
│   │   ├── memory.py           # ConversationMemory (in-process, bounded)
│   │   ├── trace.py            # TraceRecorder + bounded TraceStore
│   │   ├── search.py           # SearchService ABC + NullSearchService
│   │   ├── feedback.py         # in-memory FeedbackStore
│   │   └── logger.py           # JSON logging + request_id contextvar
│   └── api/routes.py           # /health /chat /agents /trace/{id} /feedback
├── frontend/                   # index.html, styles.css, app.js  (see D1)
├── tests/
│   ├── conftest.py             # app + MockProvider fixtures
│   ├── test_agents.py  test_router.py  test_api.py
│   ├── test_llm_provider.py    # OpenAI-compatible error mapping via MockTransport
│   └── test_safety.py
├── .env.example  .gitignore  requirements.txt  requirements-dev.txt
├── pyproject.toml              # pytest config only (asyncio_mode=auto)
├── Dockerfile  docker-compose.yml  LICENSE (MIT)  README.md
```

API: `GET /health`, `POST /chat` (`{message, conversation_id?}` → `{request_id, conversation_id, agent, agents_used, response, sections, fact_check?, safety?, trace}`), `GET /agents`, `GET /trace/{request_id}`, `POST /feedback` (`{request_id, rating: up|down, comment?}`). `/` serves the UI.

## 5. Build order (test after each)
1. Scaffold, config, errors, logging, LLM layer and MockProvider, plus provider tests
2. Schemas, BaseAgent, registry, the 6 specialist agents, plus agent tests
3. Safety and router (LLM + fallback), plus router and safety tests
4. Orchestrator with multi-agent plans, memory and trace
5. FastAPI routes, exception handlers, plus API tests
6. Frontend: chat, active-agent indicator, status, trace panel, clear button, example prompts, errors, responsive
7. Quality gate: full pytest run, launch uvicorn, call every endpoint, ≥5 real queries, secrets check
8. Dockerfile/compose, README with Mermaid diagram, pinned requirements, LICENSE, final report

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| No real LLM key, so the app has only been shown working on mock output | Label mock clearly everywhere. If you provide a key (D2), I run the ≥5 real queries against it. If not, the README says plainly that only mock mode was verified. |
| Docker not installed, so the Dockerfile can't be verified | The Dockerfile stays minimal and standard. The README marks it "not verified in the author's environment" until someone runs it. |
| Keyword safety layer has false positives and is easy to bypass | Say so in the README limitations. Unit-test the clear cases. Don't present it as robust moderation. |
| LLM router returns invalid JSON or invents agents | Schema validation, a registry whitelist, and a keyword fallback, all recorded in the trace and tested via `MockProvider(malformed=True)`. |
| Mock heuristics make routing look smarter than it is | Tests assert on mechanics (validation, fallback, plan building), not "intelligence". The README describes the mock honestly. |
| In-memory memory, traces and feedback are lost on restart and don't work across workers | Accepted for the MVP: bounded sizes, a single worker, documented. |
| Prompt injection through user text | User text goes only in user messages, never in system prompts. Router output is whitelisted. No tools execute code or reach the filesystem or network. |
| Microsoft Store Python path quirks on Windows | Use `python -m venv .venv` and `python -m pip`, so no global installs are needed. |

## 7. Decisions needed from you
- **D1, frontend:** I recommend **plain HTML/CSS/JS** served by FastAPI. That means one process, no build step and a simpler Docker image, and it covers every required UI feature. The alternative is React+Vite, which looks more modern on a CV but adds a Node build, `node_modules`, and a 2-stage Dockerfile.
- **D2, real provider:** do you have an OpenAI-compatible key (Groq's free tier, OpenAI, OpenRouter) to use for one manual verification run? It would only go in a local `.env`, which is never committed. If you don't, I'll ship mock-verified only and say so.
- **D3, search:** the default is the honest `NullSearchService` (everything "unverified"). An optional extra is a keyless Wikipedia search backend behind the same interface. It would provide real but limited sources, and it adds a network dependency.
