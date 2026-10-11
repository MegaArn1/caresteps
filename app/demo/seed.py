"""Build the fictional demo patient and a two-week history.

The character
-------------
Mdm Tan, 72. Diagnosed hypertension, on a plan from her polyclinic. Records her blood
pressure most days but not all, sometimes forgets to log, and is unsure what one of her
two medicines is for. She has a follow-up appointment in a few days.

This is **not a real person and not a real care plan.** Every row carries
``is_simulated = 1``. The plan text is written by us for the prototype and carries no
clinical authority - ``source_type = 'demo_fictional'`` says so explicitly, and the UI
renders that label.

Why the history looks the way it does
-------------------------------------
The gaps are the point. A clean two weeks would make the app's central feature - asking
why a record is missing - impossible to demonstrate. So the seed includes:

* readings on most but not all days, with a deliberate three-day gap
* medication reports that stop two days ago, producing genuine ``unrecorded`` days
* one backfilled report, so the distinct "you told us later" state is visible
* one reading that was corrected, so the revision chain is visible
* one open difficulty raised earlier, so follow-up has something real to follow up on
* one resolved difficulty, so the app can be shown *not* re-raising it

The numbers are internally consistent: the recent week sits a little above the earlier
week, which gives the trend view something honest to describe without anyone claiming a
cause.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from .. import repository as repo

PROFILE_NAME = "Mdm Tan"
AGE_BAND = "65-74"

# The fictional plan. Source type is explicit, and there is no personal target, because
# inventing one would be exactly the failure this project argues against.
PLAN_ITEMS = [
    {
        "instruction": "Take your blood pressure medicine once each morning.",
        "source_type": "demo_fictional",
        "source_label": "Fictional demo plan (written for this prototype)",
        "verified_by_user": True,
    },
    {
        "instruction": "Record your blood pressure at home and bring the record to your next visit.",
        "source_type": "demo_fictional",
        "source_label": "Fictional demo plan (written for this prototype)",
        "verified_by_user": True,
    },
    {
        "instruction": "Next follow-up appointment at the polyclinic.",
        "source_type": "demo_fictional",
        "source_label": "Fictional demo plan (written for this prototype)",
        "verified_by_user": True,
    },
]

# Two medicines, mapped to education entries loaded from content/. The names are
# common real drugs so the knowledge lookup is meaningful; the association between this
# character and these drugs is entirely fictional.
MEDICATIONS = [
    {"name": "Amlodipine", "generic_name": "amlodipine", "education_id": "edu_amlodipine_purpose"},
    {"name": "Losartan", "generic_name": "losartan", "education_id": "edu_losartan_purpose"},
]


def _daylist(back: int) -> list[date]:
    today = date.today()
    return [today - timedelta(days=back - 1 - i) for i in range(back)]


# (day offset from the start of a 14-day window, systolic, diastolic, pulse, feeling)
# None means no reading that day - the gaps are deliberate.
READING_PATTERN = [
    (0, 138, 86, 72, None),
    (1, 141, 88, 70, None),
    (2, 136, 84, 74, None),
    (3, None, None, None, None),          # travel / forgot
    (4, 139, 85, 71, None),
    (5, 143, 89, 73, "a bit tired"),
    (6, 140, 86, 70, None),
    (7, None, None, None, None),          # gap begins
    (8, None, None, None, None),
    (9, None, None, None, None),          # three-day gap ends
    (10, 146, 91, 75, None),
    (11, 144, 90, 72, None),
    (12, 148, 92, 76, "slight headache"),
    (13, 145, 90, 74, None),
]


def seed_demo(conn: sqlite3.Connection, *, verbose: bool = False) -> str:
    """Populate the database with the fictional patient. Returns the user id.

    Raises if a profile already exists, so a caller cannot silently double-seed. Reset
    first with ``repo.reset_db`` / ``make seed``.
    """
    existing = repo.get_profile(conn)
    if existing:
        raise RuntimeError(
            "A profile already exists. Reset the database before seeding again."
        )

    user_id = repo.create_profile(
        conn,
        display_name=PROFILE_NAME,
        age_band=AGE_BAND,
        language="en",
        reminder_time="08:00",
        is_simulated=True,
    )

    # ---------------------------------------------------------------- care plan
    plan_ids = []
    for item in PLAN_ITEMS:
        plan_ids.append(
            repo.add_care_plan_item(
                conn,
                user_id,
                instruction=item["instruction"],
                source_type=item["source_type"],
                source_label=item["source_label"],
                verified_by_user=item["verified_by_user"],
                # No target: absent on purpose. A target would need a real source.
                is_simulated=True,
            )
        )

    # -------------------------------------------------------------- medications
    med_ids = []
    for med in MEDICATIONS:
        med_ids.append(
            repo.add_medication(
                conn,
                user_id,
                name=med["name"],
                generic_name=med["generic_name"],
                plan_instruction="As recorded on your plan. Take as your doctor or pharmacist instructed.",
                plan_source_id=plan_ids[0],
                education_id=med["education_id"],
                confirmed_by_user=True,
                is_simulated=True,
            )
        )

    # ----------------------------------------------------------------- readings
    days = _daylist(14)
    reading_ids: list[str | None] = []
    for idx, (_, sys_v, dia_v, pulse, feeling) in enumerate(READING_PATTERN):
        if sys_v is None:
            reading_ids.append(None)
            continue
        day = days[idx]
        # Readings are taken in the morning, near the recorded reminder time.
        measured = datetime.combine(day, datetime.min.time()).replace(
            hour=7, minute=45 + (idx % 3) * 5
        ).astimezone().isoformat(timespec="seconds")
        result = repo.confirm_reading(
            conn,
            user_id,
            {
                "systolic": sys_v,
                "diastolic": dia_v,
                "pulse": pulse,
                "measured_at": measured,
                "user_feeling": feeling,
                "note": None,
                "entered_source": "manual",
            },
            is_simulated=True,
        )
        reading_ids.append(result["id"])

    # A corrected reading, so the revision chain is real rather than described.
    # Day 12 originally entered as 148/92; the user noticed she had misread it.
    target_idx = 12
    original_id = reading_ids[target_idx]
    if original_id:
        corrected_id = repo.correct_reading(
            conn, user_id, original_id,
            systolic=147, diastolic=91, pulse=76,
            note="Re-read the monitor the next morning and corrected this.",
        )
        reading_ids[target_idx] = corrected_id

    # ------------------------------------------------------ medication reports
    # Reports exist for the first twelve days and then stop. The last two days are
    # genuinely without a record, which is what produces derived 'unrecorded' rows and
    # gives the demo its opening question.
    for idx, day in enumerate(days[:-2]):
        reported = datetime.combine(day, datetime.min.time()).replace(
            hour=8, minute=5
        ).astimezone().isoformat(timespec="seconds")
        repo.record_medication_report(
            conn,
            user_id,
            status="taken",
            medication_id=med_ids[0],
            scheduled_for=f"{day.isoformat()}T08:00",
            reported_at=reported,
            is_backfilled=False,
            is_simulated=True,
        )

    # One backfilled report: a day she forgot to log and filled in later. This is a
    # different state from a normal report and the UI must show it differently.
    backfill_day = days[6]
    repo.record_medication_report(
        conn,
        user_id,
        status="taken",
        medication_id=med_ids[0],
        scheduled_for=f"{backfill_day.isoformat()}T08:00",
        reported_at=(
            datetime.combine(days[8], datetime.min.time())
            .replace(hour=19, minute=30)
            .astimezone()
            .isoformat(timespec="seconds")
        ),
        note="Filled in later - I did take it.",
        is_backfilled=True,
        is_simulated=True,
    )

    # One 'unsure', so the four-state model is visibly four states and not three.
    unsure_day = days[4]
    conn.execute(
        """INSERT INTO medication_report
           (id, user_id, medication_id, status, is_self_report, is_backfilled,
            scheduled_for, reported_at, note, is_simulated, created_at)
           VALUES (?,?,?,'unsure',1,0,?,?,?,1,?)""",
        (
            repo.new_id("mrep"), user_id, med_ids[1],
            f"{unsure_day.isoformat()}T08:00",
            datetime.combine(unsure_day, datetime.min.time())
            .replace(hour=8, minute=10).astimezone().isoformat(timespec="seconds"),
            "Could not remember whether I had taken the second one.",
            repo.now_iso(),
        ),
    )

    # ----------------------------------------------------------------- barriers
    # Open: raised a week ago, still unresolved, so follow-up has something to say.
    open_barrier = repo.record_barrier(
        conn,
        user_id,
        user_words="I am not sure what the second tablet is actually for.",
        category="unclear_purpose",
        category_confirmed=True,
        proposed_by="user",
        is_simulated=True,
    )
    # Age it so it does not look like it was created this second.
    conn.execute(
        "UPDATE barrier_event SET created_at = ? WHERE id = ?",
        (
            datetime.combine(days[7], datetime.min.time())
            .replace(hour=9, minute=20).astimezone().isoformat(timespec="seconds"),
            open_barrier,
        ),
    )

    # Resolved: raised and settled, so the app can be shown NOT re-raising it.
    resolved_barrier = repo.record_barrier(
        conn,
        user_id,
        user_words="I keep forgetting to write the reading down.",
        category="forgot",
        category_confirmed=True,
        proposed_by="user",
        is_simulated=True,
    )
    repo.resolve_barrier(conn, resolved_barrier, "resolved")
    conn.execute(
        "UPDATE barrier_event SET created_at = ?, resolved_at = ? WHERE id = ?",
        (
            datetime.combine(days[2], datetime.min.time())
            .replace(hour=10, minute=0).astimezone().isoformat(timespec="seconds"),
            datetime.combine(days[3], datetime.min.time())
            .replace(hour=18, minute=0).astimezone().isoformat(timespec="seconds"),
            resolved_barrier,
        ),
    )

    # A chosen action, so the summary has a "what she decided to do" section.
    action_id = repo.add_support_action(
        conn,
        user_id,
        title="Record after breakfast instead of before",
        basis_type="user_choice",
        basis_label="Chosen by the patient",
        barrier_id=resolved_barrier,
        detail="Moved the reminder later so it fits the morning routine.",
        is_simulated=True,
    )
    repo.set_action_status(conn, action_id, "done")

    # ---------------------------------------------------------------- questions
    repo.add_question(
        conn, user_id,
        "What is the second tablet for, and do I still need it?",
        origin="barrier", priority=2, is_simulated=True,
    )
    repo.add_question(
        conn, user_id,
        "My readings have been a bit higher lately - is that something to worry about?",
        origin="user", priority=1, is_simulated=True,
    )

    if verbose:
        print(f"Seeded profile {user_id} ({PROFILE_NAME}) with 14 days of history")

    return user_id


def reset_and_seed(conn: sqlite3.Connection) -> str:
    """Convenience for the CLI and the reset button."""
    from ..db import reset_db

    reset_db()
    return seed_demo(conn)
