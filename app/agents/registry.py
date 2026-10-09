"""Agent registry: the single place that knows which agents exist.

The router builds its prompt and its keyword fallback from the registry, so adding an agent means
writing one `BaseAgent` subclass and registering it here — no routing if/else to edit.
"""

from app.agents.base import BaseAgent
from app.agents.coding import CodingAgent
from app.agents.communication import CommunicationAgent
from app.agents.fact_check import FactCheckAgent
from app.agents.knowledge import KnowledgeAgent
from app.agents.reasoning import ReasoningAgent
from app.agents.safety import SafetyAgent
from app.llm.base import LLMProvider, ModelChoice
from app.services.search import SearchService


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        return self._agents[name]

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def routable(self) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.routable]


def build_registry(llm: LLMProvider | None, search: SearchService, max_tokens: int = 1200,
                   agent_models: dict[str, ModelChoice] | None = None) -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(SafetyAgent(llm, max_tokens))
    registry.register(CodingAgent(llm, max_tokens))
    registry.register(KnowledgeAgent(llm, max_tokens))
    registry.register(ReasoningAgent(llm, max_tokens))
    registry.register(CommunicationAgent(llm, max_tokens))
    registry.register(FactCheckAgent(llm, search, max_tokens))
    for name, choice in (agent_models or {}).items():
        if name in registry and registry.get(name).uses_llm:
            registry.get(name).model_choice = choice
    return registry
