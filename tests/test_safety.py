"""M6 acceptance criteria: the boundary cases must be reproducible.

The plan says "the prescribed boundary cases reproduce; ordinary chat cannot override a
rule output". These tests are that sentence made checkable.

The most important property here is ordering. If a message contains both an emergency
phrase and a request to change a dose, the emergency must win. That is not a nicety: it
is the difference between a user in trouble and a user being politely told about
prescribing policy.
"""

from __future__ import annotations

import pytest

from app.safety import route as safety_route
from app.safety.rules import RULES, rule_metadata


class TestEmergencyBeforeEverything:
    @pytest.mark.parametrize(
        "text",
        [
            "I have chest pain",
            "I cannot breathe properly",
            "my face is drooping and my speech is slurred",
            "he passed out and is confused",
            "my lips are turning blue",
            "there is heavy bleeding that won't stop bleeding",
        ],
    )
    def test_emergency_phrases_trigger_help(self, text):
        verdict = safety_route(text, {})
        assert verdict.action == "emergency", f"'{text}' should be an emergency"
        assert verdict.blocks_model is True
        assert verdict.message

    def test_emergency_beats_a_medication_request(self):
        """The ordering guarantee, stated as a test.

        A user says something that is BOTH an emergency and a request to change a dose.
        Help must come first.
        """
        verdict = safety_route(
            "I have chest pain and I want to stop taking my tablets", {}
        )
        assert verdict.action == "emergency"
        assert "chest pain" in verdict.reason.lower() or "chest" in verdict.reason.lower()

    def test_emergency_beats_a_clarification(self):
        verdict = safety_route("my blood pressure was very high and now I cannot breathe", {})
        assert verdict.action == "emergency"

    def test_emergency_sources_are_attached(self):
        verdict = safety_route("chest pain", {})
        assert verdict.sources, "an emergency verdict must cite where it came from"
        assert verdict.rule_id

    def test_negated_symptoms_do_not_trigger(self):
        """A false positive here trains the user to ignore the alarm.

        This grew out of a real defect. Per-rule ``exclude_patterns`` lists covered
        only the phrasings someone had thought of, so three enabled red-flag rules had
        no exclusion list at all and fired on plain denials: "no heavy bleeding" and
        "I did not have a seizure" both raised the emergency panel. A false alarm on an
        emergency screen is the most harmful failure in this product, because the next
        alarm may be real and the user has learned to dismiss it.

        The fix moved negation detection into the matcher, so it applies to every rule
        including ones added later. These cases are the regression set.
        """
        denials = [
            "no chest pain",
            "no heavy bleeding",
            "I did not have a seizure",
            "there was no seizure",
            "no confusion",
            "she did not faint",
            "no shortness of breath",
            "no weakness or numbness",
            "I have not had any bleeding",
            "the bleeding has stopped",
            "no chest pain today",
            "my lips are not turning blue",
            "he denies any chest pain",
            "I have no blood in my vomit",
            "no head injury",
            "the seizure resolved",
            "not short of breath",
            "the fit is over",
            "my chest pain went away",
            "the numbness has gone",
            "no bleeding at all",
        ]
        for text in denials:
            verdict = safety_route(text, {})
            assert verdict.action not in {"emergency", "urgent_advice"}, (
                f"'{text}' states the symptom is ABSENT and must not alarm"
            )

    def test_continuation_phrases_still_alarm(self):
        """The trap in the negation fix: 'will not stop' LOOKS like a denial.

        Every continuation phrase contains a negation token, so a naive negation check
        silences a genuine emergency. "The bleeding will not stop" is a cry for help,
        not a denial, and these cases guard the ordering that keeps it one.
        """
        continuations = [
            "the bleeding will not stop",
            "my bleeding won't stop",
            "bleeding that does not stop",
            "my bleeding wont stop",
            "bleeding that doesn't stop",
        ]
        for text in continuations:
            verdict = safety_route(text, {})
            assert verdict.action in {"emergency", "urgent_advice"}, (
                f"'{text}' describes an ONGOING emergency and must alarm"
            )

    def test_a_denial_in_one_clause_does_not_mask_a_symptom_in_the_next(self):
        """Clause scoping: the dangerous failure mode of a window-based check."""
        for text in [
            "no chest pain but I cannot breathe",
            "I did not faint earlier but now I have chest pain",
            "the numbness has gone but the bleeding will not stop",
        ]:
            verdict = safety_route(text, {})
            assert verdict.action in {"emergency", "urgent_advice"}, (
                f"'{text}' contains a real symptom after a denial"
            )

    def test_uncertainty_is_not_reassurance(self):
        """"Not sure if it is chest pain" is a live concern, not a denial."""
        for text in [
            "I am not sure if it is chest pain",
            "not sure whether this is chest pain",
        ]:
            verdict = safety_route(text, {})
            assert verdict.action in {"emergency", "urgent_advice"}, (
                f"'{text}' expresses uncertainty about a real symptom"
            )

    def test_unnegated_symptoms_still_alarm(self):
        """The positive half, so the negation check cannot pass by silencing everything."""
        for text in [
            "I have chest pain",
            "chest pain that started an hour ago",
            "heavy bleeding",
            "I am bleeding a lot",
            "I had a seizure",
            "my lips are turning blue",
            "I cannot breathe",
            "I fell and hit my head",
            "sudden weakness on one side",
            "I was confused and then passed out",
        ]:
            verdict = safety_route(text, {})
            assert verdict.action in {"emergency", "urgent_advice"}, (
                f"'{text}' is a real symptom and must alarm"
            )

    def test_urgent_is_not_escalated_to_emergency(self):
        verdict = safety_route("I fell and hit my head", {})
        assert verdict.action == "urgent_advice"

    def test_urgent_message_names_the_escalation_trigger(self):
        """An urgent message must not close off the emergency path."""
        verdict = safety_route("I hit my head when I fell", {})
        lowered = verdict.message.lower()
        assert "995" in lowered, "the urgent message should name the emergency route"
        assert "drowsy" in lowered or "confused" in lowered or "vomit" in lowered


