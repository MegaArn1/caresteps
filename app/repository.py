"""The only module permitted to write to the database.

This is a trust property, not a style preference. The architecture claims that the model
cannot write to storage; that claim is true because *nothing* in the LLM or tool layer
executes SQL. Tools call these functions, and these functions validate their inputs.

Every function that creates health data:
  1. validates its arguments and raises ``ValidationError`` on bad input,
  2. stamps provenance (``is_simulated``, confirmation flags),
  3. never silently overwrites history.

Conventions
-----------
* All timestamps are ISO-8601 strings with an explicit offset, produced by ``now_iso``.
* ``new_id`` gives a short sortable-ish identifier; collisions are handled by UNIQUE
  constraints rather than assumed away.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Sequence

from .db import session

# ------------------------------------------------------------------ constants

ADHERENCE_STATUSES = {"taken", "not_taken", "unsure", "unrecorded"}

BARRIER_CATEGORIES = {
    "forgot": "I forgot to record / take it",
    "difficulty_using": "It is hard for me to do it",
    "unclear_purpose": "I do not know what this medicine is for",
    "worried_side_effect": "I am worried it is causing a problem",
    "running_out": "I am running out of it",
    "declined_to_say": "I would rather not say",
    "other": "Something else",
}

# Vital-sign plausibility bounds. Two separate bands, because two separate questions:
#
#   IMPOSSIBLE  - no home monitor produces this. Almost certainly a typo. Still
#                 storable, but the user must confirm.
#   UNUSUAL     - a home monitor can produce this, but it sits outside what most
#                 people see. Worth a second look, nothing more.
#
# Neither band is a clinical judgement and neither blocks saving. This module's job is
# to ask "did you mean this?", never to discard a real reading, never to call a value
# dangerous. See M1: an unusual-but-parseable reading must not be silently dropped just
# because it falls outside a common range.
SYS_IMPOSSIBLE = (40, 300)
DIA_IMPOSSIBLE = (20, 200)
SYS_UNUSUAL = (90, 180)
DIA_UNUSUAL = (50, 110)


class ValidationError(ValueError):
    """Raised when input cannot be accepted. Carries a user-facing message."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field
        self.message = message


# ---------------------------------------------------------------- small helpers


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Internal field names never reach the user. A validation message is read by a
# 70-year-old on a phone, so it says "the top number", not "systolic", and never
# leaks a database column name.
FIELD_LABELS = {
    "systolic": "the top number",
    "diastolic": "the bottom number",
    "pulse": "the pulse",
    "measured_at": "when you took the reading",
    "name": "the name",
    "instruction": "the plan text",
    "text": "the question",
    "user_words": "what you tell us",
    "status": "the answer",
    "medication_id": "the medicine",
    "category": "the reason",
    "reminder_time": "the time",
    "original_id": "that reading",
    "target_source": "where the target came from",
    "age_band": "the age range",
    "display_name": "a name",
}


def field_label(field: str | None) -> str:
    """A patient-readable name for an internal field, or a safe generic fallback."""
    if not field:
        return "that"
    return FIELD_LABELS.get(field, "that value")


def _as_int(value: Any, field: str) -> int:
    label = field_label(field)
    if value is None or value == "":
        raise ValidationError(f"I still need {label}.", field)
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(
            f"I could not read {label} as a number. Please type the digits only.",
            field,
        ) from None
    return n


def _clean(value: Any) -> str:
    return ("" if value is None else str(value)).strip()


# ------------------------------------------------------------------ M0: profile


def get_profile(conn: sqlite3.Connection, user_id: str | None = None) -> dict | None:
    row = (
        conn.execute("SELECT * FROM user_profile WHERE id = ?", (user_id,)).fetchone()
        if user_id
        else conn.execute(
            "SELECT * FROM user_profile ORDER BY created_at LIMIT 1"
        ).fetchone()
    )
    return dict(row) if row else None


