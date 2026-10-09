from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    snippet: str = ""


class Claim(BaseModel):
    text: str
    # "source_found": a related source was retrieved — it is NOT proof the claim is correct.
    # "unverified": no source could be retrieved (or no search backend is configured).
    status: Literal["source_found", "unverified"]
    sources: list[Source] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    search_backend: str
    answer_origin: Literal["model_generated"] = "model_generated"
    claims: list[Claim]
    notice: str


class ExtractedClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=500)
    # Short keyword query for the search backend (whole sentences search poorly).
    search_query: str = Field(default="", max_length=120)


class ClaimExtraction(BaseModel):
    """Structured LLM output used by the fact-checking agent."""

    claims: list[ExtractedClaim] = Field(default_factory=list, max_length=5)
