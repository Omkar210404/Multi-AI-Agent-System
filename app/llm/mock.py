"""Deterministic, offline mock provider.

Used as the default provider (no API key needed) and in tests. It does NOT generate real answers:
- structured requests (routing, claim extraction) get valid JSON built from simple keyword heuristics,
  so the real parsing/validation code paths are exercised;
- free-text requests get a templated reply that is always visibly tagged as mock output.

Test hooks (constructor arguments, never driven by env vars):
- `responses`: queue of raw texts returned in order before falling back to the default behaviour
- `responder`: callable(LLMRequest) -> str | None, overriding the default behaviour when it returns a str
- `fail_with`: exception instance raised on every call (or `fail_times` calls, then succeed)
- `malformed`: return non-JSON text for structured requests
- `calls`: list of every LLMRequest received, for assertions
"""

import asyncio
import json
import re
import time
from collections import deque
from collections.abc import Callable

from app.llm.base import LLMProvider, LLMRequest, LLMResponse

# Heuristic table for the mock "router". This simulates an LLM's routing judgement offline;
# it is intentionally simple and is independent of the app's own keyword fallback.
_MOCK_ROUTING_RULES: list[tuple[str, str, re.Pattern]] = [
    ("coding", "coding_agent", re.compile(
        r"\b(code|python|function|script|bug|debug|sql|javascript|java|csv|api|regex|class|algorithm|program)\b", re.I)),
    ("communication", "communication_agent", re.compile(
        r"\b(rewrite|rephrase|translate|email|summari[sz]e|tone|proofread|grammar|polish|draft)\b", re.I)),
    ("reasoning", "reasoning_agent", re.compile(
        r"\b(why|compare|pros and cons|trade-?offs?|should i|decide|step by step|logic|puzzle)\b", re.I)),
    ("fact_check", "fact_check_agent", re.compile(
        r"\b(is it true|fact[- ]?check|verify|true that|accurate|myth)\b", re.I)),
]

MOCK_HEADER = "**Demo answer · {agent}**"

_MOCK_REPLIES = {
    "coding_agent": (
        "With a real model connected, the Coding specialist returns working code here. Placeholder:\n\n"
        "```python\ndef solve():\n    # real code comes from the configured LLM provider\n    ...\n```"
    ),
    "knowledge_agent": (
        "With a real model connected, the Knowledge specialist explains the topic here: "
        "a direct answer first, then an example."
    ),
    "reasoning_agent": (
        "With a real model connected, the Reasoning specialist builds on the previous draft:\n\n"
        "1. Key factors\n2. How they interact\n3. Conclusion"
    ),
    "communication_agent": (
        "With a real model connected, the Writing specialist returns your text rewritten here, "
        "keeping the meaning and adjusting the tone."
    ),
    "fact_check_agent": "With a real model connected, a fact-check summary appears here.",
}


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(
        self,
        model: str = "mock-model",
        responses: list[str] | None = None,
        responder: Callable[[LLMRequest], str | None] | None = None,
        fail_with: Exception | None = None,
        fail_times: int | None = None,
        malformed: bool = False,
        latency_ms: float = 0.0,
    ):
        self.model = model
        self._responses = deque(responses or [])
        self._responder = responder
        self._fail_with = fail_with
        self._fail_times = fail_times
        self._malformed = malformed
        self._latency_ms = latency_ms
        self.calls: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        started = time.perf_counter()
        self.calls.append(request)
        if self._latency_ms:
            await asyncio.sleep(self._latency_ms / 1000)

        if self._fail_with is not None:
            if self._fail_times is None or self._fail_times > 0:
                if self._fail_times is not None:
                    self._fail_times -= 1
                raise self._fail_with

        text = self._next_text(request)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            usage=None,
        )

    def _next_text(self, request: LLMRequest) -> str:
        if self._responses:
            return self._responses.popleft()
        if self._responder is not None:
            scripted = self._responder(request)
            if scripted is not None:
                return scripted
        if request.json_schema is not None:
            if self._malformed:
                return "Sure! Here is the answer you wanted (not JSON)."
            return json.dumps(self._structured(request))
        agent = request.metadata.get("agent", "assistant")
        body = _MOCK_REPLIES.get(agent, "This is a placeholder reply.")
        return f"{MOCK_HEADER.format(agent=agent)}\n\n{body}"

    @staticmethod
    def _structured(request: LLMRequest) -> dict:
        task = request.metadata.get("task")
        text = request.last_user_message
        if task == "routing":
            matches = [(intent, agent) for intent, agent, pattern in _MOCK_ROUTING_RULES if pattern.search(text)]
            agents = [agent for _, agent in matches if agent != "fact_check_agent"][:2]
            requires_fact_check = any(agent == "fact_check_agent" for _, agent in matches)
            if not agents:
                agents = ["knowledge_agent"]
            if "reasoning_agent" in agents and "coding_agent" not in agents and "knowledge_agent" not in agents:
                agents.insert(0, "knowledge_agent")
            intent = matches[0][0] if matches else "knowledge"
            return {
                "intent": intent,
                "agents": agents,
                "reason": "mock router: keyword heuristics",
                "requires_fact_check": requires_fact_check,
            }
        if task == "claim_extraction":
            if text.startswith("**Demo answer"):
                return {"claims": []}  # mock answers contain no real factual claims
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
            return {"claims": [{"claim": s, "search_query": " ".join(s.split()[:5])} for s in sentences[:3]]}
        return {}
