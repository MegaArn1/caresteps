"""The conversation orchestrator.

Turn structure, in order, with no step skippable:

    1. safety.route()          - deterministic, runs first, verdict is final
    2. build context           - facts the model is allowed to see, from tools
    3. model loop              - tool calls executed server-side, validated, audited
    4. output check            - numbers must match the fact table; sources must exist
    5. persist + return

The ordering is the architecture. If the model ran first, safety would be a suggestion;
because safety runs first and can return without ever calling the model, an emergency
message cannot be delayed or reworded by a language model.

Step 2 is worth dwelling on. The model does not get to *ask* for context it wants and
then act on it; the orchestrator pre-loads the small set of facts relevant to a turn,
and every tool result is filtered through ``_scoped`` so a handler cannot accidentally
leak another user's row.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .. import repository as repo
from ..safety import route as safety_route
from ..safety.rules import RULES, rule_metadata
from ..tools import TOOL_SCHEMAS, ToolContext, dispatch, tool_summary
from ..tools.handlers import schemas_for_model, validate_args
from .degraded import DegradedReply, reply as degraded_reply
from .prompts import SYSTEM_PROMPT, prompt_fingerprint
from .provider import LLMResult, get_provider

MAX_HISTORY_MESSAGES = 12


@dataclass
class TurnResult:
    """What the route handler needs in order to render one turn."""

    text: str
    mode: str  # safety | live | degraded
    agent_mode: str  # "live" | "degraded" - for the badge
    payload: dict = field(default_factory=dict)
    safety: dict | None = None
    tool_calls: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    degraded_reason: str | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "mode": self.mode,
            "agent_mode": self.agent_mode,
            "payload": self.payload,
            "safety": self.safety,
            "tool_calls": self.tool_calls,
            "sources": self.sources,
            "degraded_reason": self.degraded_reason,
            "latency_ms": self.latency_ms,
        }


# --------------------------------------------------------------- output checking

# Patterns that indicate the model has drifted into territory it must not enter.
FORBIDDEN_PATTERNS = [
    (r"\byou should (?:take|stop|skip|start|change|increase|decrease|double)\b",
     "appears to advise a medication change"),
    (r"\b(?:i have|i've|i will) (?:sent|shared|emailed|booked|ordered|contacted|notified)\b",
     "claims to have taken an action outside its ability"),
    (r"\b(?:you are|you're|this is) (?:safe|fine|nothing to worry about|normal)\b",
     "offers reassurance it is not able to give"),
    (r"\b(?:stop|skip) (?:your|the) (?:medication|medicine|tablet|pill)\b",
     "advises stopping medication"),
    (r"\byour (?:medication|medicine) is causing\b",
     "asserts causation between a medicine and a symptom"),
]

# A number with at least two digits, used to cross-check model prose against the
# computed fact table.
_NUMBER_RE = re.compile(r"\b(\d{2,3})\b")


def check_output(text: str, allowed_numbers: set[str], allow_plain: bool = False) -> list[str]:
    """Return a list of problems with the model's prose.

    Two checks:

    * **forbidden phrasing** - a small set of regexes for the specific ways this app
      could cross a line. Crude on purpose: a subtle classifier would be harder to
      audit than five obvious patterns, and the point is to catch the failure loudly.
    * **numeric grounding** - every two-or-three digit number in the prose must appear
      in the numbers the tools actually returned. This catches the classic
      hallucination of a plausible-looking average.

    ``allow_plain`` relaxes the numeric check for turns where no numbers were provided
    and none are expected (for example a pure clarification).
    """
    problems: list[str] = []
    lowered = (text or "").lower()

    for pattern, description in FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            problems.append(description)

    if not allow_plain:
        seen = set(_NUMBER_RE.findall(text or ""))
        unsupported = {n for n in seen if n not in allowed_numbers}
        # A handful of numbers are legitimately not from the fact table: times of day
        # and the emergency number are configured constants. They are in
        # allowed_numbers via the safety context, so anything left is genuinely
        # ungrounded.
        if unsupported:
            problems.append(
                "mentions a number that no tool returned: "
                + ", ".join(sorted(unsupported)[:5])
            )

    return problems


def _collect_numbers(value: Any, into: set[str]) -> None:
    """Walk a tool result and gather every number a model could legitimately cite."""
    if isinstance(value, dict):
        for v in value.values():
            _collect_numbers(v, into)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect_numbers(v, into)
    elif isinstance(value, bool):
        return
    elif isinstance(value, int):
        into.add(str(value))
        # A mean like 142.5 is cited as 142 or 143; both are grounded.
        into.add(str(int(value)))
    elif isinstance(value, float):
        rounded = int(round(value))
        for n in (rounded - 1, rounded, rounded + 1):
            into.add(str(n))


# ------------------------------------------------------------------- the turn


def run_turn(
    conn,
    user_id: str,
    session_id: str,
    message: str,
    ctx_drafts: dict | None = None,
) -> TurnResult:
    """Process one user message end to end."""
    message = (message or "").strip()

    # ---------------------------------------------------------------- 1. safety
    safety_context = _safety_context(conn, user_id, message)
    verdict = safety_route(message, safety_context)

    if verdict.blocks_model:
        repo.audit(
            conn, kind="safety_route", user_id=user_id, session_id=session_id,
            tool_name="safety.route", args={"text": message[:200]},
            result_status="refused" if verdict.action != "clarify" else "ok",
            rule_version=RULES.version,
            detail=f"action={verdict.action} rule={verdict.rule_id}",
            mode="safety",
        )
        payload = _safety_payload(conn, user_id, verdict)

        # A boundary refusal is where a concern would otherwise be lost. Offer the
        # constructive route rather than leaving a dead end.
        if verdict.action == "refuse" and verdict.details.get("offer_question"):
            payload["offer_add_question"] = True

        return TurnResult(
            text=verdict.message or _default_safety_text(verdict),
            mode="safety",
            agent_mode="safety",
            payload=payload,
            safety=verdict.to_dict(),
            sources=verdict.sources,
        )

    # -------------------------------------------------- 2. context + 3. model
    if not get_provider().s.live:
        return _degraded_turn(conn, user_id, session_id, message, ctx_drafts)

    return _live_turn(conn, user_id, session_id, message, ctx_drafts)


def _live_turn(conn, user_id, session_id, message, drafts) -> TurnResult:
    provider = get_provider()
    ctx = ToolContext(
        conn=conn, user_id=user_id, session_id=session_id, drafts=drafts if drafts is not None else {}
    )

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # A compact, factual orientation. Deliberately minimal: the model can call tools
    # for anything more, and giving it less up front means fewer chances to anchor on
    # something stale.
    profile = repo.get_profile(conn, user_id) or {}
    messages.append(
        {
            "role": "system",
            "content": (
                "Current context, for grounding only. Do not read values out of this "
                "unless a tool also returned them.\n"
                + json.dumps(
                    {
                        "display_name": profile.get("display_name"),
                        "age_band": profile.get("age_band"),
                        "reminder_time": profile.get("reminder_time"),
                        "today": repo.today_iso(),
                        "note": "All records for this user are simulated prototype data.",
                    }
                )
            ),
        }
    )

    for m in repo.list_messages(conn, session_id, limit=MAX_HISTORY_MESSAGES):
        if m["role"] in {"user", "assistant"}:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    tool_schemas = schemas_for_model()
    allowed_numbers: set[str] = set()
    # Constants the prose may legitimately contain. Sourced from the rules, not
    # hard-coded here, so the emergency number in prose and the one on the help page
    # cannot diverge.
    for rule in RULES.of_kind("red_flag"):
        for token in re.findall(r"\b(\d{2,4})\b", rule.patient_message or ""):
            allowed_numbers.add(token)

    executed: list[dict] = []
    source_ids: list[str] = []
    total_latency = 0
    final_text = ""

    for round_index in range(provider.s.max_tool_rounds):
        result: LLMResult = provider.complete(messages, tools=tool_schemas)
        total_latency += result.elapsed_ms or 0

        repo.audit(
            conn, kind="llm_call", user_id=user_id, session_id=session_id,
            tool_name=None,
            args={"round": round_index, "messages": len(messages)},
            result_status="ok" if result.ok else "error",
            detail=(result.error or f"finish={result.finish_reason}")[:300],
            mode="live",
        )

        if not result.ok:
            # Mid-conversation failure. If we already have something useful, keep it;
            # otherwise degrade honestly rather than silently returning nothing.
            if executed:
                final_text = _fallback_text_from_tools(executed)
                break
            return _degraded_turn(
                conn, user_id, session_id, message, drafts, reason=result.error
            )

        if not result.wants_tools:
            final_text = result.content
            break

        # Record the assistant's tool-call turn so the provider sees a valid history.
        messages.append(
            {
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.raw_arguments},
                    }
                    for c in result.tool_calls
                ],
            }
        )

        for call in result.tool_calls:
            args, problems = validate_args(call.name, dict(call.arguments))
            if problems:
                tool_result = _error_result(
                    "The request could not be used as sent: " + "; ".join(problems)
                )
            else:
                tool_result = dispatch(ctx, call.name, args)

            if "retrieve_education" in call.name and tool_result.source_ids:
                source_ids.extend(tool_result.source_ids)

            # Everything the tool returned becomes citable numbers.
            _collect_numbers(tool_result.data, allowed_numbers)
            _collect_numbers(tool_result.message, allowed_numbers)

            executed.append(
                {
                    "name": call.name,
                    "args": args,
                    "status": tool_result.status,
                    "message": tool_result.message[:300],
                    # data is kept so _payload_from_tools can surface draft_id
                    # without a second pass over tool results.
                    "data": tool_result.data,
                }
            )

            repo.audit(
                conn, kind="tool_call", user_id=user_id, session_id=session_id,
                tool_name=call.name, args=args,
                result_status=tool_result.status,
                source_ids=tool_result.source_ids,
                rule_version=RULES.version,
                detail=tool_result.message[:200],
                mode="live",
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": tool_result.as_tool_message(),
                }
            )
    else:
        # Loop exhausted without a final answer. Say so rather than passing through a
        # half-finished chain.
        final_text = _fallback_text_from_tools(executed)

    if not final_text:
        final_text = _fallback_text_from_tools(executed)

    # ------------------------------------------------------- 4. output checking
    problems = check_output(final_text, allowed_numbers)
    if problems:
        repo.audit(
            conn, kind="llm_call", user_id=user_id, session_id=session_id,
            tool_name="output_check", result_status="refused",
            detail="; ".join(problems)[:300], mode="live",
        )
        # Replace rather than amend. A model that drifted once is likely to drift
        # again in the repair, and there is an honest fallback available.
        final_text = _grounded_fallback(executed, problems)

    return TurnResult(
        text=final_text,
        mode="live",
        agent_mode="live",
        payload=_payload_from_tools(executed),
        tool_calls=executed,
        sources=sorted(set(source_ids)),
        latency_ms=total_latency or None,
    )


def _error_result(message: str):
    from ..tools import ToolResult

    return ToolResult(status="error", message=message)


def _fallback_text_from_tools(executed: list[dict]) -> str:
    """A truthful sentence built from what tools actually did.

    Used when the model fails part-way. It does not attempt to be a good answer; it
    reports the outcome accurately, which is what M6's "say it failed, do not
    improvise a plausible medical answer" requires.
    """
    if not executed:
        return (
            "Something went wrong before I could finish that. Nothing was changed. "
            "Please try again, or use the buttons on this page."
        )
    ok = [e for e in executed if e["status"] == "ok"]
    if ok:
        names = ", ".join(sorted({e["name"] for e in ok}))
        return (
            "I was not able to finish writing that out, so nothing has been saved "
            f"yet. The app did complete: {names}. Please try again, and tell me if it "
            "keeps happening."
        )
    return (
        "I could not complete that. Nothing was saved. Please try again."
    )


def _grounded_fallback(executed: list[dict], problems: list[str]) -> str:
    """Substitute for prose that failed the output check.

    The replacement names the kind of problem in plain language without repeating the
    offending content. Being visibly less fluent here is acceptable; being smoothly
    wrong is not.
    """
    detail = problems[0] if problems else "an answer I could not verify"
    return (
        "I started to answer that but I could not make it match your records, so I "
        f"have stopped rather than give you something inaccurate. The problem was: {detail}. "
        "I can show you the recorded numbers instead, or add this to your questions "
        "for your doctor or pharmacist."
    )


def _payload_from_tools(executed: list[dict]) -> dict:
    """Surface anything the UI should render alongside the prose.

    The draft_id is forwarded so the confirm button in the chat panel can POST
    it back to /api/chat/confirm without the user having to navigate away.
    """
    payload: dict[str, Any] = {"kind": "text"}
    for e in executed:
        data = e.get("data") or {}
        if e["name"] == "prepare_reading" and e["status"] == "ok":
            payload = {
                "kind": "reading_draft",
                "needs_confirmation": True,
                "draft_id": data.get("draft_id"),
                "draft": data.get("draft"),
            }
        elif e["name"] == "prepare_medication_report" and e["status"] == "ok":
            payload = {
                "kind": "medication_draft",
                "needs_confirmation": True,
                "draft_id": data.get("draft_id"),
                "draft": data.get("draft"),
            }
        elif e["name"] == "record_barrier" and e["status"] == "ok":
            payload = {"kind": "barrier_recorded"}
        elif e["name"] == "add_question" and e["status"] == "ok":
            payload = {"kind": "question_added"}
    return payload


def _degraded_turn(
    conn, user_id, session_id, message, drafts, reason: str | None = None
) -> TurnResult:
    from datetime import date, timedelta

    from .. import stats as stats_mod

    profile = repo.get_profile(conn, user_id)
    end = date.today()
    start = end - timedelta(days=13)
    try:
        bundle = stats_mod.build_period_stats(conn, user_id, days=14)
    except Exception:
        bundle = None

    context = {
        "profile": profile,
        "stats": bundle,
        "plan": repo.list_care_plan(conn, user_id),
        "medications": repo.list_medications(conn, user_id),
    }

    if reason:
        # The user-facing reason is deliberately plain. The technical detail goes to
        # the audit log, not to a 70-year-old on a phone.
        friendly = "The assistant is offline"
    else:
        friendly = "No assistant is connected"

    reply: DegradedReply = degraded_reply(message, context, reason=friendly)

    repo.audit(
        conn, kind="llm_call", user_id=user_id, session_id=session_id,
        tool_name="degraded_router", args={"intent_hint": message[:120]},
        result_status="ok", detail=(reason or "provider not configured")[:200],
        mode="degraded",
    )

    return TurnResult(
        text=reply.text,
        mode="degraded",
        agent_mode="degraded",
        payload=reply.payload,
        degraded_reason=reason or "No model endpoint configured",
    )


def _safety_context(conn, user_id: str, message: str) -> dict:
    """Assemble the small context the safety gates need."""
    meds = repo.list_medications(conn, user_id)
    lowered = (message or "").lower()

    # Is the user ASKING ABOUT a medicine they have not named, so the app would have
    # to guess which one to explain?
    #
    # This must be narrow. An earlier version fired on any bare "my tablet" and
    # therefore refused "I forgot my tablet yesterday" and "I am running out of my
    # tablets" - i.e. it refused the exact behaviour the app exists to support, and
    # mislabelled a supply problem as a drug-identification problem.
    #
    # Two conditions are now required together:
    #   1. an information-seeking phrase about the medicine itself, AND
    #   2. a generic reference to a current medicine, AND
    #   3. no confirmed medicine actually named, AND
    #   4. no adherence/statement marker that means this is a report, not a query.
    generic_refs = (
        "my pill", "my tablet", "my medication", "my medicine",
        "this medicine", "this medication", "this tablet", "this pill",
        "the white one", "the small one",
    )
    seeking_info = (
        "what is", "what are", "what's", "which is", "why am i", "why do i",
        "tell me about", "explain", "what does", "is it for", "what for",
        "do i need", "should i still",
    )
    # Markers that mean the message is a statement about what happened, not a
    # question about what a medicine is. Any of these clears the boundary path.
    report_markers = (
        "forgot", "forget", "missed", "miss", "took", "taken", "did not take",
        "didn't take", "running out", "running low", "nearly out", "almost out",
        "need a refill", "collect", "ran out", "remain", "left", "finished",
    )

    mentions_generic = any(p in lowered for p in generic_refs)
    asks_about_medicine = any(p in lowered for p in seeking_info)
    names_confirmed = any(m["name"].lower() in lowered for m in meds)
    is_report = any(p in lowered for p in report_markers)

    unknowable = (
        mentions_generic
        and asks_about_medicine
        and not names_confirmed
        and not is_report
    )

    return {
        "user_id": user_id,
        "medications": [m["name"] for m in meds],
        "medication_count": len(meds),
        "mentions_unknowable_medication": unknowable,
        "today": repo.today_iso(),
    }


def _safety_payload(conn, user_id: str, verdict) -> dict:
    payload: dict[str, Any] = {"kind": "safety", "action": verdict.action}

    if verdict.action in {"emergency", "urgent_advice"}:
        from .help import emergency_info

        info = emergency_info()
        payload["kind"] = "emergency" if verdict.action == "emergency" else "urgent"
        payload["help"] = info
        payload["can_still_record"] = True

    if verdict.action == "clarify":
        payload["kind"] = "clarify"
        payload["options"] = verdict.details.get("options", [])

    if verdict.action == "refuse":
        payload["kind"] = "boundary"
        payload["redirect"] = verdict.details.get("redirect")

    return payload


def _default_safety_text(verdict) -> str:
    if verdict.action == "emergency":
        return verdict.message or "Please get medical help now."
    if verdict.action == "urgent_advice":
        return verdict.message or "Please contact a doctor soon."
    return verdict.message or "I cannot help with that as asked."


def orchestrator_metadata() -> dict:
    """Everything the trace page needs to describe how this app answers."""
    from ..config import SETTINGS
    from .degraded import summarise_degraded

    return {
        "llm": SETTINGS.llm.describe(),
        "prompt": prompt_fingerprint(),
        "rules": rule_metadata(),
        "tools": tool_summary(),
        "degraded": summarise_degraded(),
        "max_tool_rounds": SETTINGS.llm.max_tool_rounds,
    }
