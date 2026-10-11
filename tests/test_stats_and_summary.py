"""M4 and M5 acceptance criteria.

The claims under test:

* the numbers the user sees are computed, reproducible, and always carry their
  denominator
* insufficient data produces a refusal to describe, not a default value
* the chart breaks at a gap instead of drawing across it
* the summary contains nothing that is not in the records
* the summary never turns "no record" into "did not take it"
* no target means no target comparison
* the model's summary context contains no invented fields
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytest

from app import repository as repo
from app import stats as stats_mod
from app.summary import (
    OMITTABLE_KEYS,
    apply_omissions,
    build_summary_facts,
    narrative_context,
)


def _add_reading(conn, user_id, day: date, systolic: int, diastolic: int):
    measured = datetime.combine(day, datetime.min.time()).replace(hour=8).astimezone().isoformat(
        timespec="seconds"
    )
    return repo.confirm_reading(
        conn, user_id, repo.prepare_reading(user_id, systolic, diastolic, measured)
    )["id"]


class TestStatistics:
    def test_insufficient_data_refuses_to_average(self, conn, user):
        """M4: with one reading, the honest answer is 'not enough'."""
        _add_reading(conn, user, date.today(), 140, 88)
        bundle = stats_mod.build_period_stats(conn, user, days=14)
        assert bundle["readings"]["n"] == 1
        assert bundle["readings"]["sufficient"] is False
        assert bundle["readings"]["mean_systolic"] is None, "must not invent a mean"
        assert "not enough" in bundle["readings"]["note"].lower()

    def test_average_is_computed_and_reproducible(self, conn, user):
        today = date.today()
        _add_reading(conn, user, today - timedelta(days=2), 140, 90)
        _add_reading(conn, user, today - timedelta(days=1), 150, 100)
        bundle = stats_mod.build_period_stats(conn, user, days=14)
        assert bundle["readings"]["n"] == 2
        assert bundle["readings"]["mean_systolic"] == 145.0
        assert bundle["readings"]["mean_diastolic"] == 95.0

        # Recomputing must give the same answer. Determinism is the point.
        again = stats_mod.build_period_stats(conn, user, days=14)
        assert again["readings"]["mean_systolic"] == bundle["readings"]["mean_systolic"]

    def test_every_statistic_carries_its_denominator(self, conn, user):
        for i in range(5):
            _add_reading(conn, user, date.today() - timedelta(days=i), 140 + i, 88)
        bundle = stats_mod.build_period_stats(conn, user, days=14)
        r = bundle["readings"]
        assert r["n"] == 5
        assert r["window"]["days"] == 14
        assert str(r["n"]) in r["note"], "the note must state the sample size"
        assert r["coverage"]["window_days"] == 14
        assert r["coverage"]["days_with_data"] == 5
        assert r["coverage"]["missing_days"] == 9

    def test_comparison_refuses_when_a_window_is_thin(self, conn, user):
        """M4: do not invite the user to read a trend into noise."""
        _add_reading(conn, user, date.today(), 145, 90)
        comparison = stats_mod.compare_windows(repo.list_readings(conn, user, days=60), 14)
        assert comparison["comparable"] is False
        assert comparison["delta_systolic"] is None
        assert comparison["delta_diastolic"] is None
        assert "not enough" in comparison["explanation"].lower()

    def test_comparison_describes_without_explaining(self, conn, user):
        today = date.today()
        # Previous fortnight: lower.
        for i in range(15, 21):
            _add_reading(conn, user, today - timedelta(days=i), 135, 85)
        # Recent fortnight: higher.
        for i in range(0, 6):
            _add_reading(conn, user, today - timedelta(days=i), 150, 95)

        comparison = stats_mod.compare_windows(repo.list_readings(conn, user, days=60), 14)
        assert comparison["comparable"] is True
        assert comparison["delta_systolic"] > 0
        explanation = comparison["explanation"].lower()
        assert "does not explain why" in explanation
        # No causal or evaluative verbs anywhere in the generated text.
        for banned in ("improved", "improving", "worse", "worsening", "because", "due to", "caused"):
            assert banned not in explanation

    def test_series_records_gaps_explicitly(self, conn, user):
        today = date.today()
        _add_reading(conn, user, today - timedelta(days=3), 140, 88)
        _add_reading(conn, user, today, 142, 89)
        series = stats_mod.series_for_chart(
            repo.list_readings(conn, user, days=30), today - timedelta(days=3), today
        )
        assert len(series["points"]) == 4
        assert series["days_with_data"] == 2
        assert series["days_without_data"] == 2
        # The missing days are present as entries with has_data False, which is what
        # lets the renderer break the line rather than draw across.
        missing = [p for p in series["points"] if not p["has_data"]]
        assert len(missing) == 2
        for p in missing:
            assert "systolic" not in p, "a gap must not carry a fabricated value"

    def test_corrected_readings_are_flagged_in_the_series(self, conn, user):
        today = date.today()
        original = _add_reading(conn, user, today, 148, 92)
        repo.correct_reading(conn, user, original, systolic=147, diastolic=91)
        series = stats_mod.series_for_chart(
            repo.list_readings(conn, user, days=30), today, today
        )
        assert series["points"][0]["had_correction"] is True

    def test_superseded_reading_is_excluded_from_statistics(self, conn, user):
        """A corrected value must not inflate the count or skew the mean."""
        today = date.today()
        original = _add_reading(conn, user, today, 200, 120)
        repo.correct_reading(conn, user, original, systolic=140, diastolic=88)
        bundle = stats_mod.build_period_stats(conn, user, days=14)
        assert bundle["readings"]["n"] == 1
        assert bundle["readings"]["max_systolic"] == 140


class TestAdherenceStatistics:
    def test_unrecorded_is_counted_apart(self, conn, user):
        from app import stats as stats_mod

        med = repo.add_medication(conn, user, name="Amlodipine")
        repo.record_medication_report(conn, user, status="taken", medication_id=med)
        derived = repo.derive_unrecorded(
            conn, user,
            (date.today() - timedelta(days=2)).isoformat(),
            date.today().isoformat(),
        )
        summary = stats_mod.adherence_summary(
            repo.list_medication_reports(conn, user, days=7), derived,
            date.today() - timedelta(days=2), date.today(),
        )
        assert summary["counts"]["taken"] >= 1
        assert summary["counts"]["unrecorded"] == len(derived)
        assert summary["counts"]["not_taken"] == 0
        assert "does not mean a dose was missed" in summary["interpretation"]

    def test_no_compliance_rate_is_ever_produced(self, conn, user):
        """There is no defensible denominator, so there must be no percentage."""
        from app import stats as stats_mod

        derived = repo.derive_unrecorded(
            conn, user,
            (date.today() - timedelta(days=5)).isoformat(),
            date.today().isoformat(),
        )
        summary = stats_mod.adherence_summary(
            [], derived, date.today() - timedelta(days=5), date.today()
        )
        for key in summary:
            assert "rate" not in key.lower()
            assert "percent" not in key.lower()
            assert "compliance" not in key.lower()
        assert "not a measure of true adherence" in summary["note"]


class TestSummaryFacts:
    def test_summary_only_contains_recorded_data(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)

        # Every numeric claim traces to a record id.
        assert facts["readings"]["n"] > 0
        assert facts["readings"]["record_ids"]
        assert len(facts["readings"]["record_ids"]) == facts["readings"]["n"]

        # Every section that makes a claim carries its provenance list.
        recorded = facts["coverage"]["record_ids"]
        assert recorded

    def test_summary_never_turns_no_record_into_not_taken(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)
        assert facts["medication"]["counts"]["unrecorded"] > 0, (
            "the demo patient is meant to have unrecorded days"
        )
        assert "does not mean a dose was missed" in facts["medication"]["statement"]

        # No report row may carry the derived status.
        for report in facts["medication"]["reports"]:
            assert report["status"] != "unrecorded"

    def test_patient_words_are_labelled_as_reported(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)
        block = facts["reported_by_patient"]
        assert "not diagnoses" in block["intro"].lower()
        assert "not been checked by a clinician" in block["intro"].lower()
        for difficulty in block["difficulties"]:
            assert difficulty["label"] in {
                "confirmed by the patient", "not confirmed by the patient"
            }

    def test_no_target_comparison_without_a_sourced_target(self, conn, demo_user):
        """M4: absent a sourced personal target, no 'on target' judgement may appear."""
        facts = build_summary_facts(conn, demo_user, days=14)
        assert facts["readings"]["target_comparison"] is None

    def test_target_comparison_appears_only_with_a_source(self, conn, user):
        repo.add_care_plan_item(
            conn, user, instruction="Target from the clinic letter.",
            source_type="clinician_given",
            source_label="Polyclinic letter 2026-09-01",
            target_systolic=140, target_diastolic=90,
            target_source="Polyclinic letter dated 2026-09-01",
        )
        today = date.today()
        for i in range(4):
            _add_reading(conn, user, today - timedelta(days=i), 145, 92)

        facts = build_summary_facts(conn, user, days=14)
        comparison = facts["readings"]["target_comparison"]
        assert comparison is not None
        assert comparison["available"] is True
        assert comparison["target_source"] == "Polyclinic letter dated 2026-09-01"
        # The wording compares two numbers and explicitly declines to assess.
        assert "not an assessment of control" in comparison["statement"]

    def test_summary_carries_a_disclaimer_and_generator(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)
        assert facts["meta"]["disclaimer"]
        assert "not a medical report" in facts["meta"]["disclaimer"].lower()
        assert facts["meta"]["generator"] == "CareSteps prototype"
        assert facts["meta"]["all_simulated"] is True

    def test_omission_removes_only_omittable_sections(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)
        trimmed = apply_omissions(facts, ["reported_by_patient.notes"])

        assert trimmed["reported_by_patient"]["notes"] == []
        # The numbers are not omittable: a page with the caveats but not the data
        # would be misleading in the other direction.
        assert trimmed["readings"]["n"] == facts["readings"]["n"]
        assert trimmed["meta"]["disclaimer"] == facts["meta"]["disclaimer"]

    def test_non_omittable_path_is_ignored(self, conn, demo_user):
        facts = build_summary_facts(conn, demo_user, days=14)
        trimmed = apply_omissions(facts, ["readings.n", "meta.disclaimer", "made.up"])
        assert trimmed["readings"]["n"] == facts["readings"]["n"]

    def test_omittable_keys_all_reachable(self, conn, demo_user):
        """Every advertised omittable path must actually exist in the facts dict."""
        facts = build_summary_facts(conn, demo_user, days=14)
        for path in OMITTABLE_KEYS:
            section, _, leaf = path.partition(".")
            assert section in facts, f"{path} names a missing section"
            assert leaf in facts[section], f"{path} names a missing key"

    def test_narrative_context_is_minimal_and_invents_nothing(self, conn, demo_user):
        """The model gets a trimmed context, and nothing beyond the records."""
        facts = build_summary_facts(conn, demo_user, days=14)
        context = narrative_context(facts)

        assert set(context) == {
            "period", "readings_count", "readings_sufficient", "coverage_statement",
            "medication_statement", "recorded_target", "open_difficulties",
            "question_count", "disclaimer",
        }
        # No raw record dumps, no per-reading detail the model could misattribute.
        assert "record_ids" not in str(context)
        assert context["readings_count"] == facts["readings"]["n"]


class TestSummaryContainsNoClinicalClaims:
    def test_no_diagnosis_words_in_generated_text(self, conn, demo_user):
        """Walk the generated summary for language the app must never produce.

        Note the nuance: the disclaimer legitimately contains the word "diagnoses" in
        a NEGATION ("these are not diagnoses"). Blanket-forbidding the substring would
        force us to delete the very wording that protects the reader. So this checks
        for affirmative clinical claims, allowing the disclaimers that deny them.
        """
        import json
        import re

        facts = build_summary_facts(conn, demo_user, days=14)
        blob = json.dumps(facts).lower()

        # Affirmative claim forms: "diagnosed with", "the diagnosis is", "prescribed".
        for pattern in (
            r"diagnosed with",
            r"diagnosis is",
            r"\bprescribed\b",
            r"\byou should\b",
            r"\bwe recommend\b",
            r"\bhas improved\b",
            r"\bis stable\b",
            r"\bunder control\b",
        ):
            assert not re.search(pattern, blob), f"the summary contains '{pattern}'"

    def test_no_send_or_contact_claim(self, conn, demo_user):
        import json

        facts = build_summary_facts(conn, demo_user, days=14)
        blob = json.dumps(facts).lower()
        for banned in ("sent to", "shared with", "emailed", "notified"):
            assert banned not in blob

    def test_all_record_ids_are_plausible(self, conn, demo_user):
        """A record id that does not exist would make the traceability claim false."""
        facts = build_summary_facts(conn, demo_user, days=14)
        for reading_id in facts["readings"]["record_ids"]:
            assert repo.get_reading(conn, reading_id) is not None

        for question in facts["questions"]["items"]:
            for qid in question["record_ids"]:
                found = conn.execute(
                    "SELECT id FROM consultation_question WHERE id = ?", (qid,)
                ).fetchone()
                assert found is not None
