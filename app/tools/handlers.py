"""Server-side execution of tool calls.

Every handler:
  1. receives arguments that were *validated against the JSON Schema* by the caller,
  2. re-validates anything safety-relevant on its own (a schema says "this is a
     string"; it cannot say "this is not a dose suggestion"),
  3. returns a ``ToolResult`` describing what happened, and
  4. never raises to the model. A failure becomes ``status="error"`` with a message
     the model can relay honestly ("I could not save that"), which is what M6 requires
     for the write-failure path.

Nothing here interpolates model output into SQL. All database access goes through
``repository``, which uses parameterised statements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import repository as repo
from .. import stats as stats_mod
from .contracts import TOOL_SCHEMAS


@dataclass
class ToolContext:
    """Everything a handler is allowed to know about the current turn."""

    conn: Any
    user_id: str
    session_id: str
    # Session-scoped drafts produced by prepare_* and consumed by confirm_*.
    # Held in memory so an abandoned draft simply disappears.
    drafts: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    status: str  # ok | refused | error
    data: dict = field(default_factory=dict)
    message: str = ""
    source_ids: list[str] = field(default_factory=list)
    rule_version: str | None = None

    def to_payload(self) -> dict:
        return {
            "status": self.status,
            "data": self.data,
            "message": self.message,
            "source_ids": self.source_ids,
        }

    def as_tool_message(self) -> str:
        """Serialise for the model, compactly.

        Numbers are passed through as JSON rather than re-worded, so the model cannot
        drift them. ``status='error'`` is included deliberately: it is what lets the
        model say "that did not save" instead of claiming success.
        """
        return json.dumps(self.to_payload(), default=str)


# ------------------------------------------------------------------- helpers


def _err(message: str, **data) -> ToolResult:
    return ToolResult(status="error", message=message, data=data)


def _ok(message: str = "", **data) -> ToolResult:
    return ToolResult(status="ok", message=message, data=data)


def _require(args: dict, key: str) -> Any:
    value = args.get(key)
    if value is None or value == "":
        raise ValueError(f"'{key}' is required")
    return value


# ------------------------------------------------------------------- handlers


def h_get_care_plan(ctx: ToolContext, args: dict) -> ToolResult:
    plan = repo.list_care_plan(ctx.conn, ctx.user_id)
    meds = repo.list_medications(ctx.conn, ctx.user_id)

    plan_out = []
    for p in plan:
        plan_out.append(
            {
                "id": p["id"],
                "instruction": p["instruction"],
                "source_type": p["source_type"],
                "source_label": p["source_label"],
                "confirmed_by_user": bool(p["verified_by_user"]),
                "team_checked": bool(p["verified_by_team"]),
                "clinician_reviewed": bool(p["reviewed_by_clinician"]),
                "is_simulated": bool(p["is_simulated"]),
                "target": (
                    {
                        "systolic": p["target_systolic"],
                        "diastolic": p["target_diastolic"],
                        "source": p["target_source"],
                    }
                    if p["target_systolic"] or p["target_diastolic"]
                    else None
                ),
            }
        )

    med_out = []
    for m in meds:
        med_out.append(
            {
                "id": m["id"],
                "name": m["name"],
                "generic_name": m["generic_name"],
                "confirmed_by_user": bool(m["confirmed_by_user"]),
                "plan_instruction": m["plan_instruction"],
                "has_explanation": bool(m["education_id"]),
            }
        )

    if not plan_out and not med_out:
        return _ok(
            "No care plan is recorded for this user. Do not assume one exists.",
            plan=[], medications=[], note="no_plan_recorded"
        )

    # A deliberate caution, so the model does not over-read "confirmed".
    return _ok(
        "This is the recorded plan, with its source. A user-confirmed name does not "
        "mean the drug information has been clinically reviewed.",
        plan=plan_out,
        medications=med_out,
    )


def h_prepare_reading(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        draft = repo.prepare_reading(
            user_id=ctx.user_id,
            systolic=args.get("systolic"),
            diastolic=args.get("diastolic"),
            measured_at=args.get("measured_at") or repo.now_iso(),
            pulse=args.get("pulse"),
            user_feeling=args.get("user_feeling"),
            note=args.get("note"),
        )
    except repo.ValidationError as exc:
        return _err(exc.message, field=exc.field)

    key = repo.new_id("draft")
    ctx.drafts[key] = {"kind": "reading", "draft": draft}

    return _ok(
        "Draft prepared. Nothing has been saved yet. Show the user the numbers and "
        "ask them to confirm before saving.",
        draft_id=key,
        draft=draft,
        requires_confirmation=True,
    )


def h_prepare_medication_report(ctx: ToolContext, args: dict) -> ToolResult:
    status = args.get("status")
    if status == "unrecorded":
        # Belt and braces. The schema already excludes it; the handler says why.
        return _err(
            "'unrecorded' cannot be reported by a user - it is derived from a missing "
            "entry. Ask the user what actually happened instead.",
            field="status",
        )
    if status not in {"taken", "not_taken", "unsure"}:
        return _err(f"Unsupported status: {status}", field="status")

    medication_id = None
    matched = None
    name = (args.get("medication_name") or "").strip()
    if name:
        med = repo.find_medication_by_name(ctx.conn, ctx.user_id, name)
        if med:
            medication_id = med["id"]
            matched = med["name"]
        else:
            # Names that do not match are NOT guessed at. The app asks.
            return _err(
                f"I could not match '{name}' to a medicine on the confirmed list. Ask "
                "the user which medicine they mean rather than choosing one.",
                field="medication_name",
                failed_match=name,
            )

    draft = {
        "status": status,
        "medication_id": medication_id,
        "medication_name": matched,
        "scheduled_for": args.get("scheduled_for"),
        "note": args.get("note"),
        "reported_at": repo.now_iso(),
    }
    key = repo.new_id("draft")
    ctx.drafts[key] = {"kind": "medication_report", "draft": draft}

    return _ok(
        "Draft prepared. Nothing saved yet. Confirm with the user first.",
        draft_id=key,
        draft=draft,
        requires_confirmation=True,
    )


def h_confirm_draft(ctx: ToolContext, args: dict) -> ToolResult:
    """Persist a previously prepared draft.

    Not exposed to the model, in the sense that the model never receives a
    ``draft_id`` it can use without the UI having shown the draft. The handler still
    validates that the draft exists, so a fabricated id fails safely.
    """
    draft_id = args.get("draft_id")
    entry = ctx.drafts.get(draft_id)
    if not entry:
        return _err(
            "That draft is no longer available. Prepare it again.",
            field="draft_id",
        )

    if entry["kind"] == "reading":
        try:
            result = repo.confirm_reading(
                ctx.conn, ctx.user_id, entry["draft"],
                is_simulated=True,
            )
        except repo.ValidationError as exc:
            return _err(exc.message, field=exc.field)
        ctx.drafts.pop(draft_id, None)
        if result["deduplicated"]:
            return _ok(
                "This reading was already saved, so it was not counted twice.",
                reading_id=result["id"],
                deduplicated=True,
            )
        return _ok("Saved.", reading_id=result["id"], deduplicated=False)

    if entry["kind"] == "medication_report":
        d = entry["draft"]
        try:
            rid = repo.record_medication_report(
                ctx.conn, ctx.user_id,
                status=d["status"],
                medication_id=d["medication_id"],
                scheduled_for=d.get("scheduled_for"),
                reported_at=d.get("reported_at"),
                note=d.get("note"),
                is_backfilled=bool(args.get("is_backfilled")),
            )
        except repo.ValidationError as exc:
            return _err(exc.message, field=exc.field)
        ctx.drafts.pop(draft_id, None)
        return _ok("Saved.", report_id=rid)

    return _err("Unknown draft type.")


def h_retrieve_education(ctx: ToolContext, args: dict) -> ToolResult:
    topic = _require(args, "topic")
    subject = args.get("subject")

    allowed = {
        "medication_purpose", "how_to_measure", "when_to_seek_help", "adherence_support"
    }
    if topic not in allowed:
        return _err(f"Unsupported topic: {topic}", field="topic")

    facts = repo.search_facts(ctx.conn, topic=topic, subject=subject, limit=8)

    if not facts:
        # The empty result is itself the important output. The model is told, in the
        # tool response, that it must not fill the gap from memory.
        return ToolResult(
            status="ok",
            message=(
                "No vetted entry matched. Tell the user you cannot answer this "
                "reliably from the information you have, and offer to add it to their "
                "questions. Do NOT answer from general knowledge."
            ),
            data={"facts": [], "nothing_found": True},
        )

    out = []
    for f in facts:
        out.append(
            {
                "fact_id": f["id"],
                "statement": f["statement"],
                "applies_to": f["applies_to"],
                "source_id": f["source_id"],
                "source_title": f["source_title"],
                "publisher": f["publisher"],
                "url": f["source_url"],
                "retrieved_at": f["source_retrieved_at"],
                "review_state": f["review_state"],
                "source_review_state": f["source_review"],
            }
        )

    return ToolResult(
        status="ok",
        message=(
            "Use only these statements, and cite the source when you explain. Do not "
            "extend them with dosing, missed-dose or stopping advice."
        ),
        data={"facts": out, "nothing_found": False},
        source_ids=[f["source_id"] for f in facts],
    )


def h_record_barrier(ctx: ToolContext, args: dict) -> ToolResult:
    words = args.get("user_words")
    if not words or not str(words).strip():
        return _err("The user's own words are required.", field="user_words")

    category = args.get("category")
    confirmed = bool(args.get("category_confirmed"))

    details = []
    if category and not confirmed:
        details.append(
            "Stored as a PROPOSAL, not a confirmed fact. Ask the user to confirm the "
            "category before treating it as settled."
        )
    if category and confirmed:
        details.append("Stored as confirmed by the user.")

    try:
        bid = repo.record_barrier(
            ctx.conn, ctx.user_id,
            user_words=str(words),
            category=category,
            category_confirmed=confirmed,
            proposed_by="user" if confirmed else "model",
            related_event=args.get("related_event"),
        )
    except repo.ValidationError as exc:
        return _err(exc.message, field=exc.field)

    support_options = _support_options_for(category if confirmed else None)
    return _ok(
        "Saved." + (" " + " ".join(details) if details else ""),
        barrier_id=bid,
        category=category,
        category_confirmed=confirmed,
        support_options=support_options,
    )


# Each confirmed barrier category maps to a DIFFERENT support. This table is the
# product's differentiator expressed as code: the same missing record becomes a
# different next step depending on what the patient says.
SUPPORT_BY_CATEGORY: dict[str, list[dict]] = {
    "forgot": [
        {"id": "backfill", "title": "Fill in the days you remember", "basis": "user_choice"},
        {"id": "change_reminder", "title": "Choose a better time for the reminder", "basis": "user_choice"},
    ],
    "difficulty_using": [
        {"id": "simpler_entry", "title": "Use the shorter entry form", "basis": "user_choice"},
        {"id": "family_help", "title": "Have someone help with the app", "basis": "user_choice"},
    ],
    "unclear_purpose": [
        {"id": "explain_medicine", "title": "Read what this medicine is for", "basis": "education"},
        {"id": "ask_pharmacist", "title": "Add a question for the pharmacist", "basis": "user_choice"},
    ],
    "worried_side_effect": [
        {"id": "record_concern", "title": "Write down what you noticed and when", "basis": "user_choice"},
        {"id": "ask_doctor", "title": "Add a question for the doctor", "basis": "user_choice"},
    ],
    "running_out": [
        {"id": "check_supply", "title": "Note how many are left", "basis": "user_choice"},
        {"id": "refill_plan", "title": "Ask about your next repeat prescription", "basis": "user_choice"},
    ],
    "declined_to_say": [
        {"id": "park", "title": "Leave this for now", "basis": "user_choice"},
    ],
    "other": [
        {"id": "free_text", "title": "Say more in your own words", "basis": "user_choice"},
    ],
}


def _support_options_for(category: str | None) -> list[dict]:
    if not category:
        return [
            {"id": "confirm_category", "title": "Confirm what kind of difficulty this was", "basis": "user_choice"},
        ]
    return SUPPORT_BY_CATEGORY.get(
        category, SUPPORT_BY_CATEGORY["other"]
    )


def h_get_period_stats(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        days = int(args.get("days", 14))
    except (TypeError, ValueError):
        return _err("'days' must be a whole number.", field="days")
    days = max(7, min(90, days))

    bundle = stats_mod.build_period_stats(ctx.conn, ctx.user_id, days=days)
    return _ok(
        "These are the computed numbers. Report them as given and show the number of "
        "readings they are based on. Do not compute anything yourself and do not "
        "describe a change as caused by anything.",
        stats=bundle,
    )


def h_get_recent_activity(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        days = int(args.get("days", 7))
    except (TypeError, ValueError):
        return _err("'days' must be a whole number.", field="days")
    days = max(1, min(60, days))

    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days - 1)

    readings = [
        r for r in repo.list_readings(ctx.conn, ctx.user_id, days=days)
    ]
    reports = repo.list_medication_reports(ctx.conn, ctx.user_id, days=days)
    unrecorded = repo.derive_unrecorded(
        ctx.conn, ctx.user_id, start.isoformat(), end.isoformat()
    )
    open_barriers = repo.due_followups(ctx.conn, ctx.user_id)
    recent_resolved = [
        b for b in repo.list_barriers(ctx.conn, ctx.user_id, status="resolved")
        if b.get("resolved_at") and b["resolved_at"][:10] >= start.isoformat()
    ]

    return _ok(
        "Use this to notice a gap worth asking about and to follow up on something "
        "the user raised before. Days listed under 'unrecorded_days' have NO record "
        "either way - you must not describe them as days the medicine was missed.",
        days=days,
        window={"from": start.isoformat(), "to": end.isoformat()},
        readings_count=len(readings),
        latest_reading=(
            {k: readings[0][k] for k in ("systolic", "diastolic", "measured_at")}
            if readings else None
        ),
        medication_reports=[
            {"status": r["status"], "reported_at": r["reported_at"], "backfilled": bool(r["is_backfilled"])}
            for r in reports
        ],
        unrecorded_days=[u["scheduled_for"][:10] for u in unrecorded],
        unrecorded_count=len(unrecorded),
        open_difficulties=[
            {
                "id": b["id"],
                "user_words": b["user_words"],
                "category": b["category"],
                "category_confirmed": bool(b["category_confirmed"]),
                "raised_on": b["created_at"][:10],
            }
            for b in open_barriers
        ],
        recently_resolved=[
            {"user_words": b["user_words"], "resolved_on": (b["resolved_at"] or "")[:10]}
            for b in recent_resolved
        ],
        caution=(
            "Do not re-raise anything under 'recently_resolved'. Do not treat an "
            "unrecorded day as a missed dose."
        ),
    )


def h_set_reminder_preference(ctx: ToolContext, args: dict) -> ToolResult:
    time_str = args.get("reminder_time")
    if not time_str:
        return _err("A time is required.", field="reminder_time")

    before = repo.get_profile(ctx.conn, ctx.user_id) or {}
    try:
        repo.update_preferences(ctx.conn, ctx.user_id, reminder_time=str(time_str))
    except repo.ValidationError as exc:
        return _err(exc.message, field=exc.field)

    return _ok(
        "Updated. This changes when the app asks you to record - it does not change "
        "when or how you take your medicine.",
        reminder_time=time_str,
        previous=before.get("reminder_time"),
        medication_schedule_changed=False,
    )


def h_build_visit_summary(ctx: ToolContext, args: dict) -> ToolResult:
    try:
        days = int(args.get("days", 14))
    except (TypeError, ValueError):
        return _err("'days' must be a whole number.", field="days")
    days = max(7, min(90, days))

    from ..summary import build_summary_facts

    facts = build_summary_facts(ctx.conn, ctx.user_id, days=days)
    return _ok(
        "Draft summary built from stored records only. The user previews, edits and "
        "decides what to keep. Nothing is sent anywhere.",
        summary=facts,
        requires_confirmation=True,
    )


def h_add_question(ctx: ToolContext, args: dict) -> ToolResult:
    text = args.get("text")
    if not text or not str(text).strip():
        return _err("The question cannot be empty.", field="text")
    origin = args.get("origin", "user")
    if origin not in {"user", "barrier", "safety"}:
        origin = "user"
    try:
        qid = repo.add_question(ctx.conn, ctx.user_id, str(text), origin=origin)
    except repo.ValidationError as exc:
        return _err(exc.message, field=exc.field)
    return _ok("Added to the question list.", question_id=qid, text=text)


# --------------------------------------------------------------- the dispatch

_HANDLERS: dict[str, Callable[[ToolContext, dict], ToolResult]] = {
    "get_care_plan": h_get_care_plan,
    "prepare_reading": h_prepare_reading,
    "prepare_medication_report": h_prepare_medication_report,
    "retrieve_education": h_retrieve_education,
    "record_barrier": h_record_barrier,
    "get_period_stats": h_get_period_stats,
    "get_recent_activity": h_get_recent_activity,
    "set_reminder_preference": h_set_reminder_preference,
    "build_visit_summary": h_build_visit_summary,
    "add_question": h_add_question,
}

# Reachable from the UI only - never advertised to the model.
UI_ONLY_HANDLERS = {"confirm_draft": h_confirm_draft}

KNOWN_TOOLS = set(_HANDLERS) | set(UI_ONLY_HANDLERS)


def dispatch(ctx: ToolContext, name: str, args: dict, allow_ui_only: bool = False) -> ToolResult:
    """Execute a tool call by name.

    An unknown name is an error rather than an exception, so a hallucinated tool name
    produces a truthful failure the model can report, instead of a 500.
    """
    if name in UI_ONLY_HANDLERS and not allow_ui_only:
        return _err(
            f"'{name}' is not available. Only a person confirming a draft can save it.",
            tool=name,
        )
    handler = _HANDLERS.get(name)
    if handler is None:
        return _err(f"There is no such tool: '{name}'.", tool=name)
    try:
        return handler(ctx, args or {})
    except repo.ValidationError as exc:
        return _err(exc.message, field=exc.field)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        return _err(f"The tool failed: {type(exc).__name__}")


def schemas_for_model() -> list[dict]:
    """The tool list advertised to the model. Excludes UI-only handlers."""
    return [
        s for s in TOOL_SCHEMAS if s["function"]["name"] in _HANDLERS
    ]


def validate_args(schema_name: str, args: dict) -> tuple[dict, list[str]]:
    """Minimal structural validation used before dispatch.

    Not a full JSON Schema implementation - deliberately. It checks the properties
    that matter for safety (unknown keys, missing required keys, enum membership) and
    leaves the rest to the handlers, which re-validate anything consequential.
    """
    problems: list[str] = []
    for tool in TOOL_SCHEMAS:
        if tool["function"]["name"] != schema_name:
            continue
        spec = tool["function"]["parameters"]
        props = spec.get("properties", {})
        if not isinstance(args, dict):
            return {}, ["Arguments must be an object"]

        for key in spec.get("required", []):
            if key not in args or args[key] is None:
                problems.append(f"Missing required argument '{key}'")

        for key in list(args):
            if key not in props:
                problems.append(f"Unexpected argument '{key}'")
                args.pop(key)

        for key, value in list(args.items()):
            if value is None:
                continue
            constraints = props.get(key, {})
            if "enum" in constraints and value not in constraints["enum"]:
                problems.append(
                    f"'{key}' must be one of {constraints['enum']}, got '{value}'"
                )
            expected = constraints.get("type")
            if expected == "integer" and not isinstance(value, int):
                try:
                    args[key] = int(value)
                except (TypeError, ValueError):
                    problems.append(f"'{key}' must be a whole number")
            elif expected == "boolean" and not isinstance(value, bool):
                problems.append(f"'{key}' must be true or false")
            elif expected == "string" and not isinstance(value, str):
                args[key] = str(value)
        return args, problems
    return args, [f"Unknown tool '{schema_name}'"]
