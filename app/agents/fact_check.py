import asyncio

from app.agents.base import AgentContext, BaseAgent
from app.llm.base import ChatMessage, LLMProvider
from app.llm.structured import parse_model_output
from app.schemas.chat import AgentOutput
from app.schemas.fact_check import Claim, ClaimExtraction, FactCheckResult
from app.services.search import SearchService
from app.services.trace import TraceRecorder


class FactCheckAgent(BaseAgent):
    """Extracts checkable claims from the draft answer and looks for related sources.

    It does not decide truth. Claims are labelled `source_found` (a related source was retrieved,
    to be read by the user) or `unverified`. Without a search backend every claim is `unverified`.
    """

    name = "fact_check_agent"
    intent = "fact_check"
    description = ("Extracts factual claims from the answer and looks up related sources; "
                   "labels claims it cannot source as unverified.")
    stage = 40
    optional = True
    temperature = 0.0
    routing_keywords = ("is it true", "fact check", "fact-check", "verify", "true that", "accurate", "myth", "source")
    system_prompt = """You extract checkable factual claims.
- From the text in the user message, list up to 5 short, self-contained, verifiable factual claims
  (names, dates, numbers, causal facts). Skip opinions, advice, code and hedged statements.
- Rewrite each claim so it is understandable without the surrounding text.
- For each claim also give search_query: 2-6 keywords naming the main subject, suitable for an
  encyclopedia search (e.g. "Great Wall of China visibility from space").
- If there are no checkable claims, return an empty list.
Return JSON: {"claims": [{"claim": "...", "search_query": "..."}]}"""

    def __init__(self, llm: LLMProvider | None, search: SearchService, max_tokens: int = 1200):
        super().__init__(llm, max_tokens=max_tokens)
        self.search = search

    async def handle(self, ctx: AgentContext, trace: TraceRecorder) -> AgentOutput:
        drafts = [o for o in ctx.prior_outputs if o.agent != self.name]
        text_to_check = drafts[-1].content if drafts else ctx.message

        response = await self.complete(
            trace, [ChatMessage(role="user", content=text_to_check)],
            json_schema=ClaimExtraction.model_json_schema(), task="claim_extraction",
        )
        extraction = parse_model_output(response.text, ClaimExtraction)
        extracted = [c for c in extraction.claims if c.claim.strip()][:5]

        with trace.step("search", agent=self.name, detail=f"backend={self.search.name}") as step:
            results = await asyncio.gather(
                *(self.search.search(c.search_query.strip() or c.claim) for c in extracted))
            step.detail = f"backend={self.search.name}; claims={len(extracted)}"

        claims = [
            Claim(text=c.claim.strip(), status="source_found" if sources else "unverified", sources=sources)
            for c, sources in zip(extracted, results)
        ]
        result = FactCheckResult(search_backend=self.search.name, claims=claims, notice=self._notice(claims))
        return AgentOutput(agent=self.name, content=result.notice, data=result.model_dump(mode="json"))

    def _notice(self, claims: list[Claim]) -> str:
        if not claims:
            return "No checkable factual claims were found in the answer."
        if self.search.name == "none":
            return ("The answer is model-generated. No search backend is configured, so none of the "
                    f"{len(claims)} extracted claim(s) could be checked against sources: treat them as unverified.")
        found = sum(c.status == "source_found" for c in claims)
        return (f"The answer is model-generated. Related {self.search.name} sources were found for {found} of "
                f"{len(claims)} claim(s). A related source is not proof: read it to confirm. "
                "Claims without sources are unverified.")
