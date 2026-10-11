"""M5 routes: build, preview, edit, print.

The sequence is the requirement. The summary is generated, shown, edited, and only then
printed. There is no code path in this file that sends it anywhere - that is a
deliberate absence, and it is stated on the page so nobody has to take it on trust.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import repository as repo
from ..safety.rules import RULES
from ..summary import OMITTABLE_KEYS, apply_omissions, build_summary_facts
from .deps import current_user_id, db, get_session_id, read_conn

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def index(request: Request, days: int = 14):
    """Preview screen. Everything here came from stored records.

    Omissions ARE applied here, not only on the print page. An earlier version applied
    them in ``printable()`` alone, so a presenter who removed a section and pointed at
    the preview to show it gone was pointing at a section that was still on screen.
    The preview is the screen the user actually edits on, so it has to honour the edit.
    """
    from .pages import _base

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        facts = build_summary_facts(conn, user_id, days=days)
        questions = repo.list_questions(conn, user_id)
    finally:
        conn.close()

    omitted = request.session.get("summary_omitted") or []
    facts = apply_omissions(facts, omitted)

    return _render(
        request,
        "summary.html",
        {
            **_base(request),
            "facts": facts,
            "days": days,
            "questions": questions,
            "omittable": OMITTABLE_KEYS,
            "omitted": omitted,
        },
    )


@router.post("/omit")
async def omit(request: Request, days: int = Form(14)):
    """Toggle a section out of the summary.

    Omission is per-section and reversible, which is what makes "the patient decides
    what travels" real rather than a promise.
    """
    user_id = current_user_id(request)
    key = request.query_params.get("key") or (await request.form()).get("key", "")
    omitted = set(request.session.get("summary_omitted") or [])
    if key in omitted:
        omitted.discard(key)
    elif key in OMITTABLE_KEYS:
        omitted.add(key)
    request.session["summary_omitted"] = sorted(omitted)
    return RedirectResponse(url=f"/summary?days={days}", status_code=303)


@router.post("/question/add")
async def add_question(
    request: Request, text: str = Form(...), origin: str = Form("user")
):
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            repo.add_question(conn, user_id, text, origin=origin)
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request), tool_name="add_question",
            args={"origin": origin}, result_status="ok",
            rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/summary", status_code=303)


@router.post("/question/{question_id}/include")
async def set_inclusion(
    request: Request, question_id: str, include: str = Form("1")
):
    user_id = current_user_id(request)
    conn = db()
    try:
        repo.set_question_inclusion(conn, user_id, question_id, include == "1")
    finally:
        conn.close()
    return RedirectResponse(url="/summary", status_code=303)


@router.post("/question/{question_id}/delete")
async def delete_question(request: Request, question_id: str):
    user_id = current_user_id(request)
    conn = db()
    try:
        repo.delete_question(conn, user_id, question_id)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request), tool_name="delete_question",
            args={"question_id": question_id}, result_status="ok",
            rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/summary", status_code=303)


@router.get("/print", response_class=HTMLResponse)
def printable(request: Request, days: int = 14):
    """Print-friendly page. No navigation, no buttons - what prints is what is shown.

    The context carries the same base values every other page gets. Leaving them out
    did not merely trim the page: base.html reads ``emergency``, ``agent`` and the two
    banner flags, and "not passed in" is not the same as "not wanted". The help bar is
    the one control that must survive onto paper, so it is passed here rather than
    assumed absent.
    """
    from .pages import _base

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        facts = build_summary_facts(conn, user_id, days=days)
    finally:
        conn.close()

    omitted = request.session.get("summary_omitted") or []
    facts = apply_omissions(facts, omitted)

    return _render(
        request,
        "summary_print.html",
        {
            **_base(request),
            "facts": facts,
            "days": days,
            # Nothing on this page is interactive, so the banners that exist to offer
            # a way out of a broken state have nothing to act on here.
            "hide_mode_banner": True,
        },
    )


@router.post("/save")
async def save(request: Request, days: int = Form(14)):
    """Store a generated version, so what was printed can be compared with the data."""
    user_id = current_user_id(request)
    conn = db()
    try:
        facts = build_summary_facts(conn, user_id, days=days)
        omitted = request.session.get("summary_omitted") or []
        summary_id = repo.save_summary(
            conn, user_id,
            period_start=facts["meta"]["period"]["from"],
            period_end=facts["meta"]["period"]["to"],
            facts=facts,
            omitted_items=omitted,
            user_edited=bool(omitted),
        )
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request), tool_name="save_summary",
            args={"summary_id": summary_id, "omitted": omitted},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/summary?saved=1", status_code=303)


def _render(request: Request, template: str, context: dict, status_code: int = 200):
    from ..main import templates

    return templates.TemplateResponse(request, template, context, status_code=status_code)
