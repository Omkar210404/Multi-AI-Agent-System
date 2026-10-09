from app.agents.base import BaseAgent


class CodingAgent(BaseAgent):
    name = "coding_agent"
    intent = "coding"
    description = "Writes, explains and debugs code. Generates code only; never executes it."
    stage = 10
    temperature = 0.2
    min_output_tokens = 2400
    routing_keywords = (
        "code", "python", "function", "script", "bug", "debug", "error", "exception", "sql", "javascript",
        "typescript", "java", "c++", "csv", "api", "regex", "class", "algorithm", "program", "refactor",
        "unit test", "pandas", "dataframe", "compile",
    )
    system_prompt = """You write correct, idiomatic, production-quality code.
- Start with a one-line summary of the approach, then the code in fenced blocks with the language tag.
- Prefer the standard library and well-known packages; state any dependency explicitly.
- Handle obvious edge cases and errors; keep functions small and named clearly.
- Keep it focused: one complete, runnable solution of at most ~60 lines. No alternative versions, and no
  command-line argument parsing or other boilerplate unless the user asks for it.
- End with a short "How to run" note and any assumptions you made.
- You cannot run code: never claim that you executed or tested it."""
