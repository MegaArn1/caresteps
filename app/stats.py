"""Deterministic statistics.

This module exists because of a specific design commitment: **every number the user
sees is computed here, not by a language model.** The model is handed the output of
these functions and may only re-phrase it. That removes the largest class of
hallucination in a health app and makes the numbers independently checkable.

Consequences that show up in the return values:

* Every result carries ``n``, ``window``, ``from``/``to`` and an ``insufficient`` flag
  so the UI can always show the denominator and the range.
* ``insufficient`` is reported rather than smoothed over. We return ``None`` for means
  instead of a default, so no caller can accidentally plot a fabricated value.
* No function here infers causation. ``compare_windows`` reports that two windows
  differ; it does not report that anything caused the difference.
"""

from __future__ import annotations

import sqlite3
import statistics
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Iterable

# Minimum readings before we will describe a period at all. Below this, the honest
# answer is "there is not enough to compare" — see M4 acceptance criteria.
MIN_READINGS_FOR_MEAN = 2

# A window needs at least this many readings in each half before a comparison is
# offered, otherwise we would be contrasting a fortnight against a single reading.
MIN_READINGS_PER_WINDOW_FOR_COMPARISON = 3


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso_date(value: str) -> str:
    return value[:10]


# --------------------------------------------------------------------- windows


def resolve_window(days: int, end: date | None = None) -> tuple[date, date]:
    """Return an inclusive ``(start, end)`` date pair ending today by default."""
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    return start, end


def coverage(
    readings: Iterable[dict], start: date, end: date
) -> dict[str, Any]:
    """Describe how much of a window actually has data.

    ``missing_days`` is reported explicitly rather than drawn as a straight line
    between distant points, which is the failure mode M4 warns about.
    """
    total_days = (end - start).days + 1
    days_with_data: set[str] = set()
    for r in readings:
        d = _iso_date(r["measured_at"])
        if start.isoformat() <= d <= end.isoformat():
            days_with_data.add(d)

    all_days = {(start + timedelta(days=i)).isoformat() for i in range(total_days)}
    missing = sorted(all_days - days_with_data)
    return {
        "window_days": total_days,
        "days_with_data": len(days_with_data),
        "missing_days": len(missing),
        "missing_dates": missing,
        "coverage_ratio": round(len(days_with_data) / total_days, 3) if total_days else 0.0,
    }


# ------------------------------------------------------------------- summaries


def summarize(
    readings: list[dict], start: date, end: date, label: str | None = None
) -> dict[str, Any]:
    """Descriptive statistics for one window.

    Returns means of ``None`` when there is too little data, plus a plain-language
    note. Callers must handle ``None``; nothing here substitutes a fake number.
    """
    in_window = [
        r
        for r in readings
        if start.isoformat() <= _iso_date(r["measured_at"]) <= end.isoformat()
    ]
    systolics = [r["systolic"] for r in in_window]
    diastolics = [r["diastolic"] for r in in_window]
    cov = coverage(readings, start, end)

    sufficient = len(in_window) >= MIN_READINGS_FOR_MEAN
    result: dict[str, Any] = {
        "label": label or f"{start.isoformat()} to {end.isoformat()}",
        "window": {"from": start.isoformat(), "to": end.isoformat(), "days": cov["window_days"]},
        "n": len(in_window),
        "sufficient": sufficient,
        "mean_systolic": round(statistics.fmean(systolics), 1) if sufficient else None,
        "mean_diastolic": round(statistics.fmean(diastolics), 1) if sufficient else None,
        "min_systolic": min(systolics) if systolics else None,
        "max_systolic": max(systolics) if systolics else None,
        "min_diastolic": min(diastolics) if diastolics else None,
        "max_diastolic": max(diastolics) if diastolics else None,
        "coverage": cov,
    }

    if not sufficient:
        result["note"] = (
            f"Only {len(in_window)} reading(s) recorded between {start.isoformat()} "
            f"and {end.isoformat()}. That is not enough to describe an average."
        )
    else:
        result["note"] = (
            f"Based on {len(in_window)} reading(s) across "
            f"{cov['days_with_data']} day(s) between {start.isoformat()} and "
            f"{end.isoformat()}. {cov['missing_days']} day(s) in this window have no "
            "record."
        )

    # How many readings came in through a correction, so the summary can be honest
    # about how much of the record was revised after the fact.
    result["revised_count"] = sum(
        1 for r in in_window if r.get("entered_source") == "correction"
    )
    return result


def compare_windows(
    readings: list[dict],
    days: int,
    end: date | None = None,
) -> dict[str, Any]:
    """Contrast the most recent window against the one immediately before it.

    Deliberately descriptive. If either half is thin, ``comparable`` is False and the
    delta fields are ``None`` — the app then says it cannot compare rather than
    inviting the user to read a trend into noise (M4).
    """
    end = end or date.today()
    current_start, current_end = resolve_window(days, end)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)

    current = summarize(readings, current_start, current_end, label="This period")
    previous = summarize(readings, previous_start, previous_end, label="Before that")

    enough = (
        current["n"] >= MIN_READINGS_PER_WINDOW_FOR_COMPARISON
        and previous["n"] >= MIN_READINGS_PER_WINDOW_FOR_COMPARISON
    )

    out: dict[str, Any] = {
        "current": current,
        "previous": previous,
        "comparable": enough,
    }

    if not enough:
        out["delta_systolic"] = None
        out["delta_diastolic"] = None
        out["explanation"] = (
            "There is not enough recorded in one or both periods to compare them. "
            f"This period has {current['n']} reading(s); the period before has "
            f"{previous['n']}."
        )
        return out

    out["delta_systolic"] = round(
        current["mean_systolic"] - previous["mean_systolic"], 1
    )
    out["delta_diastolic"] = round(
        current["mean_diastolic"] - previous["mean_diastolic"], 1
    )
    out["explanation"] = (
        f"The average of the top number is {abs(out['delta_systolic'])} "
        f"{'higher' if out['delta_systolic'] > 0 else 'lower' if out['delta_systolic'] < 0 else 'the same'} "
        f"than in the period before. This describes what was recorded; it does not "
        "explain why."
    )
    return out


