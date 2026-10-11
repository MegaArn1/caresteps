"""M1 and M2 write routes.

The two-phase pattern is enforced here: ``/readings/prepare`` returns a draft and
writes nothing; ``/readings/confirm`` persists it. The confirm endpoint requires the
draft id that prepare produced, so a client cannot POST values directly into storage
without having been shown them first.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import repository as repo
from ..llm.orchestrator import run_turn
from ..safety.rules import RULES
from .deps import current_user_id, db, get_session_id, read_conn

router = APIRouter(prefix="/readings", tags=["readings"])


@router.get("/new", response_class=HTMLResponse)
def new_reading(request: Request):
    """The entry form. Deliberately one screen with the smallest possible number of
    required fields: two numbers, and a time that defaults to now."""
    from .pages import _base

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        recent = repo.list_readings(conn, user_id, days=3)
    finally:
        conn.close()

    return _render(
        request,
        "reading_new.html",
        {**_base(request), "recent": recent, "now": repo.now_iso()},
    )


@router.post("/prepare")
async def prepare(
    request: Request,
    systolic: str = Form(...),
    diastolic: str = Form(...),
    measured_at: str = Form(""),
    pulse: str = Form(""),
    user_feeling: str = Form(""),
    note: str = Form(""),
):
    """Phase one. Validate and show a confirmation card. Writes nothing."""
    from .pages import _base

    user_id = current_user_id(request)
    sid = get_session_id(request)

    try:
        draft = repo.prepare_reading(
            user_id=user_id,
            systolic=systolic,
            diastolic=diastolic,
            measured_at=measured_at or repo.now_iso(),
            pulse=pulse or None,
            user_feeling=user_feeling or None,
            note=note or None,
        )
    except repo.ValidationError as exc:
        # Re-render the form with what the person typed still in it. The "already
        # recorded" panel is filled from the same query the GET uses: passing an
        # empty list here would make the template state that there are no readings
        # in the last three days, which this path never checked.
        conn = read_conn()
        try:
            recent = repo.list_readings(conn, user_id, days=3)
        finally:
            conn.close()

        return _render(
            request,
            "reading_new.html",
            {
                **_base(request),
                "error": exc.message,
                "field": exc.field,
                "values": {
                    "systolic": systolic, "diastolic": diastolic,
                    "measured_at": measured_at, "pulse": pulse,
                    "user_feeling": user_feeling, "note": note,
                },
                "recent": recent,
                "now": repo.now_iso(),
            },
            status_code=400,
        )

    # Hold the draft server-side, keyed by session, so confirming is a separate act.
    request.session["reading_draft"] = draft

    conn = db()
    try:
        repo.audit(
            conn, kind="tool_call", user_id=user_id, session_id=sid,
            tool_name="prepare_reading",
            args={"systolic": draft["systolic"], "diastolic": draft["diastolic"]},
            result_status="ok", rule_version=RULES.version,
            detail=f"concerns={len(draft['concerns'])}", mode="ui",
        )
    finally:
        conn.close()

    return _render(
        request,
        "reading_confirm.html",
        {"request": request, "draft": draft},
    )


@router.post("/confirm")
async def confirm(request: Request):
    """Phase two. Persist the draft that prepare produced."""
    user_id = current_user_id(request)
    sid = get_session_id(request)
    draft = request.session.get("reading_draft")

    if not draft:
        return JSONResponse(
            {"ok": False, "error": "That reading is no longer waiting to be saved. Please enter it again."},
            status_code=400,
        )

    conn = db()
    try:
        result = repo.confirm_reading(conn, user_id, draft, is_simulated=True)
        repo.audit(
            conn, kind="tool_call", user_id=user_id, session_id=sid,
            tool_name="confirm_reading",
            args={"reading_id": result["id"], "deduplicated": result["deduplicated"]},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()

    request.session.pop("reading_draft", None)

    if result["deduplicated"]:
        # A double submit is not an error, but it must not silently look like a new
        # record either.
        return RedirectResponse(url="/app/history?saved=duplicate", status_code=303)
    return RedirectResponse(url="/app/history?saved=1", status_code=303)


@router.post("/cancel")
async def cancel(request: Request):
    """Abandon a draft. Nothing was written, so there is nothing to undo."""
    request.session.pop("reading_draft", None)
    return RedirectResponse(url="/app", status_code=303)


@router.post("/{reading_id}/correct")
async def correct(
    request: Request,
    reading_id: str,
    systolic: str = Form(...),
    diastolic: str = Form(...),
    pulse: str = Form(""),
    note: str = Form(""),
):
    """Supersede a reading, keeping the original in the chain."""
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            new_id = repo.correct_reading(
                conn, user_id, reading_id,
                systolic=systolic, diastolic=diastolic,
                pulse=pulse or None, note=note or "Corrected by the patient.",
            )
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="correct_reading",
            args={"original": reading_id, "replacement": new_id},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/app/history?corrected=1", status_code=303)


# ------------------------------------------------------------- medication status

med_router = APIRouter(prefix="/medication", tags=["medication"])


@med_router.post("/report")
async def report_status(
    request: Request,
    status: str = Form(...),
    medication_id: str = Form(""),
    scheduled_for: str = Form(""),
    note: str = Form(""),
    backfill: str = Form(""),
):
    """Record what the patient says happened.

    Four states are supported, and ``unrecorded`` is refused by the repository, which
    is what stops a missing record from ever being stored as a report.
    """
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            rid = repo.record_medication_report(
                conn, user_id,
                status=status,
                medication_id=medication_id or None,
                scheduled_for=scheduled_for or None,
                note=note or None,
                is_backfilled=bool(backfill),
            )
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="record_medication_report",
            args={"status": status, "backfilled": bool(backfill)},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/app?saved=medication", status_code=303)


def _render(request: Request, template: str, context: dict, status_code: int = 200):
    from ..main import templates

    return templates.TemplateResponse(request, template, context, status_code=status_code)
