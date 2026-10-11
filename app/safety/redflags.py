"""Gate 1 - possible emergency.

Highest priority, checked first, and its result cannot be overridden by anything later
in the pipeline. The app must be willing to abandon whatever it was doing (M6: "the app
must never delay a required help message in order to finish collecting data").

Scope discipline
----------------
This is **not** a triage system. It does not estimate probability, does not rank
severity between presentations, and does not say "you are fine" when nothing matches.
A negative result means only "no configured phrase matched", which is not the same as
"no emergency" - and ``no_match_disclaimer`` states that so the UI cannot imply safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import RULES, Rule


@dataclass
class RedFlagDecision:
    triggered: bool = False
    severity: str = "info"
    reason: str = ""
    patient_message: str = ""
    rule_id: str | None = None
    sources: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    no_match_disclaimer: str = (
        "This check only looks for a short list of phrases. It does not rule anything "
        "out. If you feel very unwell, contact a doctor or call for help."
    )


def _matches(rule: Rule, text: str) -> list[str]:
    hits = []
    for pattern in rule.patterns:
        if pattern in text:
            if any(ex in text for ex in rule.exclude_patterns):
                continue
            hits.append(pattern)
    return hits


def check_red_flags(text: str, context: dict | None = None) -> RedFlagDecision:
    """Scan for configured emergency wording.

    Rules are evaluated in the order they appear in the rule files, and the first
    enabled rule that matches wins. Emergency-severity rules are listed before
    urgent ones in the content files, so the more pressing message is the one shown.
    """
    context = context or {}
    lowered = (text or "").lower().strip()

    if not lowered:
        return RedFlagDecision()

    # Emergency first, then urgent. Within a severity, file order is preserved.
    for severity in ("emergency", "urgent"):
        for rule in RULES.of_kind("red_flag"):
            if rule.severity != severity:
                continue
            hits = _matches(rule, lowered)
            if hits:
                return RedFlagDecision(
                    triggered=True,
                    severity=severity,
                    reason=rule.reason,
                    patient_message=rule.patient_message,
                    rule_id=rule.id,
                    sources=list(rule.sources),
                    matched=hits,
                )

    return RedFlagDecision()
