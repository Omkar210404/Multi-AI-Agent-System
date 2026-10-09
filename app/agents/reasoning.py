from app.agents.base import BaseAgent


class ReasoningAgent(BaseAgent):
    name = "reasoning_agent"
    intent = "reasoning"
    description = "Analyses problems step by step: causes, trade-offs, comparisons and decisions."
    stage = 20
    temperature = 0.2
    routing_keywords = (
        "why", "compare", "comparison", "pros and cons", "trade-off", "tradeoff", "should i", "decide",
        "analyze", "analyse", "step by step", "logic", "puzzle", "reason", "cause", "impact", "versus", "vs",
    )
    system_prompt = """You produce structured analysis.
- If previous agents provided a draft, build on it: correct mistakes and fill gaps rather than repeating it.
- Structure: key factors -> how they interact -> conclusion. Use numbered steps or a small table where helpful.
- Present the final, user-facing answer only: concise reasoning summary, not an internal monologue.
- State assumptions explicitly.
- Keep it under ~350 words; prefer one compact table or list over several."""
