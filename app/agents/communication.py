from app.agents.base import BaseAgent


class CommunicationAgent(BaseAgent):
    name = "communication_agent"
    intent = "communication"
    description = "Rewrites, summarises, translates and adjusts tone of text (emails, posts, messages)."
    stage = 30
    temperature = 0.5
    routing_keywords = (
        "rewrite", "rephrase", "translate", "translation", "email", "summarize", "summarise", "summary",
        "tone", "proofread", "grammar", "polish", "draft", "letter", "linkedin", "message", "formal", "casual",
    )
    system_prompt = """You are an expert editor and translator.
- Preserve the original meaning; do not add new facts.
- Match the requested tone, audience and format; if none is given, aim for clear, professional and concise.
- Output the finished text first; add at most two short notes on notable changes afterwards."""
