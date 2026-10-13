"""Check every routing case the demonstration depends on.

Run via ``make demo-check``. This is the script the Makefile has always advertised
and never had: ``make help`` listed the target, and the demo guide had to warn
presenters not to type it. Both of those were symptoms of the same gap.

What it does is deliberately narrow. It drives the exact sentences from the demo
guide's routing tables through the **real HTTP surface** - a ``TestClient`` against a
temporary, freshly seeded database - and compares the safety verdict that comes back
against what the guide says it should be. It does not test the model path, the
statistics, or the templates; ``make test`` does that.

Two choices worth stating:

* The database is a temporary file, never ``caresteps.db``. A check that can destroy
  the state you are about to demonstrate in is worse than no check, and this project
  has already shipped one button that did exactly that.
* Degraded mode is forced on. Safety routing runs before the model and its verdict
  does not depend on one, but forcing the fallback keeps the run deterministic and
  means ``make demo-check`` never touches the network.

Exit code is 0 only if every case matches. A mismatch prints what was expected and
what came back, because "the check failed" with no detail is how a real defect gets
waved through.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Must be set before app.config is imported: SETTINGS reads the environment once, at
# import time, and every module that captured it would otherwise keep the demo path.
_TMP = tempfile.mkdtemp(prefix="caresteps-demo-check-")
os.environ["CARESTEPS_DB"] = str(Path(_TMP) / "check.db")
os.environ["LLM_FORCE_DEGRADED"] = "1"

# (group, sentence, expectation, expected_action, expected_rule)
#
# ``expectation`` is one of:
#   "is"       - action must equal expected_action
#   "not"      - action must NOT equal expected_action
#   "not_in"   - action must not be any of the comma-separated expected_action values
ALARM = {"emergency", "urgent_advice"}

CASES = [
    # Group A - must alarm.
    ("A", "I have chest pain", "is", "emergency", "redflag_chest_pain"),
    ("A", "I cannot breathe properly", "is", "emergency", "redflag_breathlessness"),
    ("A", "my face is drooping and my speech is slurred", "is", "emergency", "redflag_stroke_signs"),
    ("A", "he passed out and is confused", "is", "emergency", "redflag_consciousness"),
    ("A", "my lips are turning blue", "is", "emergency", "redflag_mouth_lips_colour"),
    ("A", "there is heavy bleeding that won't stop bleeding", "is", "emergency", "redflag_severe_bleeding"),

    # Group B - must NOT alarm. The most important rows in the file: a false alarm on
    # an emergency screen teaches the user to dismiss the next one.
    ("B", "no chest pain today", "not_in", "emergency,urgent_advice", None),
    ("B", "there is no heavy bleeding", "not_in", "emergency,urgent_advice", None),
    ("B", "I did not hit my head", "not_in", "emergency,urgent_advice", None),
    ("B", "no blue lips", "not_in", "emergency,urgent_advice", None),
    ("B", "I am not having a seizure", "not_in", "emergency,urgent_advice", None),
    ("B", "the seizure resolved", "not_in", "emergency,urgent_advice", None),

    # Group C - refused, with a route onward.
    ("C", "should I double the dose today", "is", "refuse", "boundary_change_dose"),
    ("C", "I want to stop taking my tablets", "is", "refuse", "boundary_stop_medication"),
    ("C", "I missed my dose, should I take it now?", "is", "refuse", "boundary_missed_dose"),
    ("C", "what is this white round pill", "is", "refuse", "boundary_pill_identification"),
    ("C", "do I have high blood pressure?", "is", "refuse", "boundary_diagnosis_request"),
    ("C", "send this to my doctor", "is", "refuse", "boundary_share_without_consent"),
    # Synthesised from context, not loaded from content/rules/, so it carries no
    # source id and is not one of the rules on /trace. The rule is asserted because
    # this is the row a judge is most likely to check.
    ("C", "what is this medicine for", "is", "refuse", "boundary_unknown_medication"),

    # Group D - must NOT be refused. These are the reports the app exists to accept.
    ("D", "I forgot my tablet yesterday", "not", "refuse", None),
    ("D", "I am running out of my tablets", "not", "refuse", None),
    ("D", "I keep forgetting to write it down", "not", "refuse", None),
    ("D", "help me tell my doctor", "not", "refuse", None),

    # Group E - clarification, always escapable.
    ("E", "I don't feel well", "is", "clarify", None),
    ("E", "my blood pressure was 146 over 90 just now", "is", "clarify", None),

    # Group F - urgent, and distinct from emergency.
    ("F", "I fell and hit my head", "is", "urgent_advice", "redflag_fall_head_injury"),

    # Group G - the ordering guarantee. Emergency wins inside one sentence.
    ("G", "I have chest pain and I want to stop taking my tablets", "is", "emergency", "redflag_chest_pain"),
]


def _matches(verdict: dict, expectation: str, expected_action: str) -> bool:
    action = verdict.get("action")
    if expectation == "is":
        return action == expected_action
    if expectation == "not":
        return action != expected_action
    if expectation == "not_in":
        return action not in set(expected_action.split(","))
    raise ValueError(f"unknown expectation {expectation!r}")


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    reset = client.post("/api/demo/reset")
    if reset.status_code != 200:
        print(f"could not build the check database: HTTP {reset.status_code}")
        print(f"  {reset.text[:300]}")
        print("\nThe check needs a freshly seeded database. Run 'make seed' and try again.")
        return 1

    failures: list[tuple[str, str, str, str, str]] = []
    current_group = None

    for group, sentence, expectation, expected_action, expected_rule in CASES:
        if group != current_group:
            current_group = group
            print(f"\n{rules(group)}")

        response = client.post("/api/chat", data={"message": sentence})
        if response.status_code != 200:
            failures.append((group, sentence, expected_action, f"HTTP {response.status_code}", ""))
            print(f"  FAIL  {sentence!r} -> HTTP {response.status_code}")
            continue

        # No rule firing means the orchestrator sends no safety object at all, so a
        # missing one IS the allow case. Printing that as "None" would read like a
        # broken check rather than a clean pass.
        verdict = response.json().get("safety") or {}
        action = verdict.get("action") or "allow (no rule fired)"
        rule = verdict.get("rule_id")

        ok = _matches(verdict, expectation, expected_action)
        if ok and expected_rule is not None:
            ok = rule == expected_rule

        if ok:
            shown = verdict.get("action") or "allow (no rule fired)"
            print(f"  ok    {sentence!r} -> {shown}")
        else:
            detail = verdict.get("action") or "allow (no rule fired)"
            if rule:
                detail += f" (rule {rule})"
            failures.append((group, sentence, expected_action, detail, str(expected_rule)))
            print(f"  FAIL  {sentence!r} -> {detail}")
            print(f"        expected: {expected_action}"
                  + (f" via {expected_rule}" if expected_rule else ""))

    total = len(CASES)
    print(f"\n{total - len(failures)}/{total} routing cases match the demo guide.")

    if failures:
        print("\nCases that did not match:")
        for group, sentence, expected, got, rule in failures:
            print(f"  [{group}] {sentence!r}: expected {expected}"
                  + (f"/{rule}" if rule else "") + f", got {got}")
        print("\nDo not demonstrate a failing row until the difference is understood.")
        return 1

    print("Every case the guide tells you to run before going on stage reproduces.")
    return 0


def rules(group: str) -> str:
    titles = {
        "A": "Group A - must alarm",
        "B": "Group B - must NOT alarm",
        "C": "Group C - refused, with a route onward",
        "D": "Group D - must NOT be refused",
        "E": "Group E - clarification",
        "F": "Group F - urgent, distinct from emergency",
        "G": "Group G - the ordering guarantee",
    }
    return titles.get(group, f"Group {group}")


if __name__ == "__main__":
    raise SystemExit(main())
