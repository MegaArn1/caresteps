"""Tests for the degraded conversation layer and the model-output checks.

This file exists because an audit of the documentation found a claim that
**"degraded mode is tested"** which was not true: no test imported
``app.llm.degraded``. It was found by grepping the test suite rather than by reading
the docs, which is the only way that class of error gets caught.

The gap mattered more than an ordinary missing test, because degraded mode is the path
the demonstration actually runs in - there is no model endpoint configured, so every
live-looking screen in the demo goes through this module. An untested demo path is the
worst possible place to have no coverage.

Two things are covered here:

* ``app/llm/degraded.py``  - the rules-only conversation layer
* ``app/llm/orchestrator.py`` - ``check_output``, ``_collect_numbers`` and
  ``_safety_context``, which decide whether model prose is shown at all
"""

from __future__ import annotations

import pytest

from app.llm import degraded
from app.llm.orchestrator import _collect_numbers, _safety_context, check_output


class TestIntentClassification:
    """The router decides which of a small number of scripted replies is used."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("I want to prepare for my appointment", "build_summary"),
            ("help me tell my doctor about this", "build_summary"),
            # The ordering guarantee: a difficulty wins over a routine record, because
            # "readings" contains "reading" and would otherwise be swallowed.
            ("I keep forgetting to write down my readings", "barrier"),
            ("I am running out of my tablets", "barrier"),
            ("I am not sure what the second tablet is for", "barrier"),
            ("my numbers look bad", "view_trends"),
            ("show my plan", "view_plan"),
            ("I recorded 150 over 95", "record_reading"),
            ("my blood pressure was 138 over 86", "record_reading"),
            ("I took my tablet today", "record_medication"),
            ("something about the weather", "unknown"),
        ],
    )
    def test_intent_routing(self, text, expected):
        assert degraded.classify_intent(text) == expected

    def test_prose_about_readings_is_not_a_reading(self):
        """A digit is required, so talking about readings is not recording one."""
        assert degraded.classify_intent("my readings have been consistent") != "record_reading"
        assert degraded.classify_intent("I do not like writing readings down") != "record_reading"

    def test_empty_input_is_unknown_not_a_crash(self):
        assert degraded.classify_intent("") == "unknown"
        assert degraded.classify_intent(None) == "unknown"


class TestNumberExtraction:
    def test_reads_two_plausible_numbers(self):
        assert degraded._extract_bp_numbers("my reading was 138 over 86") == (138, 86)

    def test_refuses_to_guess_from_one_number(self):
        """Returning a fabricated diastolic would be worse than asking again."""
        assert degraded._extract_bp_numbers("it was 150") == (None, None)
        assert degraded._extract_bp_numbers("no numbers here") == (None, None)

    def test_inverted_values_keep_their_written_order(self):
        """82 over 150 must be reported as (82, 150), not silently rearranged.

        An earlier implementation took the largest number as systolic, which turned
        "82 over 150" into a plausible-looking (150, 82) and offered it back for
        confirmation - inventing a normal reading out of an inverted one. Now the
        written order is preserved so the user is asked about what they actually
        said. The confirmation screen is where a genuinely inverted entry gets
        noticed and corrected.
        """
        assert degraded._extract_bp_numbers("82 over 150") == (82, 150)

    def test_pair_order_is_respected_for_both_separators(self):
        assert degraded._extract_bp_numbers("138 over 86") == (138, 86)
        assert degraded._extract_bp_numbers("138/86") == (138, 86)
        # Written inverted, kept inverted.
        assert degraded._extract_bp_numbers("86/138") == (86, 138)

    def test_out_of_range_pair_is_rejected(self):
        """A pairing outside physical bounds is a typo, not a reading."""
        assert degraded._extract_bp_numbers("5 over 900") == (None, None)

    def test_picks_the_two_largest_plausible_numbers(self):
        # A pulse is often in the same sentence; the top two BP numbers should win.
        sys_v, dia_v = degraded._extract_bp_numbers("138 over 86 and pulse 72")
        assert sys_v == 138
        assert dia_v == 86


class TestDegradedReplies:
    def test_every_reply_carries_text_and_a_payload(self):
        for intent_text in (
            "I want to prepare for my appointment",
            "I keep forgetting to write down my readings",
            "my numbers look bad",
            "show my plan",
            "I recorded 150 over 95",
            "I took my tablet today",
            "something unrelated",
        ):
            reply = degraded.reply(intent_text, {})
            assert reply.text.strip(), f"no text for {intent_text!r}"
            assert isinstance(reply.payload, dict)
            assert reply.mode == "degraded"

    def test_reading_with_numbers_asks_for_confirmation(self):
        reply = degraded.reply("I measured 150 over 95", {})
        assert reply.handled_intent == "record_reading"
        assert reply.payload["kind"] == "reading_draft"
        assert reply.payload["needs_confirmation"] is True
        assert reply.payload["systolic"] == 150

    def test_reading_without_numbers_asks_instead(self):
        reply = degraded.reply("I want to record my blood pressure", {})
        assert reply.payload["kind"] == "ask_reading"

    def test_medication_reply_offers_all_four_choices_including_declining(self):
        """Declining must be offered, not hidden. M3 requires it."""
        reply = degraded.reply("I took my tablet", {})
        ids = {o["id"] for o in reply.payload["options"]}
        assert {"taken", "not_taken", "unsure"}.issubset(ids)
        assert "skip" in ids, "there must always be a way to decline"

    def test_barrier_reply_offers_reasons_and_a_skip(self):
        reply = degraded.reply("I keep forgetting", {})
        assert reply.handled_intent == "barrier"
        ids = {o["id"] for o in reply.payload["options"]}
        assert "forgot" in ids
        assert "declined_to_say" in ids, "declining is a first-class choice"

    def test_stats_reply_states_the_sample_size(self):
        """Every number shown in degraded mode still carries its denominator."""
        stats = {
            "period_days": 14,
            "readings": {
                "n": 10, "sufficient": True, "mean_systolic": 141.9,
                "mean_diastolic": 88.0,
                "note": "Based on 10 reading(s) across 10 day(s). 4 day(s) have no record.",
            },
        }
        reply = degraded.reply("how am I doing", {"stats": stats})
        assert "10 readings" in reply.text
        assert "141.9" in reply.text
        assert "does not explain why" in reply.text

    def test_insufficient_data_does_not_produce_an_average(self):
        stats = {
            "period_days": 14,
            "readings": {
                "n": 1, "sufficient": False, "mean_systolic": None,
                "mean_diastolic": None,
                "note": "Only 1 reading(s) recorded. That is not enough to describe an average.",
            },
        }
        reply = degraded.reply("how am I doing", {"stats": stats})
        assert "not enough" in reply.text.lower()
        assert "None" not in reply.text

    def test_unknown_intent_offers_working_shortcuts(self):
        """Failing to understand must still leave the user somewhere to go."""
        reply = degraded.reply("the weather is nice", {})
        shortcuts = reply.payload.get("shortcuts")
        assert shortcuts, "an unrecognised message must offer real alternatives"
        assert any("reading" in s["id"] for s in shortcuts)

    def test_unavailable_message_is_not_emitted_as_a_medicine_answer(self):
        """A medicine question must NOT be answered from nothing.

        This records the actual behaviour: the safety router refuses a generic
        medicine question, so the degraded layer never reaches a knowledge answer.
        ``UNAVAILABLE_MESSAGE`` is held in reserve for a case the router does not
        intercept, and is asserted to say the app cannot answer - it must never
        contain an actual explanation.
        """
        lowered = degraded.UNAVAILABLE_MESSAGE.lower()
        assert "not available" in lowered
        assert "pharmacist" in lowered or "doctor" in lowered
        # It must not cross from explaining that it cannot help into explaining a drug.
        for banned in ("mg", "dose", "twice a day", "with food"):
            assert banned not in lowered

    def test_empty_first_line_of_help_guarantee(self):
        summary = degraded.summarise_degraded()
        assert summary["available"]
        assert summary["unavailable"]
        assert "memory" in summary["guarantee"], (
            "the guarantee should state that nothing is generated from model memory"
        )


class TestSafetyContext:
    """``_safety_context`` decides when a medicine question becomes a refusal."""

    def test_reporting_a_missed_tablet_is_not_an_unknown_medicine(self, conn, user):
        """The bug this narrows: 'I forgot my tablet yesterday' was once refused."""
        ctx = _safety_context(conn, user, "I forgot my tablet yesterday")
        assert ctx["mentions_unknowable_medication"] is False

    def test_running_out_is_not_an_unknown_medicine(self, conn, user):
        ctx = _safety_context(conn, user, "I am running out of my tablets")
        assert ctx["mentions_unknowable_medication"] is False

    def test_asking_about_an_unnamed_medicine_is(self, conn, user):
        ctx = _safety_context(conn, user, "what is this medicine for")
        assert ctx["mentions_unknowable_medication"] is True

    def test_naming_a_confirmed_medicine_is_not_ambiguous(self, conn, user):
        from app import repository as repo

        repo.add_medication(conn, user, name="Amlodipine", confirmed_by_user=True)
        ctx = _safety_context(conn, user, "what is my amlodipine for")
        assert ctx["mentions_unknowable_medication"] is False
        assert ctx["medication_count"] == 1


class TestOutputChecking:
    """The gate that decides whether model prose is shown at all."""

    def test_clean_prose_passes(self):
        assert check_output(
            "The recorded average is 142 based on 10 readings.", {"142", "10"}
        ) == []

    def test_ungrounded_number_is_caught(self):
        problems = check_output("Your average is 137.", {"142", "10"})
        assert any("137" in p for p in problems)

    @pytest.mark.parametrize(
        "text,fragment",
        [
            ("You should stop taking your medication.", "medication"),
            ("I have sent that to your doctor.", "action"),
            ("Your medication is causing this.", "causation"),
            ("You are fine, nothing to worry about.", "reassurance"),
        ],
    )
    def test_forbidden_phrasing_is_caught(self, text, fragment):
        problems = check_output(text, set())
        assert problems, f"{text!r} should have been rejected"
        assert any(fragment in p for p in problems), problems

    def test_allow_plain_skips_the_numeric_check(self):
        """Used for turns where no numbers were supplied and none are expected."""
        assert check_output("Which medicine do you mean?", set(), allow_plain=True) == []

    def test_rounded_float_admits_neighbours(self):
        """A mean of 142.5 may legitimately be said as 142 or 143."""
        numbers: set[str] = set()
        _collect_numbers({"mean": 142.5}, numbers)
        assert "142" in numbers
        assert "143" in numbers

    def test_numbers_are_collected_from_nested_structures(self):
        numbers: set[str] = set()
        _collect_numbers(
            {"stats": {"readings": [{"systolic": 138}, {"systolic": 145}]},
             "note": "10 readings"},
            numbers,
        )
        assert {"138", "145"} .issubset(numbers)

    def test_booleans_are_not_treated_as_numbers(self):
        """True is 1 in Python; admitting it would let '1' ground anything."""
        numbers: set[str] = set()
        _collect_numbers({"ok": True, "value": 140}, numbers)
        assert "140" in numbers
        assert "1" not in numbers


class TestDegradedIsSelfContained:
    """Degraded mode must work with no network, by construction."""

    def test_module_does_not_import_a_network_client(self):
        import inspect

        source = inspect.getsource(degraded)
        for banned in ("httpx", "requests", "urllib", "socket"):
            assert f"import {banned}" not in source, (
                f"degraded.py imports {banned}; the whole point is that it works offline"
            )

    def test_reply_never_mentions_a_model_or_endpoint_in_user_text(self):
        """Technical failure detail belongs in the audit log, not on a patient's screen."""
        for text in (
            "I want to prepare for my appointment",
            "something unrelated",
            "I recorded 150 over 95",
        ):
            reply = degraded.reply(text, {}, reason="The assistant is offline")
            for banned in ("LLM_", "endpoint", "httpx", "timeout", "API"):
                assert banned not in reply.text, f"{banned} leaked into user-facing text"
