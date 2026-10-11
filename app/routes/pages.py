"""The pages a person actually uses.

Design rules, from the accessibility requirement rather than from taste:

* One task per screen. The home page has three entry points, not a dashboard.
* Tap targets are large; nothing important is smaller than 44px.
* Numbers are always accompanied by their denominator ("out of the last 14 days").
* No reading of a value is presented as a verdict.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import repository as repo
from .. import stats as stats_mod
from ..llm.help import emergency_info, other_routes
from ..llm.orchestrator import orchestrator_metadata
from ..safety.rules import RULES
from .deps import current_user_id, get_session_id, read_conn

router = APIRouter(prefix="/app", tags=["pages"])


def _base(request: Request) -> dict:
    """Values every page needs."""
    from ..config import SETTINGS

    return {
        "request": request,
        "emergency": emergency_info(),
        "other_routes": other_routes(),
        "agent": SETTINGS.llm.describe(),
        "rule_version": RULES.version,
        "session_id": get_session_id(request),
    }


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Today: three entry points, and nothing else competing for attention."""
    user_id = current_user_id(request)
    conn = read_conn()
    try:
        profile = repo.get_profile(conn, user_id)
        readings = repo.list_readings(conn, user_id, days=7)
        latest = readings[0] if readings else None
        unrecorded = repo.derive_unrecorded(
            conn,
            user_id,
            (date.today() - timedelta(days=6)).isoformat(),
            date.today().isoformat(),
        )
        open_barriers = repo.due_followups(conn, user_id)
        meds = repo.list_medications(conn, user_id)
        actions = repo.list_support_actions(conn, user_id, status="chosen")
    finally:
        conn.close()

    # The home page's most important line. It asks about a gap rather than reporting a
    # failure, and it never characterises the gap as a missed dose.
    nudge = None
    if unrecorded:
        nudge = {
            "days": [u["scheduled_for"][:10] for u in unrecorded],
            "question": (
                f"There is no record for the last {len(unrecorded)} day(s). "
                "Would you like to add anything? You can also skip this."
            ),
        }

    return _render(
        request,
        "home.html",
        {
            **_base(request),
            "profile": profile,
            "latest": latest,
            "nudge": nudge,
            "open_barriers": open_barriers,
            "medications": meds,
            "open_actions": actions,
            "today": date.today().isoformat(),
        },
    )


@router.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request):
    """M0: the existing plan, with the origin of every line visible."""
    user_id = current_user_id(request)
    conn = read_conn()
    try:
        profile = repo.get_profile(conn, user_id)
        plan = repo.list_care_plan(conn, user_id)
        meds = repo.list_medications(conn, user_id)
        # Which medicines actually have a knowledge entry, so a missing explanation is
        # visible rather than silently absent.
        for m in meds:
            m["has_explanation"] = bool(
                m["education_id"] and repo.get_fact(conn, m["education_id"])
            )
    finally:
        conn.close()

    return _render(
        request,
        "plan.html",
        {
            **_base(request),
            "profile": profile,
            "plan": plan,
            "medications": meds,
        },
    )


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    """M1: full record, including superseded rows so corrections are visible."""
    user_id = current_user_id(request)
    conn = read_conn()
    try:
        readings = repo.list_readings(conn, user_id, days=60, include_superseded=True)
        # Attach the revision chain so the template can mark corrected records.
        for r in readings:
            if r.get("corrects") or r.get("superseded_by"):
                r["chain"] = repo.reading_revision_chain(conn, r["id"])
                r["corrected"] = True
            else:
                r["corrected"] = False
    finally:
        conn.close()

    return _render(
        request,
        "history.html",
        {**_base(request), "readings": readings},
    )


@router.get("/trends", response_class=HTMLResponse)
def trends_page(request: Request):
    """M4: the numbers, computed in code, with the denominator always shown."""
    user_id = current_user_id(request)
    conn = read_conn()
    try:
        bundle = stats_mod.build_period_stats(conn, user_id, days=14)
        plan = repo.list_care_plan(conn, user_id)
        meds = repo.list_medications(conn, user_id)
    finally:
        conn.close()

    # Only present when the plan itself carries a sourced target.
    target = next(
        (
            p
            for p in plan
            if p.get("target_systolic") and p.get("target_source")
        ),
        None,
    )

    return _render(
        request,
        "trends.html",
        {
            **_base(request),
            "s": bundle,
            "target": target,
            "medications": meds,
        },
    )


@router.get("/medicines", response_class=HTMLResponse)
def medicines_page(request: Request):
    """M2: what each confirmed medicine is for, and where that came from."""
    user_id = current_user_id(request)
    conn = read_conn()
    try:
        meds = repo.list_medications(conn, user_id)
        explained = []
        for m in meds:
            fact = repo.get_fact(conn, m["education_id"]) if m["education_id"] else None
            explained.append({**m, "fact": fact})
        # Everything the knowledge base can explain, so the boundary of what is
        # covered is visible rather than implied.
        all_facts = repo.search_facts(conn, topic="medication_purpose", limit=50)
    finally:
        conn.close()

    return _render(
        request,
        "medicines.html",
        {**_base(request), "medications": explained, "all_facts": all_facts},
    )


@router.get("/support", response_class=HTMLResponse)
def support_page(request: Request):
    """M3: the differentiator, shown as a map of reason to support."""
    from ..tools.handlers import SUPPORT_BY_CATEGORY
    from ..repository import BARRIER_CATEGORIES

    user_id = current_user_id(request)
    conn = read_conn()
    try:
        barriers = repo.list_barriers(conn, user_id)
        actions = repo.list_support_actions(conn, user_id)
    finally:
        conn.close()

    return _render(
        request,
        "support.html",
        {
            **_base(request),
            "barriers": barriers,
            "actions": actions,
            "categories": BARRIER_CATEGORIES,
            "support_map": SUPPORT_BY_CATEGORY,
        },
    )


@router.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    """M6: the fixed help path. Reachable from every page, never behind a model."""
    return _render(
        request,
        "help.html",
        {**_base(request), "help": emergency_info()},
    )


@router.get("/trace", response_class=HTMLResponse)
def trace_page(request: Request):
    """The transparency page, also reachable in-app."""
    return RedirectResponse(url="/trace", status_code=303)


def _render(request: Request, template: str, context: dict) -> HTMLResponse:
    from ..main import templates

    return templates.TemplateResponse(request, template, context)