# ------------------------------------------------------------- adherence stats

ADHERENCE_LABELS = {
    "taken": "You reported taking it",
    "not_taken": "You reported not taking it",
    "unsure": "You were not sure",
    "unrecorded": "No record either way",
}


def adherence_summary(
    reports: list[dict], unrecorded: list[dict], start: date, end: date
) -> dict[str, Any]:
    """Count the four states separately, and never fold one into another.

    The critical property: ``unrecorded`` is counted apart from ``not_taken``. A day
    with no entry is not a day the patient skipped their medicine, and no downstream
    consumer of this dict can make that mistake because the keys are distinct and
    ``unrecorded`` is explicitly flagged ``self_reported: False``.
    """
    in_window = [
        r for r in reports if start.isoformat() <= _iso_date(r["reported_at"]) <= end.isoformat()
    ]
    counts = {"taken": 0, "not_taken": 0, "unsure": 0, "unrecorded": 0}
    for r in in_window:
        if r["status"] in counts:
            counts[r["status"]] += 1

    derived = [
        u
        for u in unrecorded
        if start.isoformat() <= _iso_date(u["scheduled_for"]) <= end.isoformat()
    ]
    counts["unrecorded"] += len(derived)

    self_reported_total = counts["taken"] + counts["not_taken"] + counts["unsure"]
    total_days = (end - start).days + 1

    return {
        "window": {"from": start.isoformat(), "to": end.isoformat(), "days": total_days},
        "counts": counts,
        "labels": ADHERENCE_LABELS,
        "self_reported_total": self_reported_total,
        "has_derived_only_days": len(derived) > 0,
        # Spelled out so the UI and the summary cannot silently contradict it.
        "interpretation": (
            f"{counts['unrecorded']} day(s) in this window have no record either way. "
            "A day with no record does not mean a dose was missed."
        ),
        # Explicitly refused statistic. We do not compute a "compliance rate",
        # because doing so would require treating missing records as misses.
        "note": (
            "This counts what was reported. It is not a measure of how well the "
            "medicine worked, and it is not a measure of true adherence."
        ),
    }


# ------------------------------------------------------------------ the bundle


def build_period_stats(
    conn: sqlite3.Connection, user_id: str, days: int = 14, end: date | None = None
) -> dict[str, Any]:
    """Everything M4 needs, in one auditable structure.

    This function is the *only* source of numbers for trends and for the visit
    summary, so the two can never disagree.
    """
    from . import repository as repo

    end = end or date.today()
    start, _ = resolve_window(days, end)

    readings = repo.list_readings(conn, user_id, days=days + days)  # include a prior window
    reports = repo.list_medication_reports(conn, user_id, days=days + days)
    unrecorded = repo.derive_unrecorded(conn, user_id, start.isoformat(), end.isoformat())

    period = summarize(readings, start, end, label=f"Last {days} days")
    comparison = compare_windows(readings, days, end)
    adherence = adherence_summary(reports, unrecorded, start, end)

    return {
        "period_days": days,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "readings": period,
        "comparison": comparison,
        "adherence": adherence,
        "series": series_for_chart(readings, start, end),
    }


def series_for_chart(
    readings: list[dict], start: date, end: date
) -> dict[str, Any]:
    """Points for the trend chart, with gaps made explicit.

    Returns one entry per calendar day with ``has_data`` set, so the renderer can
    break the line at a gap instead of drawing across it. This is what makes "the
    chart does not hide long gaps by connecting the line" true in code.
    """
    by_day: dict[str, list[dict]] = {}
    for r in readings:
        d = _iso_date(r["measured_at"])
        if start.isoformat() <= d <= end.isoformat():
            by_day.setdefault(d, []).append(r)

    points = []
    day = start
    while day <= end:
        iso = day.isoformat()
        entries = by_day.get(iso, [])
        if entries:
            points.append(
                {
                    "date": iso,
                    "has_data": True,
                    "systolic": round(
                        statistics.fmean([e["systolic"] for e in entries]), 1
                    ),
                    "diastolic": round(
                        statistics.fmean([e["diastolic"] for e in entries]), 1
                    ),
                    "n": len(entries),
                    "had_correction": any(
                        e.get("entered_source") == "correction" for e in entries
                    ),
                }
            )
        else:
            points.append({"date": iso, "has_data": False, "n": 0})
        day += timedelta(days=1)

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "points": points,
        "days_with_data": sum(1 for p in points if p["has_data"]),
        "days_without_data": sum(1 for p in points if not p["has_data"]),
    }


def classify_reading(systolic: int, diastolic: int, bands: list[dict]) -> dict | None:
    """Map a single reading onto classification bands supplied by the rule file.

    The bands come from ``content/rules/`` with a source attached, never from a
    constant buried in code. Returns ``None`` when no band matches, which the UI
    renders as "no category shown" rather than inventing one.
    """
    for band in bands:
        lo_s = band.get("systolic_min", 0)
        hi_s = band.get("systolic_max", 999)
        lo_d = band.get("diastolic_min", 0)
        hi_d = band.get("diastolic_max", 999)
        if lo_s <= systolic <= hi_s and lo_d <= diastolic <= hi_d:
            return band
    return None
