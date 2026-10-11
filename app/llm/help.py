"""The help path.

The single most safety-critical piece of content in the app. If this is wrong, someone
in trouble is told the wrong number.

It reads from ``content/rules/emergency.json``, which is a *reviewed artefact with a
source attached* rather than a literal in this file. That indirection is the point: the
number must be traceable to a Singapore government source, and a reviewer must be able
to change it without touching code.

There is deliberately no fallback that guesses a number. If the configuration is
missing or unverified, the app says it cannot confirm the number and tells the person to
use a hospital or a doctor - it does not print a plausible-looking digit string.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

EMERGENCY_FILE = (
    Path(__file__).resolve().parents[2] / "content" / "rules" / "emergency.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(EMERGENCY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def emergency_info() -> dict:
    """Return the verified local help configuration.

    ``verified`` is False unless the configuration names a source, which forces the UI
    into its cautious wording. An unverified number is shown greyed with a warning
    rather than presented as fact.
    """
    data = _load()
    primary = data.get("primary", {})
    sources = data.get("sources", [])

    number = (primary.get("number") or "").strip()
    verified = bool(number and sources and data.get("review_state") != "unreviewed")

    return {
        "number": number or None,
        "label": primary.get("label") or "Emergency ambulance",
        "country": data.get("country", "Singapore"),
        "verified": verified,
        "review_state": data.get("review_state", "unreviewed"),
        "sources": sources,
        "retrieved_at": data.get("retrieved_at"),
        "what_to_say": data.get(
            "what_to_say",
            [
                "Say where you are, including the block and unit number.",
                "Say what is happening and how long it has been going on.",
                "Say the person's age and any medicines they take.",
                "Stay on the line and follow the instructions you are given.",
            ],
        ),
        "also": data.get("also", []),
        "warning": data.get("warning"),
        # Shown wherever the help path appears, so the prototype never implies it has
        # contacted anyone.
        "app_does_not": (
            "This app has not contacted anyone and cannot do so. You need to make the "
            "call yourself, or ask someone nearby to call for you."
        ),
    }


def other_routes() -> list[dict]:
    """Non-emergency routes, with their own provenance."""
    data = _load()
    return data.get("other_routes", [])


def help_sources() -> list[str]:
    return [s.get("id") for s in (_load().get("sources") or []) if s.get("id")]
