"""SQLite schema and connection handling.

Deliberately bare SQL rather than an ORM: the schema is the specification, it can be
read by a judge in one sitting, and it can be explained live without a translation
layer. See docs/decisions.md (D3).

Design rules encoded in this schema:

* ``provenance``  - every health fact records where it came from and whether a human
  verified it. Three *separate* status columns, because they are three separate
  questions: did the user confirm it, did the team check it against a source, and did
  a clinician review it. A confirmed medicine name does NOT mean the drug entry was
  pharmacist-reviewed.
* ``is_simulated`` - set on every row created from demo data, so no simulated history
  can ever be mistaken for a real observation.
* ``status``      - adherence uses four values, and ``unrecorded`` is *derived*, never
  presented as something the patient reported.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- M0: profile

CREATE TABLE IF NOT EXISTS user_profile (
    id                TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    age_band          TEXT NOT NULL,          -- e.g. '65-74', never a birthdate
    language          TEXT NOT NULL DEFAULT 'en',
    -- Interaction preferences the user has confirmed for themselves.
    prefers_large_text INTEGER NOT NULL DEFAULT 1,
    reminder_time     TEXT,                   -- 'HH:MM' in local time, user-chosen
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS care_plan (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    -- What the plan says. Kept verbatim so the user can see their own plan text.
    instruction       TEXT NOT NULL,
    -- Provenance is explicit. 'demo_fictional' means written by us for the
    -- prototype and carrying no clinical authority whatsoever.
    source_type       TEXT NOT NULL,          -- demo_fictional|user_reported|clinician_given|app_education
    source_label      TEXT NOT NULL,          -- human-readable origin
    verified_by_user  INTEGER NOT NULL DEFAULT 0,
    verified_by_team  INTEGER NOT NULL DEFAULT 0,
    reviewed_by_clinician INTEGER NOT NULL DEFAULT 0,
    -- Personal BP target is ONLY recorded when a source states it. Never inferred.
    target_systolic   INTEGER,
    target_diastolic  INTEGER,
    target_source     TEXT,
    effective_date    TEXT,
    notes             TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medication_item (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    -- The name as CONFIRMED by the user, and by whom. Unknown stays unknown.
    name              TEXT NOT NULL,
    generic_name      TEXT,
    confirmed_by_user INTEGER NOT NULL DEFAULT 0,
    plan_instruction  TEXT,                   -- from the user's own plan, not invented
    plan_source_id    TEXT REFERENCES care_plan(id),
    -- Which knowledge entry (if any) explains this drug.
    education_id      TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

-- ---------------------------------------------------------------- M1: readings

CREATE TABLE IF NOT EXISTS bp_reading (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    systolic          INTEGER NOT NULL,
    diastolic         INTEGER NOT NULL,
    pulse             INTEGER,
    -- These two are DIFFERENT questions and must never be conflated.
    measured_at       TEXT NOT NULL,          -- when the cuff was on
    entered_at        TEXT NOT NULL,          -- when this row was created
    entered_source    TEXT NOT NULL DEFAULT 'manual',  -- manual|nl_draft|correction
    user_feeling      TEXT,                   -- free text, kept as the patient's words
    note              TEXT,
    -- Confirmation state: a draft is not a record.
    status            TEXT NOT NULL DEFAULT 'confirmed',  -- draft|confirmed
    superseded_by     TEXT REFERENCES bp_reading(id),      -- correction chain
    corrects          TEXT REFERENCES bp_reading(id),
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    -- Idempotency: a repeated submit of the same logical entry must not double-count.
    dedupe_key        TEXT UNIQUE,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bp_user_measured
    ON bp_reading(user_id, measured_at DESC);

-- ------------------------------------------------------- M2: medication reports

CREATE TABLE IF NOT EXISTS medication_report (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    medication_id     TEXT REFERENCES medication_item(id),
    -- taken | not_taken | unsure | unrecorded
    -- 'unrecorded' is DERIVED from a missing event. It is never a patient report.
    status            TEXT NOT NULL,
    is_self_report    INTEGER NOT NULL DEFAULT 1,   -- 0 => derived, not reported
    -- True when the user filled in a gap after the fact. Shown distinctly in the UI.
    is_backfilled     INTEGER NOT NULL DEFAULT 0,
    scheduled_for     TEXT,                   -- the plan slot this answers
    reported_at       TEXT NOT NULL,
    note              TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_medrep_user_time
    ON medication_report(user_id, reported_at DESC);

-- ------------------------------------------------------------- M3: barriers

CREATE TABLE IF NOT EXISTS barrier_event (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    -- The patient's own words, kept verbatim. This is evidence, not a label.
    user_words        TEXT NOT NULL,
    -- The classification, and whether the PATIENT confirmed it. A model guess that
    -- the user did not confirm must never be stored as fact.
    category          TEXT,                   -- forgot|difficulty_using|unclear_purpose|worried_side_effect|running_out|declined_to_say|other
    category_confirmed INTEGER NOT NULL DEFAULT 0,
    proposed_by       TEXT NOT NULL DEFAULT 'rules',  -- rules|model|user
    -- Which lack-of-record prompted this, if any.
    related_event     TEXT,
    status            TEXT NOT NULL DEFAULT 'open',   -- open|resolved|parked
    resolved_at       TEXT,
    follow_up_at      TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_action (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    barrier_id        TEXT REFERENCES barrier_event(id),
    title             TEXT NOT NULL,
    detail            TEXT,
    -- Every action must trace to a source. No source, no action.
    basis_type        TEXT NOT NULL,          -- care_plan|education|user_choice
    basis_id          TEXT,
    basis_label       TEXT,
    chosen_by_user    INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'chosen',  -- chosen|done|dropped
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

-- ------------------------------------------------------- M4/M5: knowledge & output

CREATE TABLE IF NOT EXISTS education_source (
    id                TEXT PRIMARY KEY,
    publisher         TEXT NOT NULL,
    title             TEXT NOT NULL,
    url               TEXT NOT NULL,
    retrieved_at      TEXT NOT NULL,
    applies_to        TEXT,                   -- who this is for
    reuse_note        TEXT,                   -- licensing caution
    review_state      TEXT NOT NULL DEFAULT 'team_checked',
    -- ^ team_checked|clinician_reviewed|unreviewed
    reviewer          TEXT,
    reviewed_at       TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS education_fact (
    id                TEXT PRIMARY KEY,
    source_id         TEXT NOT NULL REFERENCES education_source(id),
    topic             TEXT NOT NULL,          -- medication_purpose|how_to_measure|when_to_seek_help|adherence_support
    subject           TEXT,                   -- e.g. the drug class this fact describes
    -- OUR OWN paraphrase. Not a scraped paragraph.
    statement         TEXT NOT NULL,
    applies_to        TEXT,
    review_state      TEXT NOT NULL DEFAULT 'team_checked',
    enabled           INTEGER NOT NULL DEFAULT 1,  -- disabled facts are never retrieved
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fact_topic ON education_fact(topic, subject);

CREATE TABLE IF NOT EXISTS visit_summary (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    period_start      TEXT NOT NULL,
    period_end        TEXT NOT NULL,
    -- The generated fact table is stored WITH the summary so that what the user
    -- printed can be compared against what the data said at that moment.
    facts_json        TEXT NOT NULL,
    narrative         TEXT,
    omitted_items     TEXT,                   -- JSON list of fact keys the user removed
    user_edited       INTEGER NOT NULL DEFAULT 0,
    generated_at      TEXT NOT NULL,
    is_simulated      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS consultation_question (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    text              TEXT NOT NULL,
    origin            TEXT NOT NULL DEFAULT 'user',  -- user|barrier|safety
    priority          INTEGER NOT NULL DEFAULT 0,
    include_in_summary INTEGER NOT NULL DEFAULT 1,   -- the user decides what travels
    is_simulated      INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL
);

-- ------------------------------------------------------------- conversation & audit

CREATE TABLE IF NOT EXISTS conversation_message (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL REFERENCES user_profile(id),
    session_id        TEXT NOT NULL,
    role              TEXT NOT NULL,          -- user|assistant|system_note
    content           TEXT NOT NULL,
    -- Structured payload: cards, options, refusals. Kept so the UI can re-render
    -- the exact same turn after a refresh.
    payload_json      TEXT,
    mode              TEXT,                   -- live|degraded|safety
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_session ON conversation_message(session_id, created_at);

CREATE TABLE IF NOT EXISTS audit_event (
    id                TEXT PRIMARY KEY,
    user_id           TEXT,
    session_id        TEXT,
    kind              TEXT NOT NULL,          -- tool_call|tool_result|safety_route|llm_call|error
    tool_name         TEXT,
    args_json         TEXT,                   -- already redacted by the caller
    result_status     TEXT,                   -- ok|refused|error|skipped
    source_ids        TEXT,                   -- JSON list of source ids actually returned
    rule_version      TEXT,
    detail            TEXT,                   -- short, redacted, no stray health text
    mode              TEXT,                   -- live|degraded
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_event(session_id, created_at DESC);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with sane defaults.

    ``row_factory`` is sqlite3.Row so callers get dict-like access without an ORM.
    """
    from .config import SETTINGS

    path = Path(db_path or SETTINGS.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create the schema if absent. Safe to call repeatedly."""
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


@contextmanager
def session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Connection context manager that commits on success and rolls back on error."""
    conn = connect(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def reset_db(db_path: Path | None = None) -> None:
    """Drop every table. Used by ``make seed`` and by the demo reset button."""
    conn = connect(db_path)
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        conn.execute("PRAGMA foreign_keys = OFF")
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()
    init_db(db_path)
