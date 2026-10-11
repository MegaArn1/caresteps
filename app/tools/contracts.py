"""JSON Schema contracts for every tool.

Written as explicit JSON Schema rather than derived from Python signatures, because
what the model is permitted to send is a safety-relevant artefact and should be
readable on its own terms at ``/trace``.

Naming conventions that carry meaning:

* ``get_*``     - read-only. Never mutates.
* ``prepare_*`` - validates and returns a draft. Never persists.
* ``confirm_*`` - persists. Requires a draft that came from the matching prepare.
* ``record_*``  - persists a small fact the user has directly stated.

There is deliberately **no** tool that changes a dose, stops a medicine, sends a
message, or contacts anyone. The absence is the control.
"""

from __future__ import annotations

from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_care_plan",
            "description": (
                "Read the user's existing care plan and confirmed medicines. Returns "
                "each item with its source and verification status. Use this before "
                "referring to anything about the user's plan. Returns no plan if none "
                "is recorded - it never invents one."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_reading",
            "description": (
                "Validate a blood pressure reading and return a draft for the user to "
                "confirm. Does NOT save anything. The draft includes any input "
                "concerns. Always call this rather than assuming a reading was saved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "systolic": {"type": "integer", "description": "Top number on the monitor"},
                    "diastolic": {"type": "integer", "description": "Bottom number on the monitor"},
                    "measured_at": {
                        "type": "string",
                        "description": "ISO-8601 timestamp of when the reading was taken",
                    },
                    "pulse": {"type": "integer", "description": "Optional pulse, beats per minute"},
                    "user_feeling": {
                        "type": "string",
                        "description": "Any words the user used about how they felt, kept verbatim",
                    },
                    "note": {"type": "string", "description": "Optional note"},
                },
                "required": ["systolic", "diastolic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_medication_report",
            "description": (
                "Prepare a medication status report for the user to confirm. Use "
                "status 'taken', 'not_taken' or 'unsure'. Never use 'unrecorded' - that "
                "state is derived from a missing entry and is not something a user "
                "reports. Does NOT save anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["taken", "not_taken", "unsure"],
                        "description": "What the user said they did",
                    },
                    "medication_name": {
                        "type": "string",
                        "description": "Name as the user said it; matched against confirmed medicines",
                    },
                    "scheduled_for": {
                        "type": "string",
                        "description": "The plan slot this answers, if known",
                    },
                    "note": {"type": "string"},
                },
                "required": ["status"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_education",
            "description": (
                "Look up vetted patient-education facts. ONLY use facts returned by "
                "this tool, and cite the returned source. If it returns nothing, say "
                "you cannot answer reliably - do not fall back on general knowledge. "
                "This tool never returns dosing, missed-dose, switching or stopping "
                "guidance, because 'enabled' facts are limited to explanations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "medication_purpose",
                            "how_to_measure",
                            "when_to_seek_help",
                            "adherence_support",
                        ],
                        "description": "Which area to search",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Optional narrowing term, e.g. a drug name or class",
                    },
                },
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_barrier",
            "description": (
                "Save an execution difficulty the user has described, in their own "
                "words. Include a category ONLY when the user confirmed it; otherwise "
                "pass category_confirmed false so the app can ask. A guess must never "
                "be stored as a confirmed fact."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_words": {
                        "type": "string",
                        "description": "The user's own words, kept verbatim",
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "forgot",
                            "difficulty_using",
                            "unclear_purpose",
                            "worried_side_effect",
                            "running_out",
                            "declined_to_say",
                            "other",
                        ],
                    },
                    "category_confirmed": {
                        "type": "boolean",
                        "description": "True only if the user explicitly agreed with this category",
                    },
                    "related_event": {
                        "type": "string",
                        "description": "Which missing record prompted this, if any",
                    },
                },
                "required": ["user_words"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_period_stats",
            "description": (
                "Compute recorded statistics for a period. This is the ONLY source of "
                "numbers. Never calculate an average, a change or a count yourself. "
                "The result includes the number of readings, the window, and the "
                "missing days, so you can tell the user how much data this is based on."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Window length in days, 7 to 90",
                        "minimum": 7,
                        "maximum": 90,
                    }
                },
                "required": ["days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_activity",
            "description": (
                "See what has recently been recorded or is missing, including "
                "unrecorded medication days and any open difficulties the user raised "
                "before. Use this to notice a gap worth asking about, and to follow up "
                "on something previously raised. Call before asking the user about a "
                "gap, so you do not raise something already resolved."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 60}
                },
                "required": ["days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder_preference",
            "description": (
                "Change when the user is prompted to record. This changes the app's "
                "reminder ONLY. It must never be used to change when or how the user "
                "takes their medicine - that comes from the care plan and is not "
                "editable here."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_time": {
                        "type": "string",
                        "description": "24-hour local time, e.g. 08:00",
                        "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$",
                    }
                },
                "required": ["reminder_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_visit_summary",
            "description": (
                "Assemble a one-page summary of recorded facts for the next "
                "appointment. Returns a draft the user previews and edits. It never "
                "sends anything anywhere. Only facts already stored can be included; "
                "do not add anything the user did not report."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 7, "maximum": 90}
                },
                "required": ["days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_question",
            "description": (
                "Add a question to the list the user will take to their doctor or "
                "pharmacist. Use this when the user raises a concern the app is not "
                "permitted to answer - the concern should not be lost."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The question, in the user's own terms"},
                    "origin": {
                        "type": "string",
                        "enum": ["user", "barrier", "safety"],
                        "description": "Where the question came from",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    },
]


def tool_summary() -> list[dict[str, Any]]:
    """Compact listing for the trace page."""
    out = []
    for t in TOOL_SCHEMAS:
        fn = t["function"]
        props = fn["parameters"].get("properties", {})
        out.append(
            {
                "name": fn["name"],
                "description": fn["description"][:200],
                "parameters": list(props.keys()),
                "required": fn["parameters"].get("required", []),
            }
        )
    return out
