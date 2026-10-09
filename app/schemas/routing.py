from typing import Literal

from pydantic import BaseModel, Field


class RoutingDecision(BaseModel):
    """Structured output of the router (from the LLM, or from the keyword fallback)."""

    intent: str = Field(min_length=1, max_length=40)
    agents: list[str] = Field(min_length=1, max_length=4)
    reason: str = Field(default="", max_length=300)
    requires_fact_check: bool = False


class ExecutionPlan(BaseModel):
    """Validated, ordered list of agents the orchestrator will run."""

    intent: str
    agents: list[str]
    reason: str
    routing_source: Literal["llm", "fallback"]