class TestMedicationBoundaries:
    @pytest.mark.parametrize(
        "text",
        [
            "should I change my dose",
            "can I double the dose today",
            "I want to stop taking my medication",
            "should I take an extra pill",
        ],
    )
    def test_dose_and_stopping_requests_are_refused(self, text):
        verdict = safety_route(text, {})
        assert verdict.action == "refuse", f"'{text}' should be refused"
        assert verdict.blocks_model is True

    def test_missed_dose_question_is_refused(self):
        verdict = safety_route("I missed my dose, should I take it now?", {})
        assert verdict.action == "refuse"
        assert verdict.details.get("redirect") in {"pharmacist", "doctor_or_pharmacist"}

    def test_refusal_is_a_redirect_not_a_dead_end(self):
        """Every refusal must offer somewhere to go."""
        for text in ["should I stop taking my medicine", "is my medication causing this"]:
            verdict = safety_route(text, {})
            assert verdict.action == "refuse"
            assert verdict.details.get("redirect"), f"'{text}' refuses with no route"
            assert verdict.details.get("offer_question") is True

    def test_reporting_a_missed_dose_is_not_refused(self):
        """The false positive that would make the app obstructive.

        'I forgot my tablet yesterday' is a REPORT. Refusing it would be exactly wrong:
        recording that is the app's core purpose.
        """
        verdict = safety_route("I forgot my tablet yesterday morning", {})
        assert verdict.action != "refuse", "reporting a missed dose must not be refused"

    def test_pill_identification_is_refused(self):
        verdict = safety_route("what is this white round pill?", {})
        assert verdict.action == "refuse"
        assert verdict.details.get("redirect") == "pharmacist"

    def test_stopping_the_reminder_is_allowed(self):
        """The exclude patterns must work: this is a preference, not a clinical act."""
        verdict = safety_route("please stop the reminder at 8am", {})
        assert verdict.action != "refuse"

    def test_helping_prepare_for_the_doctor_is_allowed(self):
        """Another likely false positive, guarded deliberately."""
        for text in [
            "help me tell my doctor about this",
            "how do i tell my doctor",
            "I want questions for my doctor",
        ]:
            verdict = safety_route(text, {})
            assert verdict.action != "refuse", f"'{text}' should be supported, not refused"

    def test_diagnosis_request_is_refused(self):
        verdict = safety_route("do I have high blood pressure?", {})
        assert verdict.action == "refuse"


