"""Gate 2 - scope boundaries.

Implements Challenge 2's hard requirement: *never crosses from explanation into
medication advice*. This gate catches the requests where a helpful-sounding model
answer would be exactly the wrong thing to say.

What it intercepts
------------------
* asks to change a dose, stop a medicine, or start a new one
* asks what to do about a missed dose
* asks the app to identify a pill by appearance, or a name it does not recognise
* asks for a diagnosis

What it does instead
--------------------
Every refusal is a *redirect*, not a dead end. The patient is offered the constructive
route: record the concern, add it to the list of questions for the doctor or pharmacist,
and - where the request came bundled with a symptom - route to the help path instead.
A refusal that leaves the user with nothing is a bad refusal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import RULES, Rule


@dataclass
class BoundaryDecision:
    triggered: bool = False
    reason: str = ""
    patient_message: str = ""
    rule_id: str | None = None
    sources: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    redirect: str | None = None
    offer_question: bool = False


def _matches(rule: Rule, text: str) -> list[str]:
    hits = []
    for pattern in rule.patterns:
        if pattern in text:
            if any(ex in text for ex in rule.exclude_patterns):
                continue
            hits.append(pattern)
    return hits


def check_boundaries(text: str, context: dict | None = None) -> BoundaryDecision:
    """Return the first enabled boundary rule that fires.

    Unknown-medication handling is special-cased: rather than relying on a phrase list
    alone, the caller may pass ``context["known_medications"]`` and
    ``context["mentions_medication"]``. If the user names something about a medicine
    that is not on their confirmed list, the correct behaviour is a clarification
    ("which one do you mean?") rather than a confident explanation of the wrong drug.
    """
    context = context or {}
    lowered = (text or "").lower().strip()

    if not lowered:
        return BoundaryDecision()

    for rule in RULES.of_kind("boundary"):
        hits = _matches(rule, lowered)
        if hits:
            return BoundaryDecision(
                triggered=True,
                reason=rule.reason,
                patient_message=rule.patient_message,
                rule_id=rule.id,
                sources=list(rule.sources),
                matched=hits,
                redirect=rule.redirect,
                offer_question=rule.offer_question,
            )

    # Ungrounded medicine reference: the user asks about a drug, but the app has not
    # confirmed which one. M2 requires clarification, never a guess.
    if context.get("mentions_unknowable_medication"):
        return BoundaryDecision(
            triggered=True,
            reason="A medicine was mentioned that is not confirmed on this profile",
            patient_message=(
                "I can only explain medicines that are already confirmed on your "
                "plan, and I could not match that name to one. I do not want to guess "
                "and describe the wrong medicine. A pharmacist can identify it for "
                "you - would you like to add it to your questions for them?"
            ),
            rule_id="boundary_unknown_medication",
            sources=[],
            matched=["unmatched_medication_reference"],
            redirect="pharmacist",
            offer_question=True,
        )

    return BoundaryDecision()
