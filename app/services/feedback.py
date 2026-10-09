"""In-memory feedback store (MVP). Swap for a database-backed implementation in production."""

from collections import deque
from datetime import datetime, timezone

from app.schemas.feedback import FeedbackRecord, FeedbackRequest


class FeedbackStore:
    def __init__(self, max_records: int = 5000):
        self._records: deque[FeedbackRecord] = deque(maxlen=max_records)

    def add(self, feedback: FeedbackRequest) -> FeedbackRecord:
        record = FeedbackRecord(**feedback.model_dump(), received_at=datetime.now(timezone.utc))
        self._records.append(record)
        return record

    def all(self) -> list[FeedbackRecord]:
        return list(self._records)
