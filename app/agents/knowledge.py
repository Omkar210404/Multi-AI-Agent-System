from app.agents.base import BaseAgent


class KnowledgeAgent(BaseAgent):
    name = "knowledge_agent"
    intent = "knowledge"
    description = "Explains concepts and answers general-knowledge questions clearly."
    stage = 10
    routing_keywords = (
        "what is", "what are", "explain", "who", "when", "where", "define", "definition", "meaning",
        "history", "how does", "how do", "overview", "describe", "concept", "difference between",
    )
    system_prompt = """You explain concepts clearly to a smart non-expert.
- Lead with a direct 1-2 sentence answer, then supporting explanation with a concrete example.
- Keep it under ~250 words unless the question clearly needs more.
- Clearly mark uncertainty, and distinguish well-established facts from contested points."""
