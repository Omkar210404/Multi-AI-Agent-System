from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.fact_check import FactCheckResult
from app.schemas.trace import TraceStep

MAX_MESSAGE_CHARS = 4000


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class AgentOutput(BaseModel):
    agent: str
    content: str
    data: dict[str, Any] | None = None


class SafetyInfo(BaseModel):
    blocked: bool
    category: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    conversation_id: str
    agent: str = Field(description="Agent that produced the final response")
    agents_used: list[str]
    intent: str
    routing_source: str
    response: str = Field(min_length=1)
    sections: list[AgentOutput]
    fact_check: FactCheckResult | None = None
    safety: SafetyInfo
    provider: str
    trace: list[TraceStep]


class AgentInfo(BaseModel):
    name: str
    description: str
    stage: int
    routable: bool
    model: str | None = None


class ErrorBody(BaseModel):
    type: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
