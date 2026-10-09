from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TraceStep(BaseModel):
    """One operational step. Contains metadata only — never prompts, model reasoning or secrets."""

    name: str
    agent: str | None = None
    status: Literal["ok", "error", "skipped"] = "ok"
    started_at: datetime
    duration_ms: float = 0.0
    error_type: str | None = None
    detail: str | None = None


class Trace(BaseModel):
    request_id: str
    status: Literal["in_progress", "ok", "error"] = "in_progress"
    created_at: datetime
    total_ms: float | None = None
    steps: list[TraceStep]
