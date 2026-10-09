from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackRecord(FeedbackRequest):
    received_at: datetime


class FeedbackResponse(BaseModel):
    status: Literal["recorded"] = "recorded"
    request_id: str
