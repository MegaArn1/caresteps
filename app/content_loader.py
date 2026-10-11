"""Load the vetted knowledge base into the database.

The knowledge base lives as JSON in ``content/education/`` because that is the form a
reviewer can read and a non-programmer can correct. This module moves it into the
database at seed time so retrieval is a query rather than a file scan.

Two integrity rules are enforced here, and both fail loudly:

1. **Every fact must point at a registered source.** A fact with an unknown
   ``source_id`` is rejected, not silently skipped, because a fact without provenance
   is exactly what this project exists to avoid.
2. **Every source must have a resolvable-looking URL and a retrieval date.** If the
   provenance record is incomplete the source is rejected.

Rejections are collected and reported rather than raised, so a partially-broken
content file still lets the app start - but the failures are visible at ``/trace`` and
in the seed output, which is the honest failure mode for a demo that might be built
under time pressure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import repository as repo
from .config import CONTENT_DIR

EDUCATION_DIR = CONTENT_DIR / "education"


@dataclass
class LoadReport:
    sources_loaded: int = 0
    facts_loaded: int = 0
    facts_disabled: int = 0
    rejected_sources: list[str] = field(default_factory=list)
    rejected_facts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.rejected_sources and not self.rejected_facts

    def summary(self) -> str:
        parts = [
            f"{self.sources_loaded} source(s)",
            f"{self.facts_loaded} fact(s) enabled",
        ]
        if self.facts_disabled:
            parts.append(f"{self.facts_disabled} held back")
        if self.rejected_sources:
            parts.append(f"{len(self.rejected_sources)} source(s) REJECTED")
        if self.rejected_facts:
            parts.append(f"{len(self.rejected_facts)} fact(s) REJECTED")
        return ", ".join(parts)

    def problems(self) -> list[str]:
        return self.rejected_sources + self.rejected_facts


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_knowledge(conn, report: LoadReport | None = None) -> LoadReport:
    """Register sources, then facts. Returns a report; never raises on bad content."""
    report = report or LoadReport()

    sources_path = EDUCATION_DIR / "sources.json"
    facts_path = EDUCATION_DIR / "facts.json"

    if not sources_path.exists():
        report.rejected_sources.append(f"missing file: {sources_path}")
        return report
    if not facts_path.exists():
        report.rejected_facts.append(f"missing file: {facts_path}")
        return report

    sources_doc = _load_json(sources_path)
    registered: set[str] = set()

    for entry in sources_doc.get("sources", []):
        sid = entry.get("id")
        problems = validate_source(entry)
        if problems:
            report.rejected_sources.append(f"{sid or '<no id>'}: " + "; ".join(problems))
            continue
        repo.upsert_education_source(conn, _to_source_payload(entry))
        registered.add(sid)
        report.sources_loaded += 1

    facts_doc = _load_json(facts_path)
    for entry in facts_doc.get("facts", []):
        fid = entry.get("id")
        problems = validate_fact(entry, registered)
        if problems:
            report.rejected_facts.append(f"{fid or '<no id>'}: " + "; ".join(problems))
            continue

        payload = _to_fact_payload(entry)
        repo.upsert_education_fact(conn, payload)
        if payload.get("enabled", True):
            report.facts_loaded += 1
        else:
            report.facts_disabled += 1

    return report


def validate_source(entry: dict) -> list[str]:
    problems: list[str] = []
    for required in ("id", "publisher", "title", "url", "retrieved_at"):
        if not str(entry.get(required) or "").strip():
            problems.append(f"missing '{required}'")
    url = str(entry.get("url") or "")
    if url and not url.startswith(("http://", "https://")):
        problems.append("url is not an http(s) address")
    if not entry.get("reuse_note"):
        # Not a hard error, but a source with no reuse caveat recorded is one someone
        # has not thought about attribution for.
        problems.append("no reuse note recorded")
    return problems


def validate_fact(entry: dict, registered_sources: set[str]) -> list[str]:
    problems: list[str] = []
    for required in ("id", "source_id", "topic", "statement"):
        if not str(entry.get(required) or "").strip():
            problems.append(f"missing '{required}'")

    source_id = entry.get("source_id")
    if source_id and source_id not in registered_sources:
        problems.append(
            f"points at source '{source_id}', which is not registered - a fact "
            "without provenance must not load"
        )

    topic = entry.get("topic")
    allowed = {
        "medication_purpose",
        "how_to_measure",
        "when_to_seek_help",
        "adherence_support",
    }
    if topic and topic not in allowed:
        problems.append(f"unknown topic '{topic}'")

    # A disabled fact may be a placeholder with no real content, but an ENABLED fact
    # must not look like a placeholder - that would let scaffolding ship as content.
    if entry.get("enabled", True):
        statement = str(entry.get("statement") or "")
        if "PLACEHOLDER" in statement.upper() or "NOT SHOWN" in statement.upper():
            problems.append("enabled fact looks like a placeholder")

    return problems


def _to_source_payload(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "publisher": entry["publisher"],
        "title": entry["title"],
        "url": entry["url"],
        "retrieved_at": entry["retrieved_at"],
        "applies_to": entry.get("applies_to"),
        "reuse_note": entry.get("reuse_note"),
        "review_state": entry.get("review_state", "team_checked"),
        "reviewer": entry.get("reviewer"),
        "reviewed_at": entry.get("reviewed_at"),
    }


def _to_fact_payload(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "source_id": entry["source_id"],
        "topic": entry["topic"],
        "subject": entry.get("subject"),
        "statement": entry["statement"],
        "applies_to": entry.get("applies_to"),
        "review_state": entry.get("review_state", "team_checked"),
        "enabled": bool(entry.get("enabled", True)),
    }


def knowledge_summary(conn) -> dict:
    """What is actually in the database, for the trace page.

    Reported from the database rather than from the files, so that a file/database
    divergence is visible rather than hidden.
    """
    sources = conn.execute(
        "SELECT review_state, COUNT(*) AS c FROM education_source GROUP BY review_state"
    ).fetchall()
    facts = conn.execute(
        """SELECT topic, enabled, COUNT(*) AS c FROM education_fact
           GROUP BY topic, enabled ORDER BY topic, enabled DESC"""
    ).fetchall()

    return {
        "sources_by_review": {r["review_state"]: r["c"] for r in sources},
        "facts_by_topic": [
            {"topic": r["topic"], "enabled": bool(r["enabled"]), "count": r["c"]}
            for r in facts
        ],
        "total_facts_enabled": sum(r["c"] for r in facts if r["enabled"]),
        "total_facts_disabled": sum(r["c"] for r in facts if not r["enabled"]),
        "clinician_reviewed": 0,
        "clinician_review_note": (
            "No content in this knowledge base has been reviewed by a clinician. "
            "'team_checked' means a team member read the source and recorded it. That "
            "distinction is recorded per entry and is not a formality."
        ),
    }
