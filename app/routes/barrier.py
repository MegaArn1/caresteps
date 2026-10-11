"""M3 routes: the execution-difficulty flow.

This is the product's differentiator over a plain reminder app, so the routes are
written to make the *shape* of the interaction visible:

    notice a gap -> ask an open question -> offer options -> confirm the category
    -> offer a MATCHING support -> save the choice -> follow up later

Two rules are enforced in code rather than in wording:

1. A category proposed by the model is stored with ``category_confirmed = 0`` and is
   rendered differently until the user agrees. ``/confirm-category`` is the only way to
   set it to confirmed.
2. Declining is always available. ``declined_to_say`` is a first-class category with
   its own support option ("leave this for now"), not an error path.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import repository as repo
from ..repository import BARRIER_CATEGORIES
from ..safety.rules import RULES
from ..tools.handlers import SUPPORT_BY_CATEGORY, _support_options_for
from .deps import current_user_id, db, get_session_id, read_conn

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/barriers", response_class=HTMLResponse)
def list_barriers(request: Request):
    from .pages import _base

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        barriers = repo.list_barriers(conn, user_id)
        actions = repo.list_support_actions(conn, user_id)
    finally:
        conn.close()

    return _render(
        request,
        "barrier_list.html",
        {**_base(request), "barriers": barriers, "actions": actions,
         "categories": BARRIER_CATEGORIES},
    )


@router.get("/ask", response_class=HTMLResponse)
def ask(request: Request, reason: str = ""):
    """The open question.

    Note what is absent: any suggestion of what the reason might be. The options are
    offered only after the person has had a chance to say it themselves, and the page
    always carries a way to skip.
    """
    from .pages import _base

    return _render(
        request,
        "barrier_ask.html",
        {
            **_base(request),
            "reason": reason,
            "categories": BARRIER_CATEGORIES,
        },
    )


@router.post("/record")
async def record(
    request: Request,
    user_words: str = Form(...),
    category: str = Form(""),
    related_event: str = Form(""),
    confirmed: str = Form(""),
):
    """Save what the person said.

    ``confirmed`` is set only when the person picked the category themselves from the
    list. Wording typed into free text never arrives with ``confirmed`` set, which is
    what keeps "the user told us" and "we guessed" separate in storage.
    """
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            bid = repo.record_barrier(
                conn, user_id,
                user_words=user_words,
                category=category or None,
                category_confirmed=bool(confirmed),
                proposed_by="user" if confirmed else "model",
                related_event=related_event or None,
            )
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)

        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="record_barrier",
            args={"category": category, "confirmed": bool(confirmed)},
            result_status="ok", rule_version=RULES.version,
            detail="user_words recorded verbatim", mode="ui",
        )
    finally:
        conn.close()

    # Straight to the support that matches THIS reason. The whole point is that a
    # different answer leads somewhere different.
    return RedirectResponse(url=f"/support/barrier/{bid}", status_code=303)


@router.get("/barrier/{barrier_id}", response_class=HTMLResponse)
def barrier_detail(request: Request, barrier_id: str):
    """Matching support for one difficulty."""
    from .pages import _base

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        barrier = next(
            (b for b in repo.list_barriers(conn, user_id) if b["id"] == barrier_id),
            None,
        )
        if not barrier:
            return RedirectResponse(url="/support/barriers", status_code=303)
        actions = [
            a for a in repo.list_support_actions(conn, user_id)
            if a.get("barrier_id") == barrier_id
        ]
        # If the reason is "I do not know what this is for", the useful next step is
        # the explanation itself - so look it up rather than describing that it exists.
        explanation = None
        if barrier.get("category") == "unclear_purpose":
            meds = repo.list_medications(conn, user_id)
            for m in meds:
                if m.get("education_id"):
                    explanation = repo.get_fact(conn, m["education_id"])
                    if explanation:
                        explanation["medicine_name"] = m["name"]
                        break
        # If it is "I am running out", the useful next step is knowing what is on the
        # plan - again looked up, not described.
        plan = repo.list_care_plan(conn, user_id)
    finally:
        conn.close()

    options = (
        _support_options_for(barrier["category"])
        if barrier["category_confirmed"]
        else _support_options_for(None)
    )

    return _render(
        request,
        "barrier_detail.html",
        {
            **_base(request),
            "barrier": barrier,
            "options": options,
            "actions": actions,
            "explanation": explanation,
            "plan": plan,
            "categories": BARRIER_CATEGORIES,
        },
    )


@router.post("/barrier/{barrier_id}/confirm-category")
async def confirm_category(request: Request, barrier_id: str, category: str = Form(...)):
    """The person corrects or agrees with the proposed reason.

    This exists so a wrong guess is recoverable in one tap. Without it, a
    misclassification would be permanent and the support that follows would be wrong.
    """
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            repo.confirm_barrier_category(conn, barrier_id, category)
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="confirm_barrier_category",
            args={"barrier_id": barrier_id, "category": category},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url=f"/support/barrier/{barrier_id}", status_code=303)


@router.post("/barrier/{barrier_id}/choose")
async def choose_action(
    request: Request,
    barrier_id: str,
    action_id: str = Form(...),
    title: str = Form(...),
    basis_type: str = Form("user_choice"),
    basis_id: str = Form(""),
    basis_label: str = Form(""),
    detail: str = Form(""),
):
    """Save the chosen action. Every action carries where it came from."""
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            aid = repo.add_support_action(
                conn, user_id,
                title=title,
                basis_type=basis_type,
                basis_id=basis_id or None,
                basis_label=basis_label or None,
                barrier_id=barrier_id or None,
                detail=detail or None,
            )
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="add_support_action",
            args={"action_id": action_id, "basis_type": basis_type},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url=f"/support/barrier/{barrier_id}?chosen=1", status_code=303)


@router.post("/barrier/{barrier_id}/resolve")
async def resolve(request: Request, barrier_id: str):
    """Mark a difficulty resolved, so follow-up stops raising it."""
    user_id = current_user_id(request)
    conn = db()
    try:
        repo.resolve_barrier(conn, barrier_id, "resolved")
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="resolve_barrier", args={"barrier_id": barrier_id},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/app/support", status_code=303)


@router.post("/barrier/{barrier_id}/park")
async def park(request: Request, barrier_id: str):
    """Leave it for now. Explicitly not a failure state."""
    user_id = current_user_id(request)
    conn = db()
    try:
        repo.resolve_barrier(conn, barrier_id, "parked")
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request),
            tool_name="park_barrier", args={"barrier_id": barrier_id},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()
    return RedirectResponse(url="/app/support", status_code=303)


@router.post("/action/{action_id}/status")
async def action_status(request: Request, action_id: str, status: str = Form(...)):
    user_id = current_user_id(request)
    conn = db()
    try:
        try:
            repo.set_action_status(conn, action_id, status)
        except repo.ValidationError as exc:
            return JSONResponse({"ok": False, "error": exc.message}, status_code=400)
    finally:
        conn.close()
    return RedirectResponse(url="/app/support", status_code=303)


def _render(request: Request, template: str, context: dict, status_code: int = 200):
    from ..main import templates

    return templates.TemplateResponse(request, template, context, status_code=status_code)