def create_profile(
    conn: sqlite3.Connection,
    display_name: str,
    age_band: str,
    language: str = "en",
    reminder_time: str | None = None,
    is_simulated: bool = True,
) -> str:
    name = _clean(display_name)
    if not name:
        raise ValidationError("A display name is required", "display_name")
    if not _clean(age_band):
        raise ValidationError("An age band is required", "age_band")
    pid = new_id("usr")
    conn.execute(
        """INSERT INTO user_profile
           (id, display_name, age_band, language, reminder_time, is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (pid, name, _clean(age_band), _clean(language) or "en",
         _clean(reminder_time) or None, int(is_simulated), now_iso()),
    )
    return pid


def update_preferences(
    conn: sqlite3.Connection,
    user_id: str,
    reminder_time: str | None = None,
    prefers_large_text: bool | None = None,
) -> None:
    """Update interaction preferences only.

    Note the deliberate omission: this cannot touch the medication schedule. M3's
    acceptance criteria require that changing a reminder preference never changes the
    prescribed plan.
    """
    sets, args = [], []
    if reminder_time is not None:
        rt = _clean(reminder_time)
        if rt and not _valid_hhmm(rt):
            raise ValidationError("Time must look like 08:00", "reminder_time")
        sets.append("reminder_time = ?")
        args.append(rt or None)
    if prefers_large_text is not None:
        sets.append("prefers_large_text = ?")
        args.append(int(bool(prefers_large_text)))
    if not sets:
        return
    args.append(user_id)
    conn.execute(f"UPDATE user_profile SET {', '.join(sets)} WHERE id = ?", args)


def _valid_hhmm(value: str) -> bool:
    try:
        h, m = value.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


def list_care_plan(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM care_plan WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_care_plan_item(conn: sqlite3.Connection, plan_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM care_plan WHERE id = ?", (plan_id,)).fetchone()
    return dict(row) if row else None


def add_care_plan_item(
    conn: sqlite3.Connection,
    user_id: str,
    instruction: str,
    source_type: str,
    source_label: str,
    target_systolic: int | None = None,
    target_diastolic: int | None = None,
    target_source: str | None = None,
    verified_by_user: bool = False,
    effective_date: str | None = None,
    notes: str | None = None,
    is_simulated: bool = True,
) -> str:
    text = _clean(instruction)
    if not text:
        raise ValidationError("The plan text cannot be empty", "instruction")
    if source_type not in {
        "demo_fictional", "user_reported", "clinician_given", "app_education"
    }:
        raise ValidationError(f"Unknown source type: {source_type}", "source_type")

    # A personal target with no stated source is not recorded. This is the concrete
    # enforcement of "never invent a personal goal".
    if target_systolic is not None or target_diastolic is not None:
        if not _clean(target_source):
            raise ValidationError(
                "A blood pressure target needs a stated source; leave it empty instead",
                "target_source",
            )

    pid = new_id("plan")
    conn.execute(
        """INSERT INTO care_plan
           (id, user_id, instruction, source_type, source_label, verified_by_user,
            target_systolic, target_diastolic, target_source, effective_date, notes,
            is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, user_id, text, source_type, _clean(source_label),
         int(verified_by_user), target_systolic, target_diastolic,
         _clean(target_source) or None, effective_date, notes,
         int(is_simulated), now_iso()),
    )
    return pid


# --------------------------------------------------------------- M0: medication


