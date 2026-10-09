"""Rule-based safety gate. Runs before routing; blocked requests never reach the other agents.

This is a basic keyword/pattern layer, not a robust moderation system: it can be bypassed by
rephrasing and may produce false positives. See README limitations.
"""

import re
from dataclasses import dataclass

from app.agents.base import AgentContext, BaseAgent
from app.schemas.chat import AgentOutput
from app.services.trace import TraceRecorder

_I = re.IGNORECASE

UNSAFE_PATTERNS: dict[str, list[re.Pattern]] = {
    "weapons_explosives": [
        re.compile(r"\b(make|build|construct|assemble|create|synthesi[sz]e|recipe for)\b.{0,40}"
                   r"\b(bomb|explosives?|ied|pipe ?bomb|grenade|napalm|nerve agent|sarin|ricin|"
                   r"bio ?weapon|chemical weapon|ghost gun)s?\b", _I),
    ],
    "illegal_drugs": [
        re.compile(r"\b(cook|make|synthesi[sz]e|manufacture|produce)\b.{0,30}"
                   r"\b(meth|methamphetamine|fentanyl|heroin|cocaine|crack)\b", _I),
    ],
    "malware_hacking": [
        re.compile(r"\b(write|create|build|make|code|develop)\b.{0,40}"
                   r"\b(ransomware|keylogger|malware|computer virus|trojan|botnet|rootkit|"
                   r"credential stealer|spyware)\b", _I),
        re.compile(r"\b(hack|break) into\b.{0,30}\b(someone|somebody|account|email|phone|bank|"
                   r"instagram|facebook|wifi)\b", _I),
        re.compile(r"\b(ddos|dos) attack (on|against)\b", _I),
    ],
    "violence": [
        re.compile(r"\bhow (do i|to|can i|could i)\b.{0,30}\b(kill|murder|poison|stab|shoot|hurt)\b.{0,30}"
                   r"\b(someone|somebody|a person|people|my|him|her|them|neighbou?r|boss)\b", _I),
    ],
    "sexual_minors": [
        re.compile(r"\b(child|children|minor|minors|underage|kid|kids|teen)\b.{0,40}"
                   r"\b(sex|sexual|nude|naked|porn|explicit)\b", _I),
        re.compile(r"\b(sex|sexual|nude|naked|porn|explicit)\b.{0,40}"
                   r"\b(child|children|minor|minors|underage|kid|kids)\b", _I),
    ],
    "self_harm": [
        re.compile(r"\b(kill myself|killing myself|suicide|suicidal|end my life|hurt myself|"
                   r"self[- ]harm|want to die)\b", _I),
    ],
}

REFUSAL = ("I can't help with that request because it falls into a restricted category ({category}). "
           "If you're working on something related for a legitimate reason (for example security research "
           "or safety education), try asking about defensive or high-level aspects instead.")

SELF_HARM_RESPONSE = (
    "I'm really sorry you're going through this. You don't have to handle it alone. "
    "If you are in immediate danger, please contact your local emergency number now. "
    "You can also reach a crisis line: in India, Tele-MANAS at 14416 (or 1-800-891-4416); "
    "in the US, call or text 988; elsewhere, findahelpline.com lists free local services. "
    "Talking to someone you trust can help too."
)


@dataclass(frozen=True)
class SafetyVerdict:
    blocked: bool
    category: str | None = None


class SafetyAgent(BaseAgent):
    name = "safety_agent"
    intent = "unsafe"
    description = "Screens every request before routing; blocks clearly unsafe categories with a safe response."
    stage = 0
    routable = False
    uses_llm = False

    def check(self, message: str) -> SafetyVerdict:
        for category, patterns in UNSAFE_PATTERNS.items():
            if any(p.search(message) for p in patterns):
                return SafetyVerdict(blocked=True, category=category)
        return SafetyVerdict(blocked=False)

    def refusal(self, verdict: SafetyVerdict) -> AgentOutput:
        if verdict.category == "self_harm":
            content = SELF_HARM_RESPONSE
        else:
            content = REFUSAL.format(category=(verdict.category or "unsafe").replace("_", " "))
        return AgentOutput(agent=self.name, content=content, data={"category": verdict.category})

    async def handle(self, ctx: AgentContext, trace: TraceRecorder) -> AgentOutput:
        verdict = self.check(ctx.message)
        if verdict.blocked:
            return self.refusal(verdict)
        return AgentOutput(agent=self.name, content="No safety issues detected.", data={"category": None})
