"""Study streak tracking — consecutive days with recorded activity.

A "streak" is the number of consecutive days (ending today or yesterday)
with at least one recorded study session. This module calculates:
  - Current streak (consecutive days ending today or yesterday)
  - Longest streak ever
  - Total active days
  - Streak history (last 30 days)

Streaks are computed from the `sessions` table — no separate storage.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core import db, models


def current_streak(today: Optional[date] = None) -> int:
    """Number of consecutive days (ending today or yesterday) with sessions.

    If today has sessions, the streak includes today.
    If today has none but yesterday does, the streak ends yesterday.
    If neither has sessions, the streak is 0.
    """
    today = today or date.today()
    streak = 0

    # Check today first
    sessions_today = models.list_sessions_for_date(today.isoformat())
    if sessions_today:
        streak = 1
        check_date = today - timedelta(days=1)
    else:
        # If today has no sessions, check yesterday
        sessions_yesterday = models.list_sessions_for_date(
            (today - timedelta(days=1)).isoformat())
        if sessions_yesterday:
            streak = 1
            check_date = today - timedelta(days=2)
        else:
            return 0

    # Walk backwards counting consecutive days
    while True:
        sessions = models.list_sessions_for_date(check_date.isoformat())
        if sessions:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


def longest_streak(lookback_days: int = 365) -> int:
    """Longest streak in the last `lookback_days` days."""
    today = date.today()
    start = today - timedelta(days=lookback_days)

    # Get all dates with sessions in the range
    rows = db.fetch_all(
        "SELECT DISTINCT date FROM sessions WHERE date BETWEEN ? AND ? ORDER BY date;",
        (start.isoformat(), today.isoformat()),
    )
    if not rows:
        return 0

    dates_with_sessions = {row["date"] for row in rows}
    longest = 0
    current = 0
    check = start

    while check <= today:
        if check.isoformat() in dates_with_sessions:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
        check += timedelta(days=1)

    return longest


def total_active_days(lookback_days: int = 365) -> int:
    """Total number of distinct days with at least one session."""
    today = date.today()
    start = today - timedelta(days=lookback_days)
    rows = db.fetch_all(
        "SELECT COUNT(DISTINCT date) as c FROM sessions WHERE date BETWEEN ? AND ?;",
        (start.isoformat(), today.isoformat()),
    )
    return rows[0]["c"] if rows else 0


def streak_history(days: int = 30) -> list[tuple[str, bool]]:
    """List of (date_str, has_sessions) for the last `days` days.

    Used to render a streak calendar/heatmap.
    """
    today = date.today()
    start = today - timedelta(days=days - 1)

    rows = db.fetch_all(
        "SELECT DISTINCT date FROM sessions WHERE date BETWEEN ? AND ?;",
        (start.isoformat(), today.isoformat()),
    )
    dates_with_sessions = {row["date"] for row in rows}

    result: list[tuple[str, bool]] = []
    check = start
    while check <= today:
        result.append((check.isoformat(), check.isoformat() in dates_with_sessions))
        check += timedelta(days=1)

    return result


def streak_summary(today: Optional[date] = None) -> dict:
    """Complete streak summary for the Home tab."""
    today = today or date.today()
    return {
        "current": current_streak(today),
        "longest": longest_streak(),
        "total_active_days": total_active_days(),
        "history_30d": streak_history(30),
    }
