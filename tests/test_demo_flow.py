"""End-to-end tests over the routes the live demonstration depends on.

Written after an adversarial audit of the demo runbook ran the actual click paths and
found two defects that would have surfaced on stage:

1. ``POST /api/demo/reset`` returned HTTP 500 and left the database completely empty.
   It called ``reset_db()`` first and then failed on ``conn.close()``, because it had
   used ``session()`` - a context manager - as though it were a connection. The
   presenter's "recover the database" button destroyed the database.

2. The summary preview ignored omissions. ``apply_omissions`` was called in
   ``printable()`` but not in ``index()``, so removing a section left it on screen in
   the preview and the presenter would have pointed at content that was still there.

Both are exactly the class of bug that unit tests miss and a click-through finds, which
is why these tests drive the real HTTP surface with ``TestClient`` rather than calling
functions directly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient bound to a temporary, seeded database.

    Pointing the app at a throwaway database is fiddlier than it looks, and worth
    explaining because the naive approaches do not work:

    * ``Settings`` is a **frozen** dataclass, so ``monkeypatch.setattr`` on an instance
      raises ``FrozenInstanceError``.
    * Three modules bind ``SETTINGS`` at import time (``main``, ``llm.provider``,
      ``routes.api``), so patching ``config.SETTINGS`` alone would be ignored by them.
    * Re-importing the app would create a second ``FastAPI`` instance and duplicate
      route registration.

    So: build a replacement ``Settings`` with ``dataclasses.replace`` and bind it into
    every module that captured the original. Then initialise the temp database and let
    the first request seed it on demand.
    """
    import dataclasses

    db_file = tmp_path / "demo.db"
    monkeypatch.setenv("CARESTEPS_DB", str(db_file))

    from app import config as config_mod
    from app import main as main_mod
    from app.llm import provider as provider_mod
    from app.routes import api as api_mod

    fresh = dataclasses.replace(config_mod.SETTINGS, db_path=db_file)

    for module in (config_mod, main_mod, provider_mod, api_mod):
        monkeypatch.setattr(module, "SETTINGS", fresh, raising=False)

    # Create the schema before the app's startup hook runs, so the hook is idempotent.
    from app.db import init_db

    init_db(db_file)

    with TestClient(main_mod.app) as c:
        # The first page request seeds the demo patient on demand.
        c.get("/app")
        yield c


class TestDemoReset:
    """The recover-the-demo button must recover the demo, not destroy it."""

    def test_reset_rebuilds_and_reports_success(self, client):
        before = client.get("/healthz").json()
        assert before["profiles"] >= 1

        resp = client.post("/api/demo/reset")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        # The response must carry evidence of the rebuild, not just a claim.
        assert body["readings"] > 0

    def test_database_is_intact_after_reset(self, client):
        """The regression: reset once left every table empty."""
        client.post("/api/demo/reset")
        after = client.get("/healthz").json()
        assert after["profiles"] == 1, "reset must leave exactly one seeded profile"

    def test_app_still_renders_after_reset(self, client):
        client.post("/api/demo/reset")
        for path in ("/app", "/app/trends", "/summary"):
            assert client.get(path).status_code == 200, f"{path} broke after reset"

    def test_reset_clears_the_session_user(self, client):
        """A stale user id would point at a row the rebuild deleted."""
        client.post("/api/demo/reset")
        assert client.get("/app").status_code == 200

    def test_failure_is_reported_rather_than_claimed_success(self, client, monkeypatch):
        """If seeding fails, the response must not say it worked."""
        from app.demo import seed as demo_seed

        def boom(_conn, **_kwargs):
            raise RuntimeError("simulated seeding failure")

        monkeypatch.setattr(demo_seed, "seed_demo", boom)

        resp = client.post("/api/demo/reset")
        assert resp.status_code == 500
        body = resp.json()
        assert body["ok"] is False
        assert "make seed" in body["error"], (
            "the error must tell the presenter how to recover"
        )


