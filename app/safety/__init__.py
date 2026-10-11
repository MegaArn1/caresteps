"""Deterministic safety routing.

This package runs **before** the language model, every turn, and its verdict is final.
The architecture document claims that ordinary conversation cannot override a rule
output; that claim is implemented here and nowhere else.

Three ordered gates
-------------------
1. ``redflags``  - possible emergency. Highest priority. Nothing may delay it.
2. ``boundaries`` - requests to change medication, unknown drugs, ambiguous input.
3. ``clarify``   - under-specified input that needs a question before anything else.

Order matters and is not configurable at runtime. Red flags beat ordinary Q&A, and
the app must never finish collecting routine data before showing help (M6).
"""

from __future__ import annotations

from .boundaries import BoundaryDecision, check_boundaries
from .clarify import ClarificationDecision, check_clarification
from .redflags import RedFlagDecision, check_red_flags
from .rules import RULES, rule_metadata

__all__ = [
    "BoundaryDecision",
    "ClarificationDecision",
    "RedFlagDecision",
    "RULES",
    "SafetyVerdict",
    "check_boundaries",
    "check_clarification",
    "check_red_flags",
    "route",
    "rule_metadata",
]


class SafetyVerdict:
    """The result of safety routing for one user turn.

    ``action`` is one of:
      * ``emergency``   - show the verified local emergency path now
      * ``urgent_advice`` - advise prompt professional contact
      * ``refuse``      - decline the request, explain the limit, offer the correct route
      * ``clarify``     - ask a question before proceeding
      * ``allow``       - proceed to normal support
    """

    __slots__ = ("action", "reason", "message", "rule_id", "sources", "details")

    def __init__(
        self,
        action: str,
        reason: str = "",
        message: str = "",
        rule_id: str | None = None,
        sources: list[str] | None = None,
        details: dict | None = None,
    ):
        self.action = action
        self.reason = reason
        self.message = message
        self.rule_id = rule_id
        self.sources = sources or []
        self.details = details or {}

    @property
    def blocks_model(self) -> bool:
        """True when the model must not answer this turn at all.

        The model is skipped rather than told to be careful, because a rule that only
        exists in a prompt is not a rule — it is a suggestion.
        """
        return self.action in {"emergency", "urgent_advice", "refuse", "clarify"}

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "reason": self.reason,
            "message": self.message,
            "rule_id": self.rule_id,
            "sources": self.sources,
            "details": self.details,
            "blocks_model": self.blocks_model,
        }


def route(text: str, context: dict | None = None) -> SafetyVerdict:
    """Run all gates in priority order and return the first decisive verdict.

    ``context`` may carry ``user_id``, ``topic`` and any structured fields a rule
    needs. Unknown keys are ignored, so adding a field is not a breaking change.
    """
    context = context or {}

    red = check_red_flags(text, context)
    if red.triggered:
        return SafetyVerdict(
            action="emergency" if red.severity == "emergency" else "urgent_advice",
            reason=red.reason,
            message=red.patient_message,
            rule_id=red.rule_id,
            sources=red.sources,
            details={"matched": red.matched},
        )

    boundary = check_boundaries(text, context)
    if boundary.triggered:
        return SafetyVerdict(
            action="refuse",
            reason=boundary.reason,
            message=boundary.patient_message,
            rule_id=boundary.rule_id,
            sources=boundary.sources,
            details={
                "matched": boundary.matched,
                "redirect": boundary.redirect,
                "offer_question": boundary.offer_question,
            },
        )

    clar = check_clarification(text, context)
    if clar.triggered:
        return SafetyVerdict(
            action="clarify",
            reason=clar.reason,
            message=clar.patient_message,
            rule_id=clar.rule_id,
            sources=clar.sources,
            details={"options": clar.options},
        )

    return SafetyVerdict(action="allow")