def list_medications(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM medication_item WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_medication(conn: sqlite3.Connection, medication_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM medication_item WHERE id = ?", (medication_id,)
    ).fetchone()
    return dict(row) if row else None


def find_medication_by_name(
    conn: sqlite3.Connection, user_id: str, name: str
) -> dict | None:
    """Exact, case-insensitive match against the user's confirmed list.

    Deliberately NOT fuzzy. M2 requires that an ambiguous or unknown name goes to
    clarification rather than being matched to the nearest thing.
    """
    target = _clean(name).lower()
    if not target:
        return None
    for med in list_medications(conn, user_id):
        if med["name"].lower() == target:
            return med
        if (med.get("generic_name") or "").lower() == target:
            return med
    return None


def add_medication(
    conn: sqlite3.Connection,
    user_id: str,
    name: str,
    generic_name: str | None = None,
    plan_instruction: str | None = None,
    plan_source_id: str | None = None,
    education_id: str | None = None,
    confirmed_by_user: bool = False,
    is_simulated: bool = True,
) -> str:
    clean = _clean(name)
    if not clean:
        raise ValidationError("A medicine name is required", "name")
    mid = new_id("med")
    conn.execute(
        """INSERT INTO medication_item
           (id, user_id, name, generic_name, confirmed_by_user, plan_instruction,
            plan_source_id, education_id, is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (mid, user_id, clean, _clean(generic_name) or None, int(confirmed_by_user),
         _clean(plan_instruction) or None, plan_source_id, education_id,
         int(is_simulated), now_iso()),
    )
    return mid


# ----------------------------------------------------------------- M1: readings


def reading_dedupe_key(
    user_id: str, systolic: int, diastolic: int, measured_at: str
) -> str:
    """Stable key for the same logical reading.

    Guards M1's "a repeated submit must not be counted twice" requirement. Keyed on
    the *measurement*, not the moment of entry, so a double-tap and a genuine re-entry
    of the same reading collapse, while two readings a minute apart stay distinct.
    """
    return f"{user_id}|{systolic}|{diastolic}|{measured_at}"


def prepare_reading(
    user_id: str,
    systolic: Any,
    diastolic: Any,
    measured_at: str,
    pulse: Any = None,
    user_feeling: str | None = None,
    note: str | None = None,
    entered_source: str = "manual",
) -> dict:
    """Phase one: validate and describe. Writes NOTHING.

    Returns a draft plus any concerns for the user to confirm. The concern list is
    advisory — it never blocks saving a confirmed real reading.
    """
    sys_v = _as_int(systolic, "systolic")
    dia_v = _as_int(diastolic, "diastolic")

    concerns: list[str] = []
    if not (SYS_IMPOSSIBLE[0] <= sys_v <= SYS_IMPOSSIBLE[1]):
        concerns.append(
            f"The top number {sys_v} is outside what a home monitor can normally show. "
            "Please check it — if it is right, you can still save it."
        )
    if not (DIA_IMPOSSIBLE[0] <= dia_v <= DIA_IMPOSSIBLE[1]):
        concerns.append(
            f"The bottom number {dia_v} is outside what a home monitor can normally "
            "show. Please check it — if it is right, you can still save it."
        )
    # Softer band: unusual but producible. Worth a second look, and no more than that.
    if SYS_IMPOSSIBLE[0] <= sys_v <= SYS_IMPOSSIBLE[1] and not (
        SYS_UNUSUAL[0] <= sys_v <= SYS_UNUSUAL[1]
    ):
        concerns.append(
            f"The top number {sys_v} is unusual for a home reading. Please check the "
            "monitor screen once more — if it is right, you can still save it."
        )
    if DIA_IMPOSSIBLE[0] <= dia_v <= DIA_IMPOSSIBLE[1] and not (
        DIA_UNUSUAL[0] <= dia_v <= DIA_UNUSUAL[1]
    ):
        concerns.append(
            f"The bottom number {dia_v} is unusual for a home reading. Please check "
            "the monitor screen once more — if it is right, you can still save it."
        )
    if sys_v <= dia_v:
        concerns.append(
            "The top number is usually higher than the bottom number. Please check "
            "which was which."
        )
    # A numeric input that is merely unusual is NOT a concern. Only genuine
    # impossibility or an obvious mix-up is surfaced.

    pulse_v = None
    if pulse is not None and _clean(pulse) != "":
        pulse_v = _as_int(pulse, "pulse")
        if not (20 <= pulse_v <= 250):
            concerns.append(
                f"A pulse of {pulse_v} is unusual. Please check it."
            )

    return {
        "systolic": sys_v,
        "diastolic": dia_v,
        "pulse": pulse_v,
        "measured_at": _clean(measured_at) or now_iso(),
        "user_feeling": _clean(user_feeling) or None,
        "note": _clean(note) or None,
        "entered_source": entered_source,
        "concerns": concerns,
        "is_simulated": True,
    }


def confirm_reading(
    conn: sqlite3.Connection, user_id: str, draft: dict, is_simulated: bool = True
) -> dict:
    """Phase two: persist a confirmed draft. Idempotent.

    Returns ``{"id":..., "deduplicated": bool}``.
    """
    sys_v = _as_int(draft.get("systolic"), "systolic")
    dia_v = _as_int(draft.get("diastolic"), "diastolic")
    measured_at = _clean(draft.get("measured_at")) or now_iso()
    key = reading_dedupe_key(user_id, sys_v, dia_v, measured_at)

    existing = conn.execute(
        "SELECT id FROM bp_reading WHERE dedupe_key = ?", (key,)
    ).fetchone()
    if existing:
        return {"id": existing["id"], "deduplicated": True}

    rid = new_id("bp")
    pulse = draft.get("pulse")
    conn.execute(
        """INSERT INTO bp_reading
           (id, user_id, systolic, diastolic, pulse, measured_at, entered_at,
            entered_source, user_feeling, note, status, is_simulated, dedupe_key,
            created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,'confirmed',?,?,?)""",
        (rid, user_id, sys_v, dia_v, int(pulse) if pulse else None, measured_at,
         now_iso(), _clean(draft.get("entered_source")) or "manual",
         draft.get("user_feeling"), draft.get("note"), int(is_simulated), key,
         now_iso()),
    )
    return {"id": rid, "deduplicated": False}


def correct_reading(
    conn: sqlite3.Connection,
    user_id: str,
    original_id: str,
    systolic: int,
    diastolic: int,
    measured_at: str | None = None,
    pulse: int | None = None,
    note: str | None = None,
) -> str:
    """Supersede a reading, keeping the original.

    M1 requires a revision mark rather than a destructive overwrite. The chain is
    walked from the oldest row forward via ``superseded_by``.
    """
    original = conn.execute(
        "SELECT * FROM bp_reading WHERE id = ? AND user_id = ?", (original_id, user_id)
    ).fetchone()
    if not original:
        raise ValidationError("That reading no longer exists", "original_id")

    new_measured = _clean(measured_at) or original["measured_at"]
    draft = {
        "systolic": _as_int(systolic, "systolic"),
        "diastolic": _as_int(diastolic, "diastolic"),
        "measured_at": new_measured,
        "pulse": pulse if pulse is not None else original["pulse"],
        "note": note if note is not None else original["note"],
        "user_feeling": original["user_feeling"],
        "entered_source": "correction",
    }
    key = reading_dedupe_key(
        user_id, draft["systolic"], draft["diastolic"], new_measured
    )
    rid = new_id("bp")
    conn.execute(
        """INSERT INTO bp_reading
           (id, user_id, systolic, diastolic, pulse, measured_at, entered_at,
            entered_source, user_feeling, note, status, corrects, is_simulated,
            dedupe_key, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,'confirmed',?,?,?,?)""",
        (rid, user_id, draft["systolic"], draft["diastolic"], draft["pulse"],
         draft["measured_at"], now_iso(), "correction", draft["user_feeling"],
         draft["note"], original_id, original["is_simulated"], key, now_iso()),
    )
    conn.execute("UPDATE bp_reading SET superseded_by = ? WHERE id = ?", (rid, original_id))
    return rid


def list_readings(
    conn: sqlite3.Connection,
    user_id: str,
    days: int | None = 30,
    include_superseded: bool = False,
) -> list[dict]:
    sql = "SELECT * FROM bp_reading WHERE user_id = ?"
    args: list[Any] = [user_id]
    if not include_superseded:
        sql += " AND superseded_by IS NULL"
    if days:
        cutoff = (datetime.now().astimezone() - timedelta(days=days)).isoformat(
            timespec="seconds"
        )
        sql += " AND measured_at >= ?"
        args.append(cutoff)
    sql += " ORDER BY measured_at DESC"
    return [dict(r) for r in conn.execute(sql, args)]


def get_reading(conn: sqlite3.Connection, reading_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM bp_reading WHERE id = ?", (reading_id,)).fetchone()
    return dict(row) if row else None


def reading_revision_chain(conn: sqlite3.Connection, reading_id: str) -> list[dict]:
    """Walk back to the first record, then forward, so the UI can show history."""
    row = conn.execute("SELECT * FROM bp_reading WHERE id = ?", (reading_id,)).fetchone()
    if not row:
        return []
    seen = {row["id"]}
    chain = [dict(row)]
    # backwards
    cur = row
    while cur["corrects"] and cur["corrects"] not in seen:
        prev = conn.execute(
            "SELECT * FROM bp_reading WHERE id = ?", (cur["corrects"],)
        ).fetchone()
        if not prev:
            break
        seen.add(prev["id"])
        chain.insert(0, dict(prev))
        cur = prev
    # forwards
    cur = row
    while cur["superseded_by"] and cur["superseded_by"] not in seen:
        nxt = conn.execute(
            "SELECT * FROM bp_reading WHERE id = ?", (cur["superseded_by"],)
        ).fetchone()
        if not nxt:
            break
        seen.add(nxt["id"])
        chain.append(dict(nxt))
        cur = nxt
    return chain


# ------------------------------------------------------------------ M2: reports


def record_medication_report(
    conn: sqlite3.Connection,
    user_id: str,
    status: str,
    medication_id: str | None = None,
    scheduled_for: str | None = None,
    reported_at: str | None = None,
    note: str | None = None,
    is_backfilled: bool = False,
    is_simulated: bool = True,
) -> str:
    """Store what the patient reported. Never a clinical judgement."""
    if status not in ADHERENCE_STATUSES:
        raise ValidationError(f"Unknown status: {status}", "status")
    if status == "unrecorded":
        # 'unrecorded' is a statement about our data, not a patient claim. The only
        # legitimate way to create one is the derivation function below.
        raise ValidationError(
            "'unrecorded' is derived from a missing entry and cannot be reported "
            "by the user",
            "status",
        )
    if medication_id:
        med = get_medication(conn, medication_id)
        if not med or med["user_id"] != user_id:
            raise ValidationError("That medicine is not on this profile", "medication_id")

    rid = new_id("mrep")
    conn.execute(
        """INSERT INTO medication_report
           (id, user_id, medication_id, status, is_self_report, is_backfilled,
            scheduled_for, reported_at, note, is_simulated, created_at)
           VALUES (?,?,?,?,1,?,?,?,?,?,?)""",
        (rid, user_id, medication_id, status, int(is_backfilled), scheduled_for,
         _clean(reported_at) or now_iso(), _clean(note) or None, int(is_simulated),
         now_iso()),
    )
    return rid


def derive_unrecorded(
    conn: sqlite3.Connection,
    user_id: str,
    from_date: str,
    to_date: str,
) -> list[dict]:
    """Find plan slots with no report at all.

    Returns synthetic ``unrecorded`` entries with ``is_self_report = 0``. These exist
    precisely so the UI can say "no record" WITHOUT implying "did not take it" — the
    single most important correctness property in this project (M1/M2 acceptance).
    """
    profile = get_profile(conn, user_id)
    if not profile or not profile.get("reminder_time"):
        return []

    reported_days = {
        r["reported_at"][:10]
        for r in conn.execute(
            """SELECT reported_at FROM medication_report
               WHERE user_id = ? AND scheduled_for IS NOT NULL""",
            (user_id,),
        )
    }
    out: list[dict] = []
    day = _parse_date(from_date)
    end = _parse_date(to_date)
    while day <= end:
        iso = day.isoformat()
        if iso not in reported_days:
            out.append(
                {
                    "id": None,
                    "user_id": user_id,
                    "medication_id": None,
                    "status": "unrecorded",
                    "is_self_report": 0,
                    "is_backfilled": 0,
                    "scheduled_for": f"{iso}T{profile['reminder_time']}",
                    "reported_at": None,
                    "derived": True,
                }
            )
        day += timedelta(days=1)
    return out


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value[:10]).date()


def list_medication_reports(
    conn: sqlite3.Connection, user_id: str, days: int | None = 30
) -> list[dict]:
    sql = "SELECT * FROM medication_report WHERE user_id = ?"
    args: list[Any] = [user_id]
    if days:
        cutoff = (datetime.now().astimezone() - timedelta(days=days)).isoformat(
            timespec="seconds"
        )
        sql += " AND reported_at >= ?"
        args.append(cutoff)
    sql += " ORDER BY reported_at DESC"
    return [dict(r) for r in conn.execute(sql, args)]


# -------------------------------------------------------------------- M3: barriers


def record_barrier(
    conn: sqlite3.Connection,
    user_id: str,
    user_words: str,
    category: str | None = None,
    category_confirmed: bool = False,
    proposed_by: str = "rules",
    related_event: str | None = None,
    is_simulated: bool = True,
) -> str:
    """Save what the patient said, and only a *confirmed* category.

    If the user has not confirmed the classification, ``category`` is stored but
    ``category_confirmed`` stays 0. The UI must render those differently. This is the
    mechanism behind "a model's guess must not become a stored fact".
    """
    words = _clean(user_words)
    if not words:
        raise ValidationError("Please say what happened", "user_words")
    if category and category not in BARRIER_CATEGORIES:
        raise ValidationError(f"Unknown category: {category}", "category")
    if category and not category_confirmed:
        # Storing an unconfirmed category is allowed, but only as a proposal.
        proposed_by = proposed_by or "model"

    bid = new_id("bar")
    conn.execute(
        """INSERT INTO barrier_event
           (id, user_id, user_words, category, category_confirmed, proposed_by,
            related_event, status, is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?,'open',?,?)""",
        (bid, user_id, words, category, int(category_confirmed), proposed_by,
         related_event, int(is_simulated), now_iso()),
    )
    return bid


def confirm_barrier_category(
    conn: sqlite3.Connection, barrier_id: str, category: str
) -> None:
    """The user corrects or confirms a proposed classification (M3 acceptance)."""
    if category not in BARRIER_CATEGORIES:
        raise ValidationError(f"Unknown category: {category}", "category")
    cur = conn.execute(
        """UPDATE barrier_event
           SET category = ?, category_confirmed = 1, proposed_by = 'user'
           WHERE id = ?""",
        (category, barrier_id),
    )
    if cur.rowcount == 0:
        raise ValidationError("That entry no longer exists", "barrier_id")


def resolve_barrier(
    conn: sqlite3.Connection, barrier_id: str, status: str = "resolved"
) -> None:
    if status not in {"open", "resolved", "parked"}:
        raise ValidationError(f"Unknown status: {status}", "status")
    conn.execute(
        "UPDATE barrier_event SET status = ?, resolved_at = ? WHERE id = ?",
        (status, now_iso() if status == "resolved" else None, barrier_id),
    )


def list_barriers(
    conn: sqlite3.Connection, user_id: str, status: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM barrier_event WHERE user_id = ?"
    args: list[Any] = [user_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql, args)]


def due_followups(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    """Open barriers worth asking about again.

    M3: follow-up must happen, but a *resolved* item must not be raised forever.
    """
    rows = conn.execute(
        """SELECT * FROM barrier_event
           WHERE user_id = ? AND status = 'open'
           ORDER BY created_at ASC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_support_action(
    conn: sqlite3.Connection,
    user_id: str,
    title: str,
    basis_type: str,
    basis_id: str | None = None,
    basis_label: str | None = None,
    barrier_id: str | None = None,
    detail: str | None = None,
    is_simulated: bool = True,
) -> str:
    """Record an action the user chose. Requires a stated basis."""
    if basis_type not in {"care_plan", "education", "user_choice"}:
        raise ValidationError(f"Unknown basis: {basis_type}", "basis_type")
    if basis_type in {"care_plan", "education"} and not basis_id:
        raise ValidationError(
            "An action from a plan or a source must record which one", "basis_id"
        )
    sid = new_id("act")
    conn.execute(
        """INSERT INTO support_action
           (id, user_id, barrier_id, title, detail, basis_type, basis_id,
            basis_label, status, is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?,?,'chosen',?,?)""",
        (sid, user_id, barrier_id, _clean(title), _clean(detail) or None, basis_type,
         basis_id, _clean(basis_label) or None, int(is_simulated), now_iso()),
    )
    return sid


def set_action_status(conn: sqlite3.Connection, action_id: str, status: str) -> None:
    if status not in {"chosen", "done", "dropped"}:
        raise ValidationError(f"Unknown status: {status}", "status")
    conn.execute("UPDATE support_action SET status = ? WHERE id = ?", (status, action_id))


def list_support_actions(
    conn: sqlite3.Connection, user_id: str, status: str | None = None
) -> list[dict]:
    sql = "SELECT * FROM support_action WHERE user_id = ?"
    args: list[Any] = [user_id]
    if status:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql, args)]


