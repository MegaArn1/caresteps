"""Restricted tools the model may call.

The architecture claims the model cannot write freely to the database. That claim is
true because of this package: the model can only ask for a *named* operation with
*schema-validated* arguments, and every operation runs server-side through
``repository``. There is no SQL, no URL fetching, and no arbitrary code path here.

Two-phase writes
----------------
Anything that creates a health record is split into ``prepare_*`` and ``confirm_*``.
The prepare step validates and returns a draft; the confirm step persists. A draft the
user abandons writes nothing (M1 acceptance criterion). The model may call prepare
freely but the confirm step is reachable from the UI only by an explicit user action,
which is what makes "the model cannot write to storage on its own" structurally true
rather than a matter of good behaviour.
"""

from __future__ import annotations

from .contracts import TOOL_SCHEMAS, tool_summary
from .handlers import ToolContext, ToolResult, dispatch

__all__ = ["TOOL_SCHEMAS", "ToolContext", "ToolResult", "dispatch", "tool_summary"]
