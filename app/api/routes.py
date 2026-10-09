from fastapi import APIRouter, Request

from app.errors import NotFoundError
from app.schemas.chat import AgentInfo, ChatRequest, ChatResponse
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.trace import Trace
from app.services.logger import get_logger

router = APIRouter()
log = get_logger("api")


def _services(request: Request):
    return request.app.state.services


@router.get("/health")
async def health(request: Request) -> dict:
    services = _services(request)
    problems = services.config_problems
    return {
        "status": "degraded" if problems else "ok",
        "provider": services.orchestrator.provider_name,
        "model": services.settings.llm_model if not problems else None,
        "router_model": services.router.model_name,
        "fallback_model": services.fallback_model,
        "search_backend": services.search.name,
        "problems": problems,
        "warnings": services.config_warnings,
        "version": request.app.version,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    return await _services(request).orchestrator.handle(body, request.state.request_id)


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(request: Request) -> list[AgentInfo]:
    return [AgentInfo(**agent.info()) for agent in _services(request).registry.all()]


@router.get("/trace/{request_id}", response_model=Trace)
async def get_trace(request_id: str, request: Request) -> Trace:
    trace = _services(request).traces.get(request_id)
    if trace is None:
        raise NotFoundError(f"no trace for request_id {request_id}")
    return trace


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def feedback(body: FeedbackRequest, request: Request) -> FeedbackResponse:
    services = _services(request)
    if body.request_id not in services.traces:
        raise NotFoundError(f"unknown request_id {body.request_id}")
    services.feedback.add(body)
    log.info("feedback recorded", extra={"event": "feedback", "status": body.rating})
    return FeedbackResponse(request_id=body.request_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def clear_conversation(conversation_id: str, request: Request) -> None:
    _services(request).memory.clear(conversation_id)
