"""Rebuild the database with the fictional demo patient.

Run via ``make seed``. Destructive by design: the whole value of a demo you can trust
is that it always starts from the same state.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import repository as repo  # noqa: E402
from app.config import SETTINGS  # noqa: E402
from app.content_loader import knowledge_summary, load_knowledge  # noqa: E402
from app.db import reset_db  # noqa: E402
from app.demo.seed import seed_demo  # noqa: E402
from app.safety.rules import rule_metadata  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the CareSteps demo database")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--keep-db", action="store_true",
                        help="do not drop existing tables first (will fail if populated)")
    args = parser.parse_args()

    if not args.keep_db:
        reset_db(SETTINGS.db_path)

    from app.db import connect

    conn = connect(SETTINGS.db_path)
    exit_code = 0
    try:
        # 1. Knowledge base first, so the medicines can reference real entries.
        report = load_knowledge(conn)
        print(f"knowledge base: {report.summary()}")
        if not report.ok:
            exit_code = 1
            print("\n  Content problems (these are build errors, not warnings):")
            for p in report.problems():
                print(f"    - {p}")
            print(
                "\n  A fact without a registered source is dropped rather than "
                "loaded, because an uncited health claim must not be able to run."
            )

        # 2. Rules, so a rule with no source is visible now rather than at runtime.
        rules = rule_metadata()
        print(f"rules: v{rules['version']}, {rules['enabled']} enabled, "
              f"{rules['held_for_review']} held for review, {rules['total']} total")
        for problem in rules["problems"]:
            print(f"    rule problem: {problem}")

        # 3. The fictional patient.
        user_id = seed_demo(conn, verbose=args.verbose)

        summary = knowledge_summary(conn)
        print(f"profile: {user_id}")
        print(f"  facts enabled: {summary['total_facts_enabled']}, "
              f"held back: {summary['total_facts_disabled']}")
        print(f"  clinician-reviewed entries: {summary['clinician_reviewed']}")

        if args.verbose:
            for table in (
                "user_profile", "care_plan", "medication_item", "bp_reading",
                "medication_report", "barrier_event", "support_action",
                "education_source", "education_fact", "consultation_question",
            ):
                print(f"  {table}: {repo.count_rows(conn, table)}")

        print(f"\ndatabase: {SETTINGS.db_path}")
        print("run 'make run' and open http://127.0.0.1:8000")

    finally:
        conn.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
