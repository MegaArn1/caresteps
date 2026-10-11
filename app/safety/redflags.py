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


# Words that turn a symptom mention into a statement that the symptom is ABSENT.
# These PRECEDE the symptom: "no chest pain", "without weakness".
NEGATIONS = (
    "no ", "not ", "n't ", "without ", "never ", "denies ", "denied ",
    "free of ", "free from ", "ruled out ", "negative for ", "nil ",
    "none ", "absence of ",
)

# Words that FOLLOW the symptom and mark it as over: "the seizure resolved",
# "the bleeding has stopped". Kept separate from NEGATIONS because they sit on the
# other side of the phrase, and searching for them backwards finds nothing.
RESOLVED_SUFFIXES = (
    " resolved", " has resolved", " stopped", " has stopped", " settled",
    " is over", " went away", " has gone", " cleared up", " no longer",
)

# Continuation phrases that LOOK like negations but mean the problem is ONGOING.
# "the bleeding will not stop" is an emergency, not a denial - but a naive scan for
# "not " reads it as one and would have silenced a genuine alarm. These patterns are
# tested BEFORE the negation list, so they win.
CONTINUATION = (
    "will not stop", "won't stop", "wont stop", "not stopping", "does not stop",
    "doesn't stop", "cannot stop", "can't stop", "cant stop", "unable to stop",
    "not easing", "not getting better", "not improving", "no better",
)

# Hedges that point the OTHER way: "not sure if it is chest pain" is a live concern,
# not a denial. When one of these follows the negation, the match counts as real.
UNCERTAINTY = (
    "sure", "certain", "really", "sure if", "sure whether", "sure about",
    "sure what", "sure that",
)

# How far back to look for a negation. Wide enough for "I have not had any chest
# pain today" (30 chars), narrow enough that an unrelated denial earlier in a long
# message does not suppress a later genuine symptom.
NEGATION_WINDOW = 30

# How far forward to look for a resolution marker. Shorter than the backward window,
# because "resolved"/"stopped" sit immediately after the symptom and a long lookahead
# would start catching the next clause.
RESOLUTION_WINDOW = 24
CLAUSE_BREAKS = (".", ",", ";", " but ", " however ", " although ", " though ", " yet ")


def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """Is the phrase being denied or reported as over, rather than currently present?

    This exists because per-rule ``exclude_patterns`` kept failing. Every time a new
    emergency rule was added without an exclusion list, a plain denial ("no heavy
    bleeding", "I did not have a seizure") fired the alarm. A false alarm is the most
    harmful failure this screen can have: it teaches the user to ignore the alarm, and
    the next one may be real.

    Putting the check HERE rather than in each rule's data means a rule added later
    cannot reintroduce the bug by omission, and rule authors do not have to enumerate
    every way English negates a symptom.

    Both directions are checked. Negation usually precedes the symptom, but a resolved
    symptom is marked by what FOLLOWS it ("the seizure resolved", "the bleeding has
    stopped"), and a backward-only search misses that entirely.
    """
    # --- look backwards for a preceding negation -----------------------------
    window = text[max(0, match_start - NEGATION_WINDOW):match_start]

    # Only consider the part after the last clause boundary, so a denial in an earlier
    # clause does not suppress a genuine symptom in this one.
    for brk in CLAUSE_BREAKS:
        if brk in window:
            window = window.rsplit(brk, 1)[-1]

    # Continuation wins over negation. Checked first, because every continuation phrase
    # contains a negation token and would otherwise be read as one.
    tail_full = text[match_start:]
    if any(c in tail_full[:60] for c in CONTINUATION):
        return False

    for neg in NEGATIONS:
        idx = window.rfind(neg)
        if idx == -1:
            continue
        # "not sure if it is chest pain" is uncertainty, not reassurance. Treat the
        # match as real.
        after = window[idx + len(neg):]
        if any(after.lstrip().startswith(u) for u in UNCERTAINTY):
            return False
        return True

    # --- look forwards for a resolution marker -------------------------------
    tail = text[match_end:match_end + RESOLUTION_WINDOW]
    for brk in CLAUSE_BREAKS:
        if brk in tail:
            tail = tail.split(brk, 1)[0]
    return any(suffix in tail for suffix in RESOLVED_SUFFIXES)


def _matches(rule: Rule, text: str) -> list[str]:
    hits = []
    for pattern in rule.patterns:
        start = text.find(pattern)
        if start == -1:
            continue
        # Rule-level exclusions are kept for cases a general negation check cannot
        # express, such as quoting a phrase in an unrelated context.
        if rule.exclude_patterns and any(ex in text for ex in rule.exclude_patterns):
            continue
        if _is_negated(text, start, start + len(pattern)):
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
