"""Gate 3 - clarification before action.

The cheapest way to avoid a wrong answer is to notice that the question is
underspecified before answering it. This gate covers the cases where acting on the
literal input would produce a confident, well-formatted, wrong result.

Distinct from gate 2: a boundary is "I am not permitted to do that", a clarification
is "I do not yet know what you are asking". The distinction is visible to the user in
the wording, and it matters - a refusal should feel final, a clarification should feel
like the app is paying attention.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import RULES, Rule


@dataclass
class ClarificationDecision:
    triggered: bool = False
    reason: str = ""
    patient_message: str = ""
    rule_id: str | None = None
    sources: list[str] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)


def check_clarification(text: str, context: dict | None = None) -> ClarificationDecision:
    context = context or {}
    lowered = (text or "").lower().strip()

    if not lowered:
        return ClarificationDecision()

    for rule in RULES.of_kind("clarify"):
        for pattern in rule.patterns:
            if pattern in lowered:
                if any(ex in lowered for ex in rule.exclude_patterns):
                    continue
                return ClarificationDecision(
                    triggered=True,
                    reason=rule.reason,
                    patient_message=rule.patient_message,
                    rule_id=rule.id,
                    sources=list(rule.sources),
                    options=rule.options,
                )

    return ClarificationDecision()
