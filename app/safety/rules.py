"""Rule loading, versioning and provenance.

Rules are data, not code. They live in ``content/rules/*.json`` so that a reviewer can
read every trigger and its source without reading Python, and so that a rule cannot be
quietly enabled without an accompanying citation.

The loader enforces two things that matter for the Responsible AI story:

1. **A rule with no source is not loaded.** If ``sources`` is empty the rule is dropped
   and recorded as a load problem. There is no way to ship an uncited threshold.
2. **A rule that is not enabled is retained but inert.** This lets the demo show a
   rule that exists and is deliberately switched off pending clinical review, rather
   than pretending it does not exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parents[2] / "content" / "rules"


@dataclass
class Rule:
    id: str
    kind: str  # red_flag | boundary | clarify
    enabled: bool
    severity: str
    patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    review_state: str = "unreviewed"
    reason: str = ""
    patient_message: str = ""
    redirect: str | None = None
    offer_question: bool = False
    options: list[dict] = field(default_factory=list)
    notes: str = ""
    raw: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalise once at load time so the matching loop stays trivial.
        self.patterns = [p.lower() for p in self.patterns]
        self.exclude_patterns = [p.lower() for p in self.exclude_patterns]


@dataclass
class RuleSet:
    version: str
    rules: list[Rule] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def of_kind(self, kind: str, enabled_only: bool = True) -> list[Rule]:
        return [
            r
            for r in self.rules
            if r.kind == kind and (r.enabled or not enabled_only)
        ]

    def by_id(self, rule_id: str) -> Rule | None:
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None


def _load_file(path: Path) -> tuple[list[Rule], list[str]]:
    problems: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - malformed content is a build error
        return [], [f"{path.name}: could not be parsed ({exc})"]

    rules: list[Rule] = []
    for entry in data.get("rules", []):
        rid = entry.get("id") or "<missing id>"
        sources = entry.get("sources") or []

        # Hard requirement: no citation, no rule.
        if not sources:
            problems.append(
                f"{path.name}:{rid} dropped - it declares no source, and an uncited "
                "rule must not be able to run"
            )
            continue

        rules.append(
            Rule(
                id=rid,
                kind=entry.get("kind", "boundary"),
                enabled=bool(entry.get("enabled", False)),
                severity=entry.get("severity", "info"),
                patterns=entry.get("patterns", []),
                exclude_patterns=entry.get("exclude_patterns", []),
                sources=sources,
                review_state=entry.get("review_state", "unreviewed"),
                reason=entry.get("reason", ""),
                patient_message=entry.get("patient_message", ""),
                redirect=entry.get("redirect"),
                offer_question=bool(entry.get("offer_question", False)),
                options=entry.get("options", []),
                notes=entry.get("notes", ""),
                raw=entry,
            )
        )
    return rules, problems


def load_rules(directory: Path | None = None) -> RuleSet:
    """Load every rule file in the directory in a stable order."""
    directory = directory or RULES_DIR
    all_rules: list[Rule] = []
    problems: list[str] = []
    version = "0"

    if not directory.exists():
        return RuleSet(version="0", rules=[], problems=[f"No rules directory at {directory}"])

    for path in sorted(directory.glob("*.json")):
        data_version = "0"
        try:
            data_version = str(json.loads(path.read_text(encoding="utf-8")).get("version", "0"))
        except Exception:
            pass
        version = max(version, data_version, key=lambda v: _version_key(v))

        rules, probs = _load_file(path)
        all_rules.extend(rules)
        problems.extend(probs)

    return RuleSet(version=version, rules=all_rules, problems=problems)


def _version_key(v: str) -> tuple:
    parts = []
    for chunk in str(v).replace("-", ".").split("."):
        parts.append((0, int(chunk)) if chunk.isdigit() else (1, 0))
    return tuple(parts)


RULES = load_rules()


def rule_metadata() -> dict[str, Any]:
    """A description of the active rule set, safe to show in the UI.

    Exposed at ``/trace`` so a judge can see exactly which rule version was live, how
    many rules are enabled, and which are held back pending review.
    """
    enabled = [r for r in RULES.rules if r.enabled]
    disabled = [r for r in RULES.rules if not r.enabled]
    return {
        "version": RULES.version,
        "total": len(RULES.rules),
        "enabled": len(enabled),
        "held_for_review": len(disabled),
        "problems": RULES.problems,
        "rules": [
            {
                "id": r.id,
                "kind": r.kind,
                "enabled": r.enabled,
                "severity": r.severity,
                "review_state": r.review_state,
                "sources": r.sources,
                "reason": r.reason,
            }
            for r in RULES.rules
        ],
    }