class TestClarification:
    def test_vague_feeling_offers_options(self):
        verdict = safety_route("I don't feel well", {})
        assert verdict.action == "clarify"
        assert verdict.details.get("options")
        # A way out must exist in every clarification.
        ids = {o.get("id") for o in verdict.details["options"]}
        assert "skip" in ids, "a clarification must always allow skipping"

    def test_ambiguous_medicine_asks_which(self):
        verdict = safety_route("what is this medicine for?", {"medication_count": 2})
        assert verdict.action in {"clarify", "refuse"}

    def test_unknown_medication_reference_is_a_boundary(self):
        verdict = safety_route(
            "what is my pill for?",
            {"mentions_unknowable_medication": True, "medication_count": 2},
        )
        assert verdict.action in {"clarify", "refuse"}


class TestOrdinaryRequestsPass:
    @pytest.mark.parametrize(
        "text",
        [
            "I want to record my blood pressure",
            "my readings were 138 over 86",
            "I am running out of my tablets",
            "I keep forgetting to write it down",
            "can I see my numbers",
            "I would like to prepare for my appointment",
        ],
    )
    def test_normal_conversation_is_allowed(self, text):
        verdict = safety_route(text, {})
        assert verdict.action == "allow", f"'{text}' should pass through, got {verdict.action}"


class TestRuleIntegrity:
    def test_every_loaded_rule_has_a_source(self):
        for rule in RULES.rules:
            assert rule.sources, f"rule {rule.id} loaded with no source"

    def test_no_rule_was_dropped_for_missing_sources(self):
        assert not RULES.problems, (
            "a rule file declared a rule with no source and it was dropped: "
            + "; ".join(RULES.problems)
        )

    def test_disabled_rules_are_reported_not_hidden(self):
        meta = rule_metadata()
        assert meta["total"] > meta["enabled"], (
            "the demo expects at least one rule held back pending review"
        )
        held = [r for r in meta["rules"] if not r["enabled"]]
        assert held, "held-back rules should be visible in the metadata"
        for rule in held:
            assert rule["review_state"] in {"pending_review", "unreviewed"}

    def test_no_numeric_threshold_is_used_as_a_trigger(self):
        """No rule may fire on a blood pressure number.

        MOH publishes no numeric emergency threshold, so a rule keyed to one would be
        an invented clinical claim. This test is the guard.
        """
        import re

        pattern = re.compile(r"\b1[0-9]{2}\s*/\s*[0-9]{2,3}\b")
        for rule in RULES.rules:
            for p in rule.patterns:
                assert not pattern.search(p), f"rule {rule.id} triggers on a number"

    def test_emergency_rules_all_cite_a_source(self):
        for rule in RULES.of_kind("red_flag"):
            assert rule.sources, f"red flag {rule.id} has no citation"
            assert rule.review_state in {"team_checked", "clinician_reviewed", "pending_review"}


class TestEmergencyConfig:
    def test_number_is_verified_and_matches_a_source(self):
        from app.llm.help import emergency_info

        info = emergency_info()
        assert info["verified"] is True, "the demo depends on a sourced emergency number"
        assert info["number"] == "995"
        assert info["sources"], "the number must cite where it came from"

    def test_help_text_says_the_app_did_not_call_anyone(self):
        from app.llm.help import emergency_info

        info = emergency_info()
        assert "cannot" in info["app_does_not"].lower()
        assert "yourself" in info["app_does_not"].lower()

    def test_no_blood_pressure_threshold_in_emergency_config(self):
        """Directly encodes the research finding.

        Neither MOH nor HealthHub publishes a mmHg cut-off for calling 995. If our
        configuration contained one, the app would be asserting something no source
        supports. This walks the whole config file so a threshold cannot be added
        anywhere without the test noticing.
        """
        import json
        import re

        from app.llm.help import EMERGENCY_FILE

        raw = json.loads(EMERGENCY_FILE.read_text(encoding="utf-8"))

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    yield from walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    yield from walk(value, f"{path}[{i}]")
            elif isinstance(node, str):
                yield path, node

        pattern = re.compile(r"\b\d{2,3}\s*/\s*\d{2,3}\b")
        offenders = [
            (path, text)
            for path, text in walk(raw)
            if pattern.search(text) and "NOT" not in text.upper()
        ]
        assert not offenders, (
            "the emergency configuration states a blood pressure threshold, which no "
            f"Singapore source supports: {offenders}"
        )
