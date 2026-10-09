"""Orchestrator: safety gate -> route -> plan -> execute agents in order -> combine -> validate."""

import time
import uuid

from pydantic import ValidationError

from app.agents.base import AgentContext
from app.agents.registry import AgentRegistry
from app.agents.safety import SafetyAgent
from app.errors import AppError, ConfigError, LLMError, MalformedOutputError
from app.llm.base import LLMProvider
from app.schemas.chat import AgentOutput, ChatRequest, ChatResponse, SafetyInfo
from app.schemas.fact_check import FactCheckResult
from app.services.logger import get_logger
from app.services.memory import ConversationMemory
from app.services.router import FACT_CHECK_AGENT, Router
from app.services.trace import TraceRecorder, TraceStore

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(self, registry: AgentRegistry, router: Router, memory: ConversationMemory,
                 traces: TraceStore, llm: LLMProvider | None, config_error: str | None = None):
        self.registry = registry
        self.router = router
        self.memory = memory
        self.traces = traces
        self.llm = llm
        self.config_error = config_error
        self.safety: SafetyAgent = registry.get("safety_agent")  # type: ignore[assignment]

    @property
    def provider_name(self) -> str:
        return self.llm.name if self.llm else "unconfigured"

    async def handle(self, request: ChatRequest, request_id: str) -> ChatResponse:
        started = time.perf_counter()
        trace = TraceRecorder(request_id)
        self.traces.save(trace)  # saved up front so failed requests are traceable too
        conversation_id = request.conversation_id or uuid.uuid4().hex
        message = request.message
        trace.event("request_received", detail=f"chars={len(message)}")
        log.info("request received", extra={"event": "request_received", "message_chars": len(message)})

        try:
            response = await self._run(request_id, conversation_id, message, trace)
        except Exception as exc:
            error_type = exc.error_type if isinstance(exc, AppError) else type(exc).__name__
            trace.event("final", status="error", error_type=error_type)
            trace.finish("error")
            log.warning("request failed", extra={
                "event": "request_failed", "status": "error", "error_type": error_type,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
            raise
        log.info("request completed", extra={
            "event": "request_completed", "status": "ok", "agents": response.agents_used,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
        return response

    async def _run(self, request_id: str, conversation_id: str, message: str,
                   trace: TraceRecorder) -> ChatResponse:
        # 1. Safety gate (rule-based, no LLM call)
        with trace.step("safety_check", agent=self.safety.name) as step:
            verdict = self.safety.check(message)
            step.detail = f"blocked; category={verdict.category}" if verdict.blocked else "passed"
        if verdict.blocked:
            log.info("request blocked", extra={"event": "safety_blocked", "category": verdict.category})
            output = self.safety.refusal(verdict)
            return self._finalize(trace, request_id, conversation_id, intent="unsafe", routing_source="safety",
                                  outputs=[output], safety=SafetyInfo(blocked=True, category=verdict.category))

        if self.llm is None:
            raise ConfigError(self.config_error or "LLM provider is not configured")

        # 2. Route
        history = self.memory.history(conversation_id)
        plan = await self.router.plan(message, history, trace)
        trace.event("intent_classified", agent="router",
                    detail=f"intent={plan.intent}; source={plan.routing_source}")
        trace.event("agent_selected", detail=" -> ".join(plan.agents))
        log.info("routed", extra={"event": "routed", "intent": plan.intent, "agents": plan.agents,
                                  "routing_source": plan.routing_source})

        # 3. Execute agents in order; each sees the outputs of the previous ones
        outputs: list[AgentOutput] = []
        for name in plan.agents:
            agent = self.registry.get(name)
            ctx = AgentContext(request_id=request_id, message=message, history=history, prior_outputs=outputs)
            try:
                outputs.append(await agent.run(ctx, trace))
            except LLMError as exc:
                if agent.optional and outputs:
                    trace.event("agent_skipped", agent=name, status="error", error_type=exc.error_type,
                                detail="optional agent failed; continuing without it")
                    continue
                raise

        response = self._finalize(trace, request_id, conversation_id, intent=plan.intent,
                                  routing_source=plan.routing_source, outputs=outputs,
                                  safety=SafetyInfo(blocked=False))
        self.memory.append_turn(conversation_id, message, response.response)
        return response

    def _finalize(self, trace: TraceRecorder, request_id: str, conversation_id: str, *, intent: str,
                  routing_source: str, outputs: list[AgentOutput], safety: SafetyInfo) -> ChatResponse:
        trace.event("response_generated", detail=f"sections={len(outputs)}")
        with trace.step("validation"):
            answers = [o for o in outputs if o.agent != FACT_CHECK_AGENT]
            fact_check_output = next((o for o in outputs if o.agent == FACT_CHECK_AGENT), None)
            final = answers[-1] if answers else None
            if final is None or not final.content.strip():
                raise MalformedOutputError("no agent produced a non-empty answer")
            try:
                response = ChatResponse(
                    request_id=request_id,
                    conversation_id=conversation_id,
                    agent=final.agent,
                    agents_used=[o.agent for o in outputs],
                    intent=intent,
                    routing_source=routing_source,
                    response=final.content,
                    sections=outputs,
                    fact_check=(FactCheckResult.model_validate(fact_check_output.data)
                                if fact_check_output and fact_check_output.data else None),
                    safety=safety,
                    provider=self.provider_name,
                    trace=[],
                )
            except ValidationError as exc:
                raise MalformedOutputError(f"response failed schema validation ({exc.error_count()} errors)") from exc
        trace.event("final", detail=f"agent={final.agent}")
        trace.finish("ok")
        response.trace = list(trace.steps)
        return response
