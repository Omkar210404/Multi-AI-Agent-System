"""Per-request trace recording and a bounded in-memory trace store."""

import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from app.errors import AppError
from app.schemas.trace import Trace, TraceStep


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TraceRecorder:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.created_at = _now()
        self._start = time.perf_counter()
        self.steps: list[TraceStep] = []
        self.status: str = "in_progress"
        self.total_ms: float | None = None

    def event(self, name: str, agent: str | None = None, status: str = "ok",
              detail: str | None = None, error_type: str | None = None) -> TraceStep:
        """Record an instantaneous step."""
        step = TraceStep(name=name, agent=agent, status=status, started_at=_now(),
                         detail=detail, error_type=error_type)
        self.steps.append(step)
        return step

    @contextmanager
    def step(self, name: str, agent: str | None = None, detail: str | None = None) -> Iterator[TraceStep]:
        """Record a timed step; marks it as an error (with the error type) if the block raises."""
        step = TraceStep(name=name, agent=agent, started_at=_now(), detail=detail)
        self.steps.append(step)
        started = time.perf_counter()
        try:
            yield step
        except Exception as exc:
            step.status = "error"
            step.error_type = exc.error_type if isinstance(exc, AppError) else type(exc).__name__
            raise
        finally:
            step.duration_ms = round((time.perf_counter() - started) * 1000, 2)

    def finish(self, status: str) -> None:
        self.status = status
        self.total_ms = round((time.perf_counter() - self._start) * 1000, 2)

    def to_model(self) -> Trace:
        return Trace(request_id=self.request_id, status=self.status, created_at=self.created_at,
                     total_ms=self.total_ms, steps=list(self.steps))


class TraceStore:
    """Keeps the most recent `max_size` traces (oldest evicted first)."""

    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._traces: OrderedDict[str, TraceRecorder] = OrderedDict()

    def save(self, recorder: TraceRecorder) -> None:
        self._traces[recorder.request_id] = recorder
        self._traces.move_to_end(recorder.request_id)
        while len(self._traces) > self.max_size:
            self._traces.popitem(last=False)

    def get(self, request_id: str) -> Trace | None:
        recorder = self._traces.get(request_id)
        return recorder.to_model() if recorder else None

    def __contains__(self, request_id: str) -> bool:
        return request_id in self._traces
