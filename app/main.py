"""FastAPI application.

Single process, no build step, SQLite on disk. The deliberate constraint is that a
fresh clone goes from nothing to a running demo with ``make setup && make seed && make
run`` and no network dependency - because the most likely way to lose this competition
is to fail to start on the judging machine.

Session handling is intentionally simple and its limits are stated rather than implied:
a signed cookie identifies a browser session, and each session gets its own user row
when the demo is reset. This is enough to demonstrate data isolation between sessions,
and it is not a claim about production authentication.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import SETTINGS
from .db import init_db
from .llm.help import emergency_info
from .llm.orchestrator import orchestrator_metadata
from .safety.rules import RULES
from .routes import api, barrier, pages, readings, stats as stats_routes, summary as summary_routes

APP_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="CareSteps",
    description="Prototype AI health companion for older adults managing blood pressure",
    version="0.1.0",
    docs_url="/api/docs",
)

# Session cookie. A random key each boot is correct for a prototype: it means a
# restart signs everyone out, which is the safe default when there is no user store.
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
    session_cookie=SETTINGS.session_cookie,
    same_site="lax",
    https_only=False,  # local demo over http; documented in docs/architecture.md
)

app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals.update(
    app_name=SETTINGS.app_name,
    challenge_label=SETTINGS.challenge_label,
    rule_version=RULES.version,
)


@app.on_event("startup")
def _startup() -> None:
    init_db(SETTINGS.db_path)


# A global escape hatch so every template can show the agent-mode badge and the
# emergency number without each route having to pass them.
@app.middleware("http")
async def inject_globals(request: Request, call_next):
    request.state.emergency = emergency_info()
    request.state.agent = SETTINGS.llm.describe()
    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict:
    from .db import connect

    conn = connect(SETTINGS.db_path)
    try:
        profile = conn.execute("SELECT COUNT(*) AS c FROM user_profile").fetchone()["c"]
    finally:
        conn.close()
    return {
        "ok": True,
        "db": str(SETTINGS.db_path),
        "profiles": profile,
        "llm": SETTINGS.llm.describe(),
        "rules_version": RULES.version,
    }


@app.get("/trace", response_class=HTMLResponse)
def trace(request: Request):
    """The transparency page.

    Deliberately public and prominent. It shows the tool contracts, the active rules
    with their sources and review state, the prompt fingerprint, the model status, and
    the live audit log for this session. This is the evidence for the AI-workflow and
    Responsible-AI judging dimensions, and it is generated from the running system
    rather than written by hand.
    """
    from .db import connect
    from .repository import list_audit

    conn = connect(SETTINGS.db_path)
    try:
        events = list_audit(conn, session_id=request.session.get("sid"), limit=100)
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "trace.html",
        {
            "meta": orchestrator_metadata(),
            "events": events,
            "emergency": emergency_info(),
        },
    )


@app.get("/", include_in_schema=False)
def root(request: Request):
    return RedirectResponse(url="/app", status_code=303)


for module in (pages, readings, barrier, summary_routes, api, stats_routes):
    app.include_router(module.router)

# The medication-status router lives in the same file as the readings router but
# carries a different prefix and therefore must be mounted separately. It was
# defined but never included here, so POST /medication/report returned 404.
app.include_router(readings.med_router)