# -------------------------------------------------------------- knowledge access


def upsert_education_source(conn: sqlite3.Connection, payload: dict) -> str:
    sid = payload["id"]
    conn.execute(
        """INSERT INTO education_source
           (id, publisher, title, url, retrieved_at, applies_to, reuse_note,
            review_state, reviewer, reviewed_at, is_simulated)
           VALUES (?,?,?,?,?,?,?,?,?,?,0)
           ON CONFLICT(id) DO UPDATE SET
             publisher=excluded.publisher, title=excluded.title, url=excluded.url,
             retrieved_at=excluded.retrieved_at, applies_to=excluded.applies_to,
             reuse_note=excluded.reuse_note, review_state=excluded.review_state""",
        (sid, payload["publisher"], payload["title"], payload["url"],
         payload.get("retrieved_at", today_iso()), payload.get("applies_to"),
         payload.get("reuse_note"), payload.get("review_state", "team_checked"),
         payload.get("reviewer"), payload.get("reviewed_at")),
    )
    return sid


def upsert_education_fact(conn: sqlite3.Connection, payload: dict) -> str:
    conn.execute(
        """INSERT INTO education_fact
           (id, source_id, topic, subject, statement, applies_to, review_state,
            enabled, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             source_id=excluded.source_id, topic=excluded.topic,
             subject=excluded.subject, statement=excluded.statement,
             applies_to=excluded.applies_to, review_state=excluded.review_state,
             enabled=excluded.enabled""",
        (payload["id"], payload["source_id"], payload["topic"],
         payload.get("subject"), payload["statement"], payload.get("applies_to"),
         payload.get("review_state", "team_checked"),
         int(payload.get("enabled", True)), now_iso()),
    )
    return payload["id"]


