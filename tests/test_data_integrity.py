"""M1 and M2 acceptance criteria, as executable checks.

These are the data-behaviour tests from the plan. Each one corresponds to a promise the
project makes about how records behave, and each would be a real defect if it failed:

* a cancelled draft writes nothing
* a confirmed reading survives a reload
* a repeated submit does not double-count
* a correction keeps the original
* ``unrecorded`` is never the same as ``not_taken``
* a target with no source is refused rather than stored
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app import repository as repo


class TestReadingLifecycle:
    def test_prepare_writes_nothing(self, conn, user):
        """Phase one must not touch the database."""
        before = repo.count_rows(conn, "bp_reading")
        repo.prepare_reading(user, 138, 86, repo.now_iso())
        assert repo.count_rows(conn, "bp_reading") == before

        # The same through a fresh connection, to prove nothing was committed
        # somewhere invisible to this handle.
        from app.db import connect

        other = connect(conn.execute("PRAGMA database_list").fetchone()[2])
        try:
            assert repo.count_rows(other, "bp_reading") == before
        finally:
            other.close()

    def test_confirm_persists_and_survives_reopen(self, conn, user, db_path):
        draft = repo.prepare_reading(user, 138, 86, repo.now_iso())
        result = repo.confirm_reading(conn, user, draft)
        assert result["deduplicated"] is False

        from app.db import connect

        reopened = connect(db_path)
        try:
            stored = repo.list_readings(reopened, user, days=1)
            assert len(stored) == 1
            assert stored[0]["systolic"] == 138
            assert stored[0]["diastolic"] == 86
        finally:
            reopened.close()

    def test_repeated_submit_is_not_counted_twice(self, conn, user):
        """M1: the same logical reading submitted twice must collapse."""
        measured = repo.now_iso()
        first = repo.confirm_reading(conn, user, repo.prepare_reading(user, 140, 88, measured))
        second_raw = repo.prepare_reading(user, 140, 88, measured)
        second = repo.confirm_reading(conn, user, second_raw)

        assert first["id"] == second["id"]
        assert second["deduplicated"] is True
        assert len(repo.list_readings(conn, user, days=1)) == 1

    def test_two_readings_a_minute_apart_are_kept(self, conn, user):
        """The dedupe key must not be so aggressive that it eats a real second reading."""
        now = datetime.now().astimezone()
        a = repo.confirm_reading(
            conn, user,
            repo.prepare_reading(user, 140, 88, now.isoformat(timespec="seconds")),
        )
        b = repo.confirm_reading(
            conn, user,
            repo.prepare_reading(
                user, 142, 89, (now + timedelta(minutes=1)).isoformat(timespec="seconds")
            ),
        )
        assert a["id"] != b["id"]
        assert len(repo.list_readings(conn, user, days=1)) == 2

    def test_correction_keeps_the_original(self, conn, user):
        """M1: a revision is a chain, not a destructive overwrite."""
        original = repo.confirm_reading(
            conn, user, repo.prepare_reading(user, 148, 92, repo.now_iso())
        )
        replacement = repo.correct_reading(
            conn, user, original["id"], systolic=147, diastolic=91
        )

        # The default view shows only the current version.
        current = repo.list_readings(conn, user, days=1)
        assert len(current) == 1
        assert current[0]["id"] == replacement
        assert current[0]["systolic"] == 147

        # The original is still there when history is requested.
        everything = repo.list_readings(conn, user, days=1, include_superseded=True)
        assert len(everything) == 2

        chain = repo.reading_revision_chain(conn, replacement)
        assert [r["systolic"] for r in chain] == [148, 147]
        assert chain[0]["superseded_by"] == replacement
        assert chain[1]["corrects"] == original["id"]

    def test_measured_and_entered_time_are_distinct(self, conn, user):
        """M1: these are two different questions and must not be conflated."""
        measured = "2026-10-01T07:30:00+08:00"
        repo.confirm_reading(conn, user, repo.prepare_reading(user, 140, 88, measured))
        stored = repo.list_readings(conn, user, days=400)[0]
        assert stored["measured_at"] == measured
        assert stored["entered_at"] != measured

    def test_unusual_reading_is_flagged_not_discarded(self, conn, user):
        """M1: an implausible-but-real reading must be storable, only questioned."""
        draft = repo.prepare_reading(user, 82, 55, repo.now_iso())
        assert draft["concerns"], "an unusual reading should raise a concern"
        result = repo.confirm_reading(conn, user, draft)
        assert result["deduplicated"] is False
        assert repo.list_readings(conn, user, days=1)[0]["systolic"] == 82

    def test_impossible_reading_is_rejected(self, user):
        with pytest.raises(repo.ValidationError):
            repo.prepare_reading(user, "not a number", 88, repo.now_iso())
        with pytest.raises(repo.ValidationError):
            repo.prepare_reading(user, "", "", repo.now_iso())


class TestMedicationStates:
    def test_unrecorded_cannot_be_reported(self, conn, user):
        """The single most important integrity rule in the app.

        'unrecorded' describes our data, not the patient's behaviour. If a user could
        report it, a missing record could be laundered into something the patient said.
        """
        with pytest.raises(repo.ValidationError) as exc:
            repo.record_medication_report(conn, user, status="unrecorded")
        assert "derived" in str(exc.value).lower()

    def test_four_states_are_stored_separately(self, conn, user):
        med = repo.add_medication(conn, user, name="Amlodipine", confirmed_by_user=True)
        for status in ("taken", "not_taken", "unsure"):
            repo.record_medication_report(conn, user, status=status, medication_id=med)

        reports = repo.list_medication_reports(conn, user, days=1)
        assert {r["status"] for r in reports} == {"taken", "not_taken", "unsure"}
        assert all(r["is_self_report"] == 1 for r in reports)

    def test_derived_unrecorded_is_not_a_self_report(self, conn, user):
        from app import stats as stats_mod

        derived = repo.derive_unrecorded(
            conn, user,
            (date.today() - timedelta(days=2)).isoformat(),
            date.today().isoformat(),
        )
        assert derived, "a profile with a reminder time should produce derived gaps"
        for entry in derived:
            assert entry["status"] == "unrecorded"
            # This flag is what stops a downstream consumer treating it as a report.
            assert entry["is_self_report"] == 0

        summary = stats_mod.adherence_summary([], derived, date.today() - timedelta(days=2), date.today())
        assert summary["counts"]["not_taken"] == 0
        assert summary["counts"]["unrecorded"] == len(derived)
        assert summary["self_reported_total"] == 0
        assert "does not mean a dose was missed" in summary["interpretation"]

    def test_derived_rows_are_never_persisted(self, conn, user):
        """Derived gaps are a view. They must not become rows."""
        before = repo.count_rows(conn, "medication_report")
        repo.derive_unrecorded(
            conn, user,
            (date.today() - timedelta(days=5)).isoformat(),
            date.today().isoformat(),
        )
        assert repo.count_rows(conn, "medication_report") == before

    def test_backfilled_report_is_marked(self, conn, user):
        rid = repo.record_medication_report(
            conn, user, status="taken", is_backfilled=True
        )
        stored = [r for r in repo.list_medication_reports(conn, user, days=1) if r["id"] == rid][0]
        assert stored["is_backfilled"] == 1

    def test_unknown_medication_id_is_refused(self, conn, user):
        with pytest.raises(repo.ValidationError):
            repo.record_medication_report(conn, user, status="taken", medication_id="med_nonexistent")

    def test_reports_cannot_cross_profiles(self, conn, user):
        other = repo.create_profile(conn, display_name="Someone Else", age_band="65-74")
        med = repo.add_medication(conn, other, name="Losartan")
        with pytest.raises(repo.ValidationError):
            repo.record_medication_report(conn, user, status="taken", medication_id=med)


class TestProvenance:
    def test_target_without_a_source_is_refused(self, conn, user):
        """M0: never invent a personal goal."""
        with pytest.raises(repo.ValidationError) as exc:
            repo.add_care_plan_item(
                conn, user,
                instruction="Keep your blood pressure under 140.",
                source_type="demo_fictional",
                source_label="demo",
                target_systolic=140,
                # target_source deliberately omitted
            )
        assert "source" in str(exc.value).lower()

    def test_target_with_a_source_is_stored_with_it(self, conn, user):
        pid = repo.add_care_plan_item(
            conn, user,
            instruction="Target recorded by the clinic.",
            source_type="clinician_given",
            source_label="Polyclinic letter, 2026-09-01",
            target_systolic=140,
            target_diastolic=90,
            target_source="Polyclinic letter dated 2026-09-01",
        )
        stored = repo.get_care_plan_item(conn, pid)
        assert stored["target_systolic"] == 140
        assert stored["target_source"] == "Polyclinic letter dated 2026-09-01"

    def test_simulated_flag_is_set_on_demo_data(self, conn, demo_user):
        for table in ("bp_reading", "medication_report", "barrier_event", "care_plan"):
            rows = conn.execute(f"SELECT is_simulated FROM {table}").fetchall()
            assert rows, f"{table} should have demo rows"
            assert all(r["is_simulated"] == 1 for r in rows), f"{table} has an unflagged row"

    def test_three_review_states_are_independent(self, conn, user):
        """A user confirming a name must not imply a clinician reviewed the content."""
        pid = repo.add_care_plan_item(
            conn, user,
            instruction="Take one tablet each morning.",
            source_type="user_reported",
            source_label="Said by the user",
            verified_by_user=True,
        )
        stored = repo.get_care_plan_item(conn, pid)
        assert stored["verified_by_user"] == 1
        assert stored["verified_by_team"] == 0
        assert stored["reviewed_by_clinician"] == 0


class TestBarriers:
    def test_unconfirmed_category_is_stored_as_a_proposal(self, conn, user):
        """M3: a guess must never be stored as a settled fact."""
        bid = repo.record_barrier(
            conn, user,
            user_words="I am not sure what the white one is for.",
            category="unclear_purpose",
            category_confirmed=False,
            proposed_by="model",
        )
        stored = [b for b in repo.list_barriers(conn, user) if b["id"] == bid][0]
        assert stored["category"] == "unclear_purpose"
        assert stored["category_confirmed"] == 0
        assert stored["proposed_by"] == "model"

    def test_user_can_correct_the_category(self, conn, user):
        bid = repo.record_barrier(
            conn, user, user_words="Something.", category="forgot",
            category_confirmed=False,
        )
        repo.confirm_barrier_category(conn, bid, "difficulty_using")
        stored = [b for b in repo.list_barriers(conn, user) if b["id"] == bid][0]
        assert stored["category"] == "difficulty_using"
        assert stored["category_confirmed"] == 1
        assert stored["proposed_by"] == "user"

    def test_unknown_category_is_refused(self, conn, user):
        with pytest.raises(repo.ValidationError):
            repo.record_barrier(conn, user, user_words="x", category="made_up")

    def test_empty_words_are_refused(self, conn, user):
        with pytest.raises(repo.ValidationError):
            repo.record_barrier(conn, user, user_words="   ")

    def test_resolved_barrier_leaves_the_followup_queue(self, conn, user):
        """M3: a settled item must stop being raised."""
        bid = repo.record_barrier(
            conn, user, user_words="I forgot.", category="forgot", category_confirmed=True
        )
        assert any(b["id"] == bid for b in repo.due_followups(conn, user))
        repo.resolve_barrier(conn, bid, "resolved")
        assert not any(b["id"] == bid for b in repo.due_followups(conn, user))

    def test_every_category_has_its_own_support(self):
        """The differentiator, as a property: no two reasons share one answer."""
        from app.tools.handlers import SUPPORT_BY_CATEGORY
        from app.repository import BARRIER_CATEGORIES

        for category in BARRIER_CATEGORIES:
            assert category in SUPPORT_BY_CATEGORY, f"{category} has no support mapped"

        signatures = {
            cat: tuple(sorted(o["id"] for o in opts))
            for cat, opts in SUPPORT_BY_CATEGORY.items()
        }
        # 'other' and 'declined_to_say' may legitimately be thin, but the five
        # substantive categories must all differ from each other.
        substantive = ["forgot", "difficulty_using", "unclear_purpose",
                       "worried_side_effect", "running_out"]
        seen = {signatures[c] for c in substantive}
        assert len(seen) == len(substantive), "two reasons lead to the same support"

    def test_action_requires_a_basis(self, conn, user):
        with pytest.raises(repo.ValidationError):
            repo.add_support_action(
                conn, user, title="Read about your medicine", basis_type="education"
            )
        ok = repo.add_support_action(
            conn, user, title="Read about your medicine",
            basis_type="education", basis_id="edu_amlodipine_purpose",
        )
        assert ok


class TestPreferences:
    def test_reminder_change_does_not_touch_the_plan(self, conn, user):
        """M3: changing when the app nags must not change the prescription."""
        repo.add_care_plan_item(
            conn, user, instruction="One tablet each morning.",
            source_type="demo_fictional", source_label="demo",
        )
        plan_before = [dict(p) for p in repo.list_care_plan(conn, user)]

        repo.update_preferences(conn, user, reminder_time="21:30")

        profile = repo.get_profile(conn, user)
        assert profile["reminder_time"] == "21:30"
        plan_after = [dict(p) for p in repo.list_care_plan(conn, user)]
        assert plan_before == plan_after

    def test_bad_time_is_refused(self, conn, user):
        with pytest.raises(repo.ValidationError):
            repo.update_preferences(conn, user, reminder_time="25:99")


class TestKnowledgeBase:
    def test_real_content_loads_without_rejection(self, knowledge):
        assert knowledge.sources_loaded > 0
        assert knowledge.facts_loaded > 0

    def test_every_enabled_fact_has_a_source(self, conn, knowledge):
        rows = conn.execute(
            """SELECT f.id FROM education_fact f
               LEFT JOIN education_source s ON s.id = f.source_id
               WHERE f.enabled = 1 AND s.id IS NULL"""
        ).fetchall()
        assert not rows, f"facts without provenance: {[r['id'] for r in rows]}"

    def test_disabled_facts_are_unreachable(self, conn, knowledge):
        """A fact held back must not be retrievable, whatever the query."""
        disabled = conn.execute(
            "SELECT id, topic FROM education_fact WHERE enabled = 0"
        ).fetchall()
        assert disabled, "the demo relies on at least one held-back fact existing"

        for row in disabled:
            found = repo.search_facts(conn, topic=row["topic"], limit=200)
            assert row["id"] not in {f["id"] for f in found}
            assert repo.get_fact(conn, row["id"]) is None

    def test_no_fact_contains_dosing_guidance(self, conn, knowledge):
        """The 'never crosses into medication advice' requirement, checked at the root."""
        banned = [
            "mg", "milligram", "missed dose", "double the dose", "skip the dose",
            "stop taking", "increase the dose", "decrease the dose", "take two",
            "half a tablet", "half a pill",
        ]
        rows = conn.execute(
            "SELECT id, statement FROM education_fact WHERE enabled = 1"
        ).fetchall()
        for row in rows:
            lowered = row["statement"].lower()
            for phrase in banned:
                assert phrase not in lowered, (
                    f"fact {row['id']} contains '{phrase}', which is dosing guidance"
                )

    def test_placeholder_cannot_ship_enabled(self, conn, knowledge):
        rows = conn.execute(
            """SELECT id, statement FROM education_fact
               WHERE enabled = 1 AND (statement LIKE '%PLACEHOLDER%'
                                      OR statement LIKE '%NOT SHOWN%')"""
        ).fetchall()
        assert not rows, "a scaffold placeholder is enabled"

    def test_no_numeric_threshold_in_enabled_content(self, conn, knowledge):
        """The app must not classify a reading. No enabled fact may state a cut-off.

        This encodes the finding that MOH and HealthHub publish no numeric emergency
        threshold: if our own content has none, the app cannot leak one by retrieval.
        """
        import re

        rows = conn.execute(
            """SELECT id, statement FROM education_fact
               WHERE enabled = 1 AND topic IN ('when_to_seek_help', 'how_to_measure')"""
        ).fetchall()
        pattern = re.compile(r"\b\d{2,3}\s*/\s*\d{2,3}\b")
        for row in rows:
            assert not pattern.search(row["statement"]), (
                f"fact {row['id']} states a numeric blood pressure threshold"
            )
