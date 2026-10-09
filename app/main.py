"""FastAPI application factory: wiring, middleware, error handlers and the static frontend."""

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agents.orchestrator import Orchestrator
from app.agents.registry import AgentRegistry, build_registry
from app.api.routes import router as api_router
from app.config import Settings, get_settings
from app.errors import AppError, ConfigError
from app.llm.base import LLMProvider
from app.llm.provider import FallbackProvider, get_provider
from app.services.feedback import FeedbackStore
from app.services.logger import get_logger, request_id_var, setup_logging
from app.services.memory import ConversationMemory
from app.services.router import Router
from app.services.search import SearchService, get_search_service
from app.services.trace import TraceStore

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
log = get_logger("main")


@dataclass
class Services:
    settings: Settings
    llm: LLMProvider | None
    search: SearchService
    registry: AgentRegistry
    memory: ConversationMemory
    traces: TraceStore
    feedback: FeedbackStore
    orchestrator: Orchestrator
    config_problems: list[str]
    config_warnings: list[str]
    fallback_model: str | None
    router: Router


def build_services(settings: Settings, llm: LLMProvider | None = None,
                   search: SearchService | None = None) -> Services:
    problems: list[str] = []
    if llm is None:
        try:
            llm = get_provider(settings)
        except ConfigError as exc:
            # Start anyway so /health can report the problem; /chat will return 503.
            problems = settings.config_problems() or [exc.detail]
            log.error("LLM provider not configured", extra={"event": "config_error", "error_type": "config_error"})
    search = search or get_search_service(settings.search_provider, settings.search_user_agent,
                                          settings.search_timeout_seconds)
    # Per-agent models only apply to a real provider (the mock ignores model names anyway).
    agent_models = settings.llm_agent_models if settings.llm_provider != "mock" else {}
    registry = build_registry(llm, search, settings.llm_max_tokens, agent_models)
    memory = ConversationMemory(max_messages=settings.memory_max_messages)
    traces = TraceStore(max_size=settings.trace_store_size)
    router = Router(registry, llm, agent_models.get("router"))
    orchestrator = Orchestrator(registry, router, memory, traces, llm,
                                config_error="; ".join(problems) or None)
    fallback_model = settings.llm_fallback_model if isinstance(llm, FallbackProvider) else None
    warnings = [f"backup provider disabled: {p}" for p in settings.fallback_problems()]
    known = {a.name for a in registry.all() if a.uses_llm} | {"router"}
    warnings += [f"LLM_AGENT_MODELS: unknown agent '{name}' ignored" for name in agent_models if name not in known]
    return Services(settings, llm, search, registry, memory, traces, FeedbackStore(), orchestrator,
                    problems, warnings, fallback_model, router)


def _error_response(status: int, error_type: str, message: str, request: Request) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status,
        content={"error": {"type": error_type, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None,
               search: SearchService | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    services = build_services(settings, llm, search)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("startup", extra={"event": "startup", "provider": services.orchestrator.provider_name,
                                   "model": settings.llm_model})
        yield
        if services.llm is not None:
            await services.llm.aclose()
        await services.search.aclose()

    app = FastAPI(title="Multi-AI Agent System", version="0.1.0", lifespan=lifespan,
                  description="Orchestrator that routes requests to specialist LLM agents.")
    app.state.services = services

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        if request.url.path not in ("/health",) and not request.url.path.startswith("/static"):
            log.info("http request", extra={
                "event": "http_request", "method": request.method, "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error_response(exc.status_code, exc.error_type, exc.public_message, request)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        issues = "; ".join(
            "request body is not valid JSON" if err["type"] == "json_invalid"
            else f"{'.'.join(str(p) for p in err['loc'] if p != 'body') or 'body'}: {err['msg']}"
            for err in exc.errors()
        )
        return _error_response(422, "validation_error", issues or "invalid request", request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        return _error_response(exc.status_code, "http_error", str(exc.detail), request)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"event": "unhandled_error", "error_type": type(exc).__name__})
        return _error_response(500, "internal_error", "An unexpected error occurred.", request)

    app.include_router(api_router)

    if FRONTEND_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

        @app.get("/", include_in_schema=False)
        async def index():
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