def search_facts(
    conn: sqlite3.Connection,
    topic: str | None = None,
    subject: str | None = None,
    limit: int = 8,
) -> list[dict]:
    """Retrieve enabled facts joined to their source.

    Only ``enabled = 1`` rows are ever returned, so a fact that failed review is
    unreachable from the model by construction rather than by prompting.
    """
    sql = """
        SELECT f.*, s.publisher, s.title AS source_title, s.url AS source_url,
               s.retrieved_at AS source_retrieved_at, s.review_state AS source_review
        FROM education_fact f
        JOIN education_source s ON s.id = f.source_id
        WHERE f.enabled = 1
    """
    args: list[Any] = []
    if topic:
        sql += " AND f.topic = ?"
        args.append(topic)
    if subject:
        sql += " AND (f.subject IS NULL OR lower(f.subject) LIKE ?)"
        args.append(f"%{subject.lower()}%")
    sql += " ORDER BY f.id LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]


def get_fact(conn: sqlite3.Connection, fact_id: str) -> dict | None:
    row = conn.execute(
        """SELECT f.*, s.publisher, s.title AS source_title, s.url AS source_url,
                  s.retrieved_at AS source_retrieved_at,
                  s.review_state AS source_review
           FROM education_fact f JOIN education_source s ON s.id = f.source_id
           WHERE f.id = ? AND f.enabled = 1""",
        (fact_id,),
    ).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------ M5: summary


