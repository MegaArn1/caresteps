"""System-wide operational statistics.

The unparameterised endpoint is intentionally global: it supports a future operations
panel and does not create a browser session or seed demo data as a side effect.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from .. import repository as repo
from .deps import current_user_id, read_conn

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/stats")
def stats(request: Request, days: int | None = None):
    """Return global system metrics.

    Earlier versions used ``/api/stats?days=N`` for per-user period statistics. The
    optional ``days`` branch preserves that explicit contract while the unparameterised
    endpoint now returns the operational totals required by the monitoring task.
    """
    if days is not None:
        from .. import stats as stats_mod

        user_id = current_user_id(request)
        conn = read_conn()
        try:
            return {
                "ok": True,
                "stats": stats_mod.build_period_stats(conn, user_id, days=days),
            }
        finally:
            conn.close()

    conn = read_conn()
    try:
        return repo.system_metrics(conn)
    finally:
        conn.close()
