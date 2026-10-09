"""Helpers for turning raw model text into validated Pydantic objects."""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import MalformedOutputError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json_object(text: str) -> dict:
    """Parse the first JSON object in `text`, tolerating markdown fences and surrounding prose."""
    cleaned = _FENCE_RE.sub("", text.strip())
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise MalformedOutputError("no JSON object found in model output")
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MalformedOutputError(f"invalid JSON in model output: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise MalformedOutputError("model output JSON is not an object")
    return value


def parse_model_output(text: str, model: type[T]) -> T:
    data = extract_json_object(text)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise MalformedOutputError(
            f"model output failed {model.__name__} validation ({exc.error_count()} errors)"
        ) from exc