def save_summary(
    conn: sqlite3.Connection,
    user_id: str,
    period_start: str,
    period_end: str,
    facts: dict,
    narrative: str | None = None,
    omitted_items: Sequence[str] | None = None,
    user_edited: bool = False,
    is_simulated: bool = True,
) -> str:
    sid = new_id("sum")
    conn.execute(
        """INSERT INTO visit_summary
           (id, user_id, period_start, period_end, facts_json, narrative,
            omitted_items, user_edited, generated_at, is_simulated)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (sid, user_id, period_start, period_end, json.dumps(facts),
         narrative, json.dumps(list(omitted_items or [])), int(user_edited),
         now_iso(), int(is_simulated)),
    )
    return sid


def get_summary(conn: sqlite3.Connection, summary_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM visit_summary WHERE id = ?", (summary_id,)
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    out["facts"] = json.loads(out.pop("facts_json"))
    out["omitted_items"] = json.loads(out.pop("omitted_items") or "[]")
    return out


def list_questions(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM consultation_question WHERE user_id = ?
           ORDER BY priority DESC, created_at""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_question(
    conn: sqlite3.Connection,
    user_id: str,
    text: str,
    origin: str = "user",
    priority: int = 0,
    is_simulated: bool = True,
) -> str:
    body = _clean(text)
    if not body:
        raise ValidationError("The question cannot be empty", "text")
    qid = new_id("q")
    conn.execute(
        """INSERT INTO consultation_question
           (id, user_id, text, origin, priority, is_simulated, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (qid, user_id, body, origin, int(priority), int(is_simulated), now_iso()),
    )
    return qid


def set_question_inclusion(
    conn: sqlite3.Connection, user_id: str, question_id: str, include: bool
) -> None:
    conn.execute(
        "UPDATE consultation_question SET include_in_summary = ? WHERE id = ? AND user_id = ?",
        (int(bool(include)), question_id, user_id),
    )


def delete_question(conn: sqlite3.Connection, user_id: str, question_id: str) -> None:
    conn.execute(
        "DELETE FROM consultation_question WHERE id = ? AND user_id = ?",
        (question_id, user_id),
    )


# ----------------------------------------------------------- conversation & audit


def add_message(
    conn: sqlite3.Connection,
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    payload: dict | None = None,
    mode: str | None = None,
) -> str:
    mid = new_id("msg")
    conn.execute(
        """INSERT INTO conversation_message
           (id, user_id, session_id, role, content, payload_json, mode, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (mid, user_id, session_id, role, content,
         json.dumps(payload) if payload is not None else None, mode, now_iso()),
    )
    return mid


def list_messages(
    conn: sqlite3.Connection, session_id: str, limit: int = 60
) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM conversation_message WHERE session_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (session_id, limit),
    ).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json") or "null")
        out.append(d)
    return out


def audit(
    conn: sqlite3.Connection,
    kind: str,
    user_id: str | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    args: dict | None = None,
    result_status: str | None = None,
    source_ids: Iterable[str] | None = None,
    rule_version: str | None = None,
    detail: str | None = None,
    mode: str | None = None,
) -> str:
    """Append an audit line.

    Callers are responsible for redacting, but ``_redact`` is applied here as a
    backstop so a careless caller cannot leak a key into the trace.
    """
    aid = new_id("aud")
    conn.execute(
        """INSERT INTO audit_event
           (id, user_id, session_id, kind, tool_name, args_json, result_status,
            source_ids, rule_version, detail, mode, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, user_id, session_id, kind, tool_name,
         json.dumps(_redact(args), default=str)[:4000] if args is not None else None,
         result_status,
         json.dumps(list(source_ids)) if source_ids else None,
         rule_version, _redact_text(detail), mode, now_iso()),
    )
    return aid


_SECRET_HINTS = ("key", "token", "secret", "password", "authorization", "bearer")


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("<redacted>" if any(h in k.lower() for h in _SECRET_HINTS) else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def _redact_text(text: str | None, limit: int = 400) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for hint in _SECRET_HINTS:
        if hint in lowered:
            return "<redacted: looked like it contained a credential>"
    return text[:limit]


def list_audit(
    conn: sqlite3.Connection, session_id: str | None = None, limit: int = 120
) -> list[dict]:
    sql = "SELECT * FROM audit_event"
    args: list[Any] = []
    if session_id:
        sql += " WHERE session_id = ?"
        args.append(session_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]


def system_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    """Return global operational counts for the monitoring API.

    Blood-pressure corrections are append-only in this project, so
    ``total_bp_recordings`` counts every stored row, including superseded history.
    An active barrier is an unresolved ``open`` event; resolved and parked events are
    deliberately excluded. Database size is the number of allocated SQLite pages and
    therefore excludes transient WAL/SHM sidecar files.
    """
    row = conn.execute(
        """SELECT
               (SELECT COUNT(*) FROM user_profile) AS total_users,
               (SELECT COUNT(*) FROM bp_reading) AS total_bp_recordings,
               (SELECT COUNT(*) FROM medication_item) AS total_medications_tracked,
               (SELECT COUNT(*) FROM barrier_event WHERE status = 'open') AS active_barriers"""
    ).fetchone()
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])

    return {
        "total_users": int(row["total_users"]),
        "total_bp_recordings": int(row["total_bp_recordings"]),
        "total_medications_tracked": int(row["total_medications_tracked"]),
        "active_barriers": int(row["active_barriers"]),
        "database_size_kb": (page_count * page_size + 1023) // 1024,
    }


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]


def get_conn():
    """Convenience for route handlers that want a fresh session context."""
    return session()
