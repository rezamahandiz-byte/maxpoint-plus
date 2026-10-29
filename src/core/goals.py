"""Goal resolution helpers.

A goal is "target minutes / target tests per period" for a specific activity.
This module turns rows in the `goals` table into numbers the UI can show:
target, actual, and the gap (signed; positive = behind, negative = ahead).

The app never says "شکست" (failure). A non-zero gap is "فاصله از برنامه"
(distance from plan).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from services.clock_sync import now_local
from typing import Optional

from . import db, models


@dataclass(frozen=True)
class GoalGap:
    activity_id: int
    activity_name: str
    period: str          # 'daily' | 'weekly'
    target_minutes: int
    target_tests: int
    actual_minutes: int
    actual_tests: int

    @property
    def gap_minutes(self) -> int:
        """Positive = behind plan, negative = ahead of plan."""
        return self.target_minutes - self.actual_minutes

    @property
    def gap_tests(self) -> int:
        return self.target_tests - self.actual_tests

    @property
    def percent(self) -> float:
        """0..100 (capped) — progress toward the minute target."""
        if self.target_minutes <= 0:
            return 0.0
        return min(100.0, round(100.0 * self.actual_minutes / self.target_minutes, 1))


def _week_range(d: date) -> tuple[date, date]:
    """Return the Iranian calendar week (Saturday through Friday)."""
    saturday = d - timedelta(days=(d.weekday() + 2) % 7)
    friday = saturday + timedelta(days=6)
    return saturday, friday


def goal_gap(activity_id: int, period: str,
             today: Optional[date] = None) -> Optional[GoalGap]:
    """Return target/actual/gap for one activity+period.

    Returns None if no goal is defined. Always returns zeros (never raises)
    if the activity or its sessions are missing — see spec
    "All functions must handle empty data gracefully (return zeros, not errors)."
    """
    today = today or now_local().date()
    goal = models.get_goal(activity_id, period)
    if goal is None:
        return None

    act = models.get_activity(activity_id)
    name = act.name if act else ""

    if period == "daily":
        start = end = today
    elif period == "weekly":
        s, e = _week_range(today)
        start, end = s, e
    else:
        return None

    sessions = models.list_sessions_in_range(start.isoformat(), end.isoformat())
    actual_minutes = sum(s.minutes for s in sessions if s.activity_id == activity_id)
    actual_tests = sum(s.tests_count for s in sessions if s.activity_id == activity_id)

    return GoalGap(
        activity_id=activity_id,
        activity_name=name,
        period=period,
        target_minutes=goal.target_minutes,
        target_tests=goal.target_tests,
        actual_minutes=actual_minutes,
        actual_tests=actual_tests,
    )


def daily_gaps(today: Optional[date] = None) -> list[GoalGap]:
    """All daily goals with their gaps. Sorted by gap descending (largest deficit first)."""
    today = today or now_local().date()
    out: list[GoalGap] = []
    for g in models.list_goals():
        if g.period == "daily":
            gg = goal_gap(g.activity_id, "daily", today)
            if gg is not None:
                out.append(gg)
    out.sort(key=lambda x: x.gap_minutes, reverse=True)
    return out


def weekly_gaps(today: Optional[date] = None) -> list[GoalGap]:
    today = today or now_local().date()
    out: list[GoalGap] = []
    for g in models.list_goals():
        if g.period == "weekly":
            gg = goal_gap(g.activity_id, "weekly", today)
            if gg is not None:
                out.append(gg)
    out.sort(key=lambda x: x.gap_minutes, reverse=True)
    return out


def set_goal(activity_id: int, period: str,
             target_minutes: int, target_tests: int = 0) -> None:
    """Convenience wrapper used by Settings."""
    models.upsert_goal(activity_id, period, int(target_minutes), int(target_tests))


def remove_goal(activity_id: int, period: str) -> None:
    models.delete_goal(activity_id, period)
