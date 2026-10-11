"""Degraded mode - the app without a model.

This module is the reason the prototype can be demoed on a hostile network. It is not
a stub and it is not a "sorry, unavailable" page. It is a working, rules-driven
conversation layer that handles the main path, and it says plainly which parts of the
app are unavailable rather than inventing a substitute.

The design commitment (M6): when the model fails, records, viewing and the fixed
emergency-help path must all still work. So this module can:

* answer the common structured requests from rules alone,
* return stats and summaries, which never needed a model,
* recognise a barrier and route it,
* and, where it genuinely cannot help, say so and point at a human.

What it must NEVER do is generate a plausible medical explanation from nothing. The
``UNAVAILABLE_MESSAGE`` is deliberately unhelpful about medicine: explaining a drug
badly is worse than declining to explain it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNAVAILABLE_MESSAGE = (
    "The explanation feature is not available at the moment, so I cannot look up "
    "what a medicine is for right now. I can still save your records, show your "
    "history, and prepare your questions. Please ask your pharmacist or doctor if you "
    "need an answer about a medicine today."
)


@dataclass
class DegradedReply:
    text: str
    payload: dict = field(default_factory=dict)
    mode: str = "degraded"
    handled_intent: str = "unknown"


# Intents that can be served without any model at all, because they were always
# deterministic. Keeping this list explicit documents the guarantee.
MODEL_FREE_INTENTS = {
    "record_reading",
    "record_medication",
    "view_trends",
    "build_summary",
    "view_plan",
    "help_emergency",
    "barrier",
    "unknown",
}


def classify_intent(text: str) -> str:
    """A small, transparent keyword router.

    Deliberately crude. A clever classifier here would create the impression that the
    degraded path understands language as well as the model does, which would be
    misleading. It handles the phrases the demo actually uses and admits ignorance
    otherwise.
    """
    t = (text or "").lower()

    # Ordering carries meaning here, and one ordering is load-bearing.
    #
    # `barrier` must be checked BEFORE `record_reading`. "I keep forgetting to write
    # down my readings" describes a difficulty, and the word "readings" contains
    # "reading" - so checking the routine intent first swallows it and answers a
    # question nobody asked. A difficulty is also the hardest thing for this user to
    # express, so when a message contains both, routing to the difficulty is the
    # higher-value reading. Belt and braces: `record_reading` additionally requires an
    # actual digit, so prose ABOUT readings cannot be mistaken for a reading.

    # 1. Preparing for the appointment.
    if any(k in t for k in ("summary", "appointment", "prepare for my visit", "print")):
        return "build_summary"

    # 2. A difficulty. The product's core, and checked early for the reason above.
    if any(
        k in t
        for k in (
            "forgot", "forget", "hard to", "hard for me", "difficult", "not sure why",
            "worried", "running out", "running low", "nearly out", "almost out",
            "ran out", "don't know what", "do not know what", "not sure what",
            "confus", "trouble", "struggl", "don't understand", "do not understand",
        )
    ):
        return "barrier"

    # 3. Preparing to talk to a professional. This is the app's stated purpose, so it
    #    must never fall through to "I did not understand".
    if any(k in t for k in ("questions for my doctor", "questions for the doctor",
                            "ask my doctor", "ask the doctor", "help me tell",
                            "tell my doctor", "tell the doctor", "add a question",
                            "add to my questions", "pharmacist")):
        return "build_summary"

    # 4. Looking at the numbers.
    if any(k in t for k in ("trend", "average", "last week", "last month",
                            "how am i doing", "chart", "my numbers", "see my")):
        return "view_trends"

    # 4. Looking at the plan.
    if any(k in t for k in ("my plan", "what am i supposed to", "my medicines",
                            "show my", "what do i take")):
        return "view_plan"

    # 5. Recording a reading. Requires a digit, deliberately.
    if any(c.isdigit() for c in t) and any(
        k in t for k in ("blood pressure", "bp", "systolic", "diastolic",
                         "reading", "mmhg", " over ")
    ):
        return "record_reading"

    # 6. Reporting a medication state.
    if any(k in t for k in ("took my", "taken my", "missed my", "my tablet", "my pill",
                            "did not take", "didn't take", "i took", "not taken")):
        return "record_medication"

    return "unknown"


def _extract_bp_numbers(text: str) -> tuple[int | None, int | None]:
    """Pull two plausible BP numbers out of free text.

    Returns ``(None, None)`` when it is not confident, so the caller asks instead of
    guessing. Never picks a single number and assumes the other.
    """
    import re

    nums = [int(n) for n in re.findall(r"\b(\d{2,3})\b", text or "")]
    # A pulse value is often present too; the two largest plausible BP numbers are
    # the best available guess, and the result is always shown for confirmation.
    candidates = [n for n in nums if 40 <= n <= 300]
    if len(candidates) < 2:
        return None, None
    top = max(candidates)
    rest = [n for n in candidates if n != top]
    bottom = max(rest) if rest else None
    if bottom is None or top <= bottom:
        return None, None
    return top, bottom


def reply(
    text: str,
    context: dict | None = None,
    reason: str | None = None,
) -> DegradedReply:
    """Produce a rules-only response.

    ``context`` may carry ``profile``, ``stats``, ``medications`` and ``drafts`` from
    the route handler. Nothing here reaches the network.
    """
    context = context or {}
    intent = classify_intent(text)
    prefix = ""
    if reason:
        # Say why, once, briefly. Repeated apology is noise.
        prefix = f"({reason}) "

    if intent == "record_reading":
        sys_v, dia_v = _extract_bp_numbers(text)
        if sys_v and dia_v:
            return DegradedReply(
                text=(
                    f"{prefix}I can save that. You said {sys_v} over {dia_v}. "
                    "Is that right?"
                ),
                payload={
                    "kind": "reading_draft",
                    "systolic": sys_v,
                    "diastolic": dia_v,
                    "needs_confirmation": True,
                    "mode_note": "Numbers were read from your message. Please check them.",
                },
                handled_intent=intent,
            )
        return DegradedReply(
            text=(
                f"{prefix}I can save that. What were the two numbers on the screen - "
                "the top one and the bottom one? You can also use the record button."
            ),
            payload={"kind": "ask_reading", "mode_note": "Nothing saved yet."},
            handled_intent=intent,
        )

    if intent == "record_medication":
        return DegradedReply(
            text=(
                f"{prefix}I can save that. Did you take it, not take it, or are you "
                "not sure? You can answer with the buttons below."
            ),
            payload={
                "kind": "medication_choice",
                "options": [
                    {"id": "taken", "label": "I took it"},
                    {"id": "not_taken", "label": "I did not take it"},
                    {"id": "unsure", "label": "I am not sure"},
                    {"id": "skip", "label": "Rather not say"},
                ],
            },
            handled_intent=intent,
        )

    if intent == "view_trends":
        stats_bundle = context.get("stats")
        if not stats_bundle:
            return DegradedReply(
                text=f"{prefix}Let me open your recorded numbers.",
                payload={"kind": "open_trends"},
                handled_intent=intent,
            )
        p = stats_bundle["readings"]
        if not p["sufficient"]:
            return DegradedReply(
                text=f"{prefix}{p['note']}",
                payload={"kind": "stats_card", "stats": stats_bundle},
                handled_intent=intent,
            )
        return DegradedReply(
            text=(
                f"{prefix}In the last {stats_bundle['period_days']} days there are "
                f"{p['n']} readings. The recorded average is {p['mean_systolic']} over "
                f"{p['mean_diastolic']}. {p['note']} This describes what was recorded; "
                "it does not explain why."
            ),
            payload={"kind": "stats_card", "stats": stats_bundle},
            handled_intent=intent,
        )

    if intent == "build_summary":
        return DegradedReply(
            text=(
                f"{prefix}Let me put your summary together. You will be able to read it "
                "and remove anything you do not want to share before you print it."
            ),
            payload={"kind": "open_summary"},
            handled_intent=intent,
        )

    if intent == "view_plan":
        plan = context.get("plan") or []
        meds = context.get("medications") or []
        if not plan and not meds:
            return DegradedReply(
                text=(
                    f"{prefix}I do not have a plan recorded for you. If you have a "
                    "written plan from your doctor, it is worth keeping it handy."
                ),
                payload={"kind": "plan_card", "plan": [], "medications": []},
                handled_intent=intent,
            )
        lines = [f"- {p['instruction']} (source: {p['source_label']})" for p in plan]
        if meds:
            lines.append("")
            lines.append("Medicines on file: " + ", ".join(m["name"] for m in meds))
        return DegradedReply(
            text=f"{prefix}Here is what is on your plan:\n" + "\n".join(lines),
            payload={"kind": "plan_card", "plan": plan, "medications": meds},
            handled_intent=intent,
        )

    if intent == "barrier":
        # Even without a model, the differentiator still works - because it was never
        # the model's job. It is a question plus a routing table.
        return DegradedReply(
            text=(
                f"{prefix}Thank you for saying. Which of these is closest? You can "
                "also skip."
            ),
            payload={
                "kind": "barrier_choice",
                "options": [
                    {"id": "forgot", "label": "I forgot"},
                    {"id": "difficulty_using", "label": "It is hard to do"},
                    {"id": "unclear_purpose", "label": "I do not know what it is for"},
                    {"id": "worried_side_effect", "label": "It worries me"},
                    {"id": "running_out", "label": "I am running out"},
                    {"id": "declined_to_say", "label": "Rather not say"},
                ],
            },
            handled_intent=intent,
        )

    return DegradedReply(
        text=(
            f"{prefix}I want to help, but I could not tell what you were asking, and "
            "the part of me that understands free text is not working right now. "
            "You can use the buttons on this page, look at your history, or prepare "
            "your questions. If it is about a medicine and you need an answer today, "
            "please ask your pharmacist."
        ),
        payload={
            "kind": "degraded_unknown",
            "shortcuts": [
                {"id": "record_reading", "label": "Record a reading"},
                {"id": "open_trends", "label": "See my numbers"},
                {"id": "open_summary", "label": "Prepare for my appointment"},
            ],
        },
        handled_intent=intent,
    )


def summarise_degraded() -> dict:
    """Describe what still works, for the UI banner and the evaluation notes."""
    return {
        "available": [
            "Record and confirm a blood pressure reading",
            "Report medication status in four separate states",
            "Record an execution difficulty and choose a matching support",
            "View computed statistics with sample size and gaps",
            "Preview, edit and print a visit summary",
            "The emergency help path, with the verified local number",
        ],
        "unavailable": [
            "Explaining what a medicine is for (knowledge lookup needs the model layer)",
            "Understanding free-text phrasing outside the phrases listed above",
            "Drafting the summary introduction in natural language",
        ],
        "guarantee": (
            "Nothing is generated from model memory in this mode. Where the app cannot "
            "help, it says so rather than substituting a guess."
        ),
    }
