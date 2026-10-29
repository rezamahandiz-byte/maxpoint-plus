"""Study planner — daily and weekly study schedule.

This module provides a simple study planner that suggests a daily
schedule based on the user's goals and activities. It generates:
  - A suggested daily schedule (which subjects to study and for how long)
  - A weekly overview (total planned minutes per day)
  - A balance check (are goals distributed evenly?)

The planner is LOCAL only — no AI, no network. It uses a simple
algorithm: distribute goal minutes across active days.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core import models, goals as goal_service
from core.fa_dates import to_fa_digits


def daily_plan(today: Optional[date] = None) -> list[dict]:
    """Suggest a study plan for today based on daily goals.

    Returns a list of dicts:
      [{"activity_id": int, "name": str, "target_minutes": int,
        "color": str, "suggested_minutes": int}]
    """
    today = today or date.today()
    gaps = goal_service.daily_gaps(today)

    if not gaps:
        return []

    plan: list[dict] = []
    for gap in gaps:
        remaining = max(0, gap.gap_minutes)
        if remaining <= 0:
            continue  # goal already met
        # Suggest studying in 25-minute chunks, max 2 hours per subject
        suggested = min(remaining, 120)
        # Round to nearest 5
        suggested = round(suggested / 5) * 5
        if suggested < 15:
            suggested = 15

        act = models.get_activity(gap.activity_id)
        plan.append({
            "activity_id": gap.activity_id,
            "name": gap.activity_name,
            "target_minutes": gap.target_minutes,
            "actual_minutes": gap.actual_minutes,
            "remaining_minutes": remaining,
            "suggested_minutes": suggested,
            "color": act.color if act and act.color else "#4EA1A1",
        })

    # Sort by remaining minutes (largest deficit first)
    plan.sort(key=lambda x: x["remaining_minutes"], reverse=True)
    return plan


def weekly_plan(today: Optional[date] = None) -> list[dict]:
    """Suggest a weekly study plan based on weekly goals.

    Returns a list of dicts:
      [{"activity_id": int, "name": str, "target_minutes": int,
        "remaining_minutes": int, "per_day_minutes": int}]
    """
    today = today or date.today()
    gaps = goal_service.weekly_gaps(today)

    if not gaps:
        return []

    # Days remaining in the week (Monday to Sunday)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    days_remaining = (sunday - today).days + 1
    if days_remaining <= 0:
        days_remaining = 1

    plan: list[dict] = []
    for gap in gaps:
        remaining = max(0, gap.gap_minutes)
        if remaining <= 0:
            continue
        per_day = remaining // days_remaining
        per_day = max(15, round(per_day / 5) * 5)

        act = models.get_activity(gap.activity_id)
        plan.append({
            "activity_id": gap.activity_id,
            "name": gap.activity_name,
            "target_minutes": gap.target_minutes,
            "actual_minutes": gap.actual_minutes,
            "remaining_minutes": remaining,
            "per_day_minutes": per_day,
            "days_remaining": days_remaining,
            "color": act.color if act and act.color else "#4EA1A1",
        })

    plan.sort(key=lambda x: x["remaining_minutes"], reverse=True)
    return plan


def balance_check(today: Optional[date] = None) -> dict:
    """Check if study time is balanced across subjects.

    Returns:
      {"balanced": bool, "min_percent": float, "max_percent": float,
       "subjects": [{"name": str, "percent": float, "minutes": int}]}
    """
    today = today or date.today()
    start = today - timedelta(days=6)
    from core import analytics
    rows = analytics.time_by_activity(start, today)
    total = sum(int(r.get("minutes") or 0) for r in rows)

    if not rows or total <= 0:
        return {"balanced": True, "min_percent": 0, "max_percent": 0, "subjects": []}

    subjects = []
    for row in rows:
        minutes = int(row.get("minutes") or 0)
        pct = round(100 * minutes / total, 1)
        subjects.append({
            "name": row.get("activity_name", "سایر"),
            "percent": pct,
            "minutes": minutes,
            "color": row.get("color"),
        })

    pcts = [s["percent"] for s in subjects]
    min_pct = min(pcts) if pcts else 0
    max_pct = max(pcts) if pcts else 0
    # Balanced if the spread is less than 30 percentage points
    balanced = (max_pct - min_pct) < 30

    return {
        "balanced": balanced,
        "min_percent": min_pct,
        "max_percent": max_pct,
        "subjects": subjects,
    }


def plan_summary(today: Optional[date] = None) -> dict:
    """Complete plan summary for the study tab."""
    today = today or date.today()
    daily = daily_plan(today)
    weekly = weekly_plan(today)
    balance = balance_check(today)

    total_suggested = sum(p["suggested_minutes"] for p in daily)
    total_weekly_remaining = sum(p["remaining_minutes"] for p in weekly)

    return {
        "daily_plan": daily,
        "weekly_plan": weekly,
        "balance": balance,
        "total_suggested_today": total_suggested,
        "total_weekly_remaining": total_weekly_remaining,
    }