class TestSummaryOmission:
    """'Remove from summary' must actually remove it, on the screen users edit on."""

    def test_omitting_a_section_removes_it_from_the_preview(self, client):
        facts = self._facts(client)
        assert facts["reported_by_patient"]["feelings"], (
            "the demo patient must have recorded feelings for this test to mean anything"
        )
        text = facts["reported_by_patient"]["feelings"][0]["text"]

        assert text in client.get("/summary").text, "precondition: visible before omit"

        r = client.post("/summary/omit?key=reported_by_patient.feelings", data={"days": 14})
        assert r.status_code in (200, 303)
        assert text not in client.get("/summary").text, (
            "the preview ignored the omission - the regression this test exists for"
        )

    def test_omission_also_applies_to_the_print_page(self, client):
        facts = self._facts(client)
        text = facts["reported_by_patient"]["feelings"][0]["text"]
        client.post("/summary/omit?key=reported_by_patient.feelings", data={"days": 14})
        assert text not in client.get("/summary/print").text

    def test_omission_is_reversible(self, client):
        facts = self._facts(client)
        text = facts["reported_by_patient"]["feelings"][0]["text"]

        client.post("/summary/omit?key=reported_by_patient.feelings", data={"days": 14})
        assert text not in client.get("/summary").text

        client.post("/summary/omit?key=reported_by_patient.feelings", data={"days": 14})
        assert text in client.get("/summary").text, "putting it back must restore it"

    def test_a_toggle_is_offered_once_omitted(self, client):
        client.post("/summary/omit?key=reported_by_patient.feelings", data={"days": 14})
        assert "Put back" in client.get("/summary").text

    def test_the_numbers_are_not_omittable(self, client):
        """A page with the caveats but not the data would mislead the other way."""
        before = self._facts(client)["readings"]["n"]
        client.post("/summary/omit?key=readings.n", data={"days": 14})
        after = self._facts(client)["readings"]["n"]
        assert before == after > 0

    def test_unknown_key_is_ignored_without_error(self, client):
        r = client.post("/summary/omit?key=made.up.section", data={"days": 14})
        assert r.status_code in (200, 303)
        assert client.get("/summary").status_code == 200

    @staticmethod
    def _facts(client) -> dict:
        """Read the same fact table the route builds, for assertions on real content."""
        from app import repository as repo
        from app.summary import build_summary_facts

        conn = client.app.state.__dict__.get("_test_conn")
        if conn is None:
            from app.config import SETTINGS
            from app.db import connect

            conn = connect(SETTINGS.db_path)
            close = True
        else:
            close = False
        try:
            profile = repo.get_profile(conn)
            return build_summary_facts(conn, profile["id"], days=14)
        finally:
            if close:
                conn.close()


class TestEmergencyPathIsReachable:
    """The help path must work without the model, from every page."""

    def test_help_page_shows_no_number_when_unverified(self, client, monkeypatch):
        """An unverified number must never be presented as THE number to call.

        The patch target matters: ``routes.pages`` does ``from ..llm.help import
        emergency_info``, so patching ``app.llm.help.emergency_info`` would have no
        effect on the page. The name has to be replaced where it is actually looked up.

        The assertion is deliberately narrow. "995" appears on this page elsewhere as
        incidental prose in the Emergency SMS note, so a blanket ``"995" not in body``
        fails for an unrelated reason and proves nothing about the primary number. What
        actually matters is that no *dialable link* to it is rendered.
        """
        unverified = {
            "number": None, "label": "Emergency ambulance", "country": "Singapore",
            "verified": False, "review_state": "unreviewed", "sources": [],
            "retrieved_at": None, "what_to_say": [], "also": [],
            "warning": "The number could not be confirmed.",
            "app_does_not": "This app has not contacted anyone and cannot do so.",
        }

        from app.routes import pages as pages_mod

        monkeypatch.setattr(pages_mod, "emergency_info", lambda: unverified)

        body = client.get("/app/help").text
        assert "tel:995" not in body, (
            "an unverified number must not be rendered as a dialable link"
        )
        # The cautious branch must still send the person somewhere real.
        assert "hospital" in body.lower() or "doctor" in body.lower()
        # And it must still state that the app did not call anyone.
        assert "not contacted anyone" in body.lower()

    def test_help_page_shows_the_number_when_verified(self, client):
        """The positive case, so the guard above cannot pass by rendering nothing."""
        body = client.get("/app/help").text
        assert "tel:995" in body, "a verified number should be dialable"
        assert "not contacted anyone" in body.lower()

    def test_chat_emergency_routes_without_the_model(self, client):
        r = client.post("/api/chat", data={"message": "I have chest pain"})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "safety"
        assert body["safety"]["action"] == "emergency"
        assert "995" in body["text"]

    def test_chat_negated_symptom_does_not_alarm(self, client):
        body = client.post("/api/chat", data={"message": "no chest pain today"}).json()
        assert body["mode"] != "safety" or body["safety"]["action"] != "emergency"

    def test_chat_requires_a_message(self, client):
        assert client.post("/api/chat", data={"message": "   "}).status_code == 400
