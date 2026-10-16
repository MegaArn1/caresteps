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
def chat(request: Request, message: str = Form(...)):
    """One conversational turn.

    The provider uses synchronous HTTP. A synchronous FastAPI route runs this
    work in the thread pool, keeping health checks and other requests responsive
    while the model is waiting. Database connections stay in the same worker.

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

        # Keep a reference to the drafts dict. The ToolContext inside _live_turn
        # mutates the same object, so any prepare_* call will have populated it by
        # the time run_turn returns. We bridge the results to the session below so
        # the chat-confirm endpoints can find them on the next request.
        ctx_drafts: dict = {}
        result = run_turn(conn, user_id, sid, text, ctx_drafts=ctx_drafts)

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

    # Persist any drafts the live turn produced so the confirm endpoint can find
    # them. The reading form uses request.session["reading_draft"] directly; the
    # chat path uses a keyed store so multiple prepare_* calls in one session do
    # not clobber each other.
    if ctx_drafts:
        existing = request.session.get("chat_drafts") or {}
        existing.update(ctx_drafts)
        request.session["chat_drafts"] = existing

    return JSONResponse({"ok": True, **result.to_dict()})


@router.post("/chat/confirm")
async def chat_confirm(request: Request, draft_id: str = Form(...)):
    """Save a draft that the chat path produced.

    The live turn calls prepare_reading or prepare_medication_report, which put
    the draft into ctx_drafts; the /api/chat handler then persists that dict to
    the session under "chat_drafts". This endpoint retrieves it, calls
    confirm_draft (the UI-only handler), and clears the entry.

    It mirrors the two-phase pattern that the form-based flow uses, just with
    the draft keyed by the id the model returned rather than stored flat.
    """
    from ..tools import ToolContext, dispatch
    from ..tools.handlers import h_confirm_draft

    user_id = current_user_id(request)
    sid = get_session_id(request)

    chat_drafts = request.session.get("chat_drafts") or {}
    if draft_id not in chat_drafts:
        return JSONResponse(
            {"ok": False, "error": "That draft is no longer waiting. Please try again."},
            status_code=400,
        )

    conn = db()
    try:
        ctx = ToolContext(conn=conn, user_id=user_id, session_id=sid, drafts=chat_drafts)
        result = h_confirm_draft(ctx, {"draft_id": draft_id})
        if result.status != "ok":
            return JSONResponse({"ok": False, "error": result.message}, status_code=400)
        repo.audit(
            conn, kind="tool_call", user_id=user_id, session_id=sid,
            tool_name="confirm_draft", args={"draft_id": draft_id},
            result_status="ok", rule_version=RULES.version, mode="ui",
        )
    finally:
        conn.close()

    # Remove the entry now it has been persisted.
    chat_drafts.pop(draft_id, None)
    request.session["chat_drafts"] = chat_drafts

    return JSONResponse({"ok": True, **result.data})


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


@router.post("/demo/reset")
async def reset(request: Request):
    """Rebuild the fictional dataset.

    Present because a public demo needs a way back to a known state. It only ever
    rebuilds simulated data, and it says so in its response.

    DESTRUCTIVE BY DESIGN, so the ordering here matters more than usual. An earlier
    version called ``reset_db()`` and then failed on ``conn.close()`` - it had used
    ``session()``, a context manager, as though it were a connection. The result was
    the worst possible failure mode: every table dropped, nothing re-seeded, HTTP 500,
    and a demo database left completely empty. A "recover the database" button that
    destroys the database is worse than no button at all.

    Two changes make that unrecoverable state impossible:

    * the connection is opened with ``connect()``, and
    * seeding is verified *before* success is reported. If the rebuild does not
      actually produce a profile, the response says so and does not claim success.

    A third defect was found later and is fixed here: the handler re-seeded the
    patient and the readings but never loaded the knowledge base, so after a reset
    ``education_source`` and ``education_fact`` were empty. ``/app/medicines``
    resolves each medicine to a fact by id, so every medicine rendered without its
    explanation — the app knew the name and had nothing to say about it. Dropping a
    table drops everything in it, and this one was filled by ``scripts/seed.py``
    rather than by ``seed_demo()``, which is why the omission was easy to miss.
    """
    from ..content_loader import load_knowledge
    from ..db import connect, reset_db
    from ..demo import seed as demo_seed

    reset_db()

    conn = connect()
    try:
        # Knowledge first, then the patient: the medication rows reference education
        # entries, so loading in the other order would leave the reference dangling.
        knowledge = load_knowledge(conn)
        user_id = demo_seed.seed_demo(conn)

        # Verify the rebuild rather than assuming it. Reaching the end of the previous
        # function was treated as evidence of success, which is exactly how the empty
        # database went unnoticed.
        profile = repo.get_profile(conn, user_id)
        readings = repo.count_rows(conn, "bp_reading")
        facts = repo.count_rows(conn, "education_fact")
        if not profile or readings == 0 or facts == 0:
            return JSONResponse(
                {
                    "ok": False,
                    "error": (
                        "The demo data could not be rebuilt, so the database is "
                        "currently incomplete. Run 'make seed' from a terminal to "
                        "restore it."
                    ),
                    "profiles": repo.count_rows(conn, "user_profile"),
                    "readings": readings,
                    "education_facts": facts,
                },
                status_code=500,
            )

        repo.audit(
            conn, kind="tool_call", user_id=user_id,
            session_id=get_session_id(request), tool_name="demo_reset",
            args={}, result_status="ok", rule_version=RULES.version, mode="ui",
            detail="demo database rebuilt with simulated data",
        )
    except Exception as exc:
        # Report the failure plainly instead of leaving a 500 and a silent empty file.
        return JSONResponse(
            {
                "ok": False,
                "error": (
                    f"The demo data could not be rebuilt ({type(exc).__name__}). "
                    "Run 'make seed' from a terminal to restore it."
                ),
                "profiles": repo.count_rows(conn, "user_profile"),
            },
            status_code=500,
        )
    finally:
        conn.close()

    request.session.pop("uid", None)
    request.session.pop("reading_draft", None)
    request.session.pop("summary_omitted", None)

    return JSONResponse(
        {
            "ok": True,
            "message": "Demo data rebuilt. All of it is simulated.",
            "user_id": user_id,
            "readings": readings,
            "education_facts": facts,
            "knowledge_ok": knowledge.ok,
        }
    )


@router.get("/rules")
def rules() -> dict:
    """The active rule set with sources and review state.

    Exposed unauthenticated on purpose: a judge or a reviewer should be able to check
    what triggers exist without running the app.
    """
    return {"ok": True, "rules": rule_metadata()}
