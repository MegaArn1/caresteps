"""JSON API.

The browser talks to the app through exactly one conversational endpoint
(``POST /api/chat``) plus a handful of small helpers. Everything the chat endpoint
returns is already safety-checked and output-checked by the orchestrator, so this
module is a thin, auditable adapter and contains no decision logic of its own.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from .. import repository as repo
from ..config import SETTINGS
from ..llm.orchestrator import run_turn
from ..safety.rules import RULES, rule_metadata
from .deps import current_user_id, db, get_session_id, read_conn

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/chat")
async def chat(request: Request, message: str = Form(...)):
    """One conversational turn.

    The message is persisted before the turn runs, so a crash mid-turn still leaves an
    audit trail of what was asked. The response is persisted after, with its mode
    recorded, which is what lets the UI re-render an identical turn after a refresh and
    what makes the trace page a faithful record rather than a re-enactment.
    """
    user_id = current_user_id(request)
    sid = get_session_id(request)
    text = (message or "").strip()

    if not text:
        return JSONResponse({"ok": False, "error": "There was no message."}, status_code=400)

    conn = db()
    try:
        repo.add_message(conn, user_id, sid, "user", text)

        result = run_turn(conn, user_id, sid, text, ctx_drafts={})

        repo.add_message(
            conn, user_id, sid, "assistant", result.text,
            payload={
                "kind": result.payload.get("kind"),
                "payload": result.payload,
                "safety": result.safety,
                "tool_calls": result.tool_calls,
                "sources": result.sources,
                "degraded_reason": result.degraded_reason,
            },
            mode=result.mode,
        )
    finally:
        conn.close()

    return JSONResponse({"ok": True, **result.to_dict()})


@router.get("/status")
def status() -> dict:
    """Agent status for the UI badge. Never includes a credential."""
    return {
        "llm": SETTINGS.llm.describe(),
        "rules": {"version": RULES.version, "problems": RULES.problems},
    }


@router.get("/messages")
def messages(request: Request, limit: int = 40):
    """Conversation history for this session, for re-rendering after a refresh."""
    sid = get_session_id(request)
    conn = read_conn()
    try:
        return {"ok": True, "messages": repo.list_messages(conn, sid, limit=limit)}
    finally:
        conn.close()


@router.get("/audit")
def audit(request: Request, limit: int = 80):
    """This session's audit trail, for the trace page."""
    sid = get_session_id(request)
    conn = read_conn()
    try:
        return {"ok": True, "events": repo.list_audit(conn, session_id=sid, limit=limit)}
    finally:
        conn.close()


@router.get("/stats")
def stats(request: Request, days: int = 14):
    """The computed statistics, exposed so the numbers on screen are inspectable."""
    from .. import stats as stats_mod

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        return {"ok": True, "stats": stats_mod.build_period_stats(conn, user_id, days=days)}
    finally:
        conn.close()


@router.post("/demo/reset")
async def reset(request: Request):
    """Rebuild the fictional dataset.

    Present because a public demo needs a way back to a known state. It only ever
    rebuilds simulated data, and it says so in its response.
    """
    from ..db import reset_db, session as db_session
    from ..demo import seed as demo_seed

    reset_db()
    conn = db_session()
    try:
        user_id = demo_seed.seed_demo(conn)
        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request), tool_name="demo_reset",
            args={}, result_status="ok", rule_version=RULES.version, mode="ui",
            detail="demo database rebuilt with simulated data",
        )
    finally:
        conn.close()

    request.session.pop("uid", None)
    request.session.pop("reading_draft", None)
    request.session.pop("summary_omitted", None)

    return JSONResponse(
        {"ok": True, "message": "Demo data rebuilt. All of it is simulated.", "user_id": user_id}
    )


@router.get("/rules")
def rules() -> dict:
    """The active rule set with sources and review state.

    Exposed unauthenticated on purpose: a judge or a reviewer should be able to check
    what triggers exist without running the app.
    """
    return {"ok": True, "rules": rule_metadata()}
