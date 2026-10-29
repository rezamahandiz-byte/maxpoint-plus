"""Local-only analytics. No network, no async, no heavy deps.

Public functions (per spec):
    today_summary(date)         -> dict(minutes, tests, goal_percent, next_step_text)
    weekly_trend(weeks=4)       -> list[dict] (one entry per week, oldest → newest)
    goal_gap(activity_id, period) -> dict(target, actual, gap)  [re-exported from goals]
    data_quality(date_range)    -> float (percent of days recorded, 0..100)
    exam_taraz_series()         -> list[(exam_number, taraz)]
    last_7_days_minutes()       -> list[(date_str, minutes)]  (used by Analysis tab)

Every function returns zeros / empty on missing data. Never raises.
"""
from __future__ import annotations

from datetime import date, timedelta

from services.clock_sync import now_local
from typing import Optional

from . import db, models
from . import goals as _goals


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa(value) -> str:
    """Render an int/float/str with Persian digits. Used for display only."""
    return str(value).translate(_FA_DIGITS)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def today_summary(today: Optional[date] = None) -> dict:
    """Single-shot summary used by the Home tab.

    Returns:
        {
          'minutes':     int,        # total study minutes today
          'tests':       int,        # total tests done today
          'goal_percent': float,     # 0..100 (averaged across all daily goals)
          'goal_gap_text': str,      # short Persian phrase for the next-step card
          'next_step_text': str,     # one concrete suggestion (local logic only)
          'sessions_count': int,
        }
    """
    today = today or now_local().date()
    today_str = today.isoformat()
    sessions = models.list_sessions_for_date(today_str)

    study_group_ids = _study_group_ids()
    study_minutes = sum(s.minutes for s in sessions
                        if _activity_in_groups(s.activity_id, study_group_ids))
    total_tests = sum(s.tests_count for s in sessions)

    # Goal progress: average across all daily goals defined.
    gaps = _goals.daily_gaps(today)
    if gaps:
        goal_percent = round(sum(g.percent for g in gaps) / len(gaps), 1)
    else:
        goal_percent = 0.0

    next_step_text = _next_step(today, gaps, study_minutes, total_tests)
    goal_gap_text = _gap_phrase(gaps)

    return {
        "minutes": study_minutes,
        "tests": total_tests,
        "goal_percent": goal_percent,
        "goal_gap_text": goal_gap_text,
        "next_step_text": next_step_text,
        "sessions_count": len(sessions),
    }


def weekly_trend(weeks: int = 4) -> list[dict]:
    """One entry per Iranian calendar week (Saturday–Friday), oldest first.

    Each entry: {'week_start': 'YYYY-MM-DD', 'minutes': int, 'tests': int}
    Empty weeks are returned with zeros — the chart should still render.
    """
    weeks = max(1, min(weeks, 12))
    today = now_local().date()
    saturday = today - timedelta(days=(today.weekday() + 2) % 7)

    out: list[dict] = []
    for i in range(weeks - 1, -1, -1):
        ws = saturday - timedelta(weeks=i)
        we = ws + timedelta(days=6)
        rows = models.list_sessions_in_range(ws.isoformat(), we.isoformat())
        out.append({
            "week_start": ws.isoformat(),
            "minutes": sum(r.minutes for r in rows),
            "tests": sum(r.tests_count for r in rows),
        })
    return out


def data_quality(date_range: tuple[date, date]) -> float:
    """Percent of days in the range with at least one recorded session.

    Returns 0.0 for an empty range. Capped at 100.0.
    """
    start, end = date_range
    if end < start:
        start, end = end, start
    days = (end - start).days + 1
    if days <= 0:
        return 0.0

    rows = db.fetch_all(
        "SELECT DISTINCT date FROM sessions WHERE date BETWEEN ? AND ?;",
        (start.isoformat(), end.isoformat()),
    )
    recorded = len(rows)
    return round(100.0 * recorded / days, 1)


def exam_taraz_series() -> list[tuple[int, int]]:
    """List of (exam_number, taraz) sorted by exam_number. Empty if no exams."""
    exams = models.list_exams()
    return [(e.exam_number, e.taraz) for e in exams]


def last_7_days_minutes(today: Optional[date] = None) -> list[tuple[str, int]]:
    """[(date_str, minutes), ...] for the last 7 days, oldest → newest.
    [Ch3] Single SQL query instead of 7 separate queries."""
    today = today or now_local().date()
    start = today - timedelta(days=6)
    rows = db.fetch_all(
        "SELECT date, SUM(minutes) as m FROM sessions "
        "WHERE date BETWEEN ? AND ? GROUP BY date;",
        (start.isoformat(), today.isoformat()),
    )
    by_date = {r["date"]: int(r["m"] or 0) for r in rows}
    return [(d.isoformat(), by_date.get(d.isoformat(), 0))
            for d in (today - timedelta(days=i) for i in range(6, -1, -1))]


def last_7_days_tests(today: Optional[date] = None) -> list[tuple[str, int]]:
    """[Ch3] Single SQL query instead of 7 separate queries."""
    today = today or now_local().date()
    start = today - timedelta(days=6)
    rows = db.fetch_all(
        "SELECT date, SUM(tests_count) as t FROM sessions "
        "WHERE date BETWEEN ? AND ? GROUP BY date;",
        (start.isoformat(), today.isoformat()),
    )
    by_date = {r["date"]: int(r["t"] or 0) for r in rows}
    return [(d.isoformat(), by_date.get(d.isoformat(), 0))
            for d in (today - timedelta(days=i) for i in range(6, -1, -1))]


def last_7_days_summary(today: Optional[date] = None) -> list[dict]:
    """[Ch3] Consolidated 7-day query — minutes + tests in one DB call."""
    today = today or now_local().date()
    start = today - timedelta(days=6)
    rows = db.fetch_all(
        """SELECT date,
                  SUM(minutes) as minutes,
                  SUM(tests_count) as tests,
                  SUM(correct_count) as correct,
                  SUM(wrong_count) as wrong,
                  SUM(blank_count) as blank
           FROM sessions WHERE date BETWEEN ? AND ? GROUP BY date;""",
        (start.isoformat(), today.isoformat()),
    )
    by_date = {r["date"]: dict(r) for r in rows}
    result = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        data = by_date.get(d.isoformat(), {})
        result.append({
            "date": d.isoformat(),
            "minutes": int(data.get("minutes") or 0),
            "tests": int(data.get("tests") or 0),
            "correct": int(data.get("correct") or 0),
            "wrong": int(data.get("wrong") or 0),
            "blank": int(data.get("blank") or 0),
        })
    return result


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _study_group_ids() -> set[int]:
    """Group ids considered 'study' (مطالعه + آزمون). Tests count as study time too."""
    out: set[int] = set()
    for g in models.list_groups():
        if g.name in ("مطالعه", "آزمون"):
            out.add(g.id)
    return out


def _activity_in_groups(activity_id: int, group_ids: set[int]) -> bool:
    if not group_ids:
        return True  # if no groups configured, count everything
    act = models.get_activity(activity_id)
    return bool(act and act.group_id in group_ids)


def _gap_phrase(gaps: list) -> str:
    """A neutral Persian phrase summarising the largest gap. No 'failure'."""
    if not gaps:
        return "هنوز هدفی تعریف نکرده‌ای."
    biggest = gaps[0]
    if biggest.gap_minutes <= 0:
        return "امروز روی برنامه بودی."
    return (f"فاصله از برنامه در {biggest.activity_name}: "
            f"{to_fa(biggest.gap_minutes)} دقیقه.")


def _next_step(today: date, gaps: list, study_minutes: int,
               total_tests: int) -> str:
    """One concrete suggestion. Local logic only. No motivational clichés.

    Priority:
        1. If a daily goal exists with a positive gap and the day isn't over →
           suggest closing the gap on that activity, capped at 25-min chunks.
        2. If no goals defined → suggest recording the first session.
        3. If all goals are met → suggest a short break or a test.
    """
    midday = today  # we don't track time-of-day here; the suggestion stays mild.

    if not gaps:
        return "یک جلسه ۲۵ دقیقه‌ای ثبت کن تا نمودار امروزمت پر شود."

    # Find the activity with the largest remaining gap.
    for g in gaps:
        if g.gap_minutes > 0:
            chunk = min(25, g.gap_minutes)
            return (f"{chunk} دقیقه دیگر برای «{g.activity_name}» ثبت کن "
                    f"تا فاصله از برنامه کمتر شود.")
        if g.gap_tests > 0:
            return (f"{to_fa(g.gap_tests)} آزمون برای «{g.activity_name}» "
                    f"ثبت کن.")

    # All goals met.
    if total_tests == 0:
        return "اهداف امروز محقق شد؛ یک آزمون کوتاه ثبت کن تا روند سنجیده شود."
    return "اهداف امروز محقق شد. ۱۵ دقیقه استراحت فعال پیشنهاد می‌شود."


# --------------------------------------------------------------------------- #
# v0.2 cross-activity and test-quality analytics
# --------------------------------------------------------------------------- #

def time_by_group(start: date, end: date) -> list[dict]:
    """Aggregate minutes by activity group for a date range."""
    rows = db.fetch_all(
        "SELECT COALESCE(g.name, 'سایر') AS group_name, COALESCE(g.color, '#7E8CE0') AS color, "
        "SUM(s.minutes) AS minutes, COUNT(s.id) AS sessions "
        "FROM sessions s JOIN activities a ON a.id=s.activity_id "
        "LEFT JOIN activity_groups g ON g.id=a.group_id "
        "WHERE s.date BETWEEN ? AND ? GROUP BY COALESCE(g.name, 'سایر'), COALESCE(g.color, '#7E8CE0') ORDER BY minutes DESC;",
        (start.isoformat(), end.isoformat()),
    )
    return [dict(r) for r in rows]


def test_quality(start: date, end: date) -> dict:
    """Summed correct/wrong/blank totals; accuracy is None until there are answers."""
    row = db.fetch_one(
        "SELECT COALESCE(SUM(tests_count),0) tests, COALESCE(SUM(correct_count),0) correct, "
        "COALESCE(SUM(wrong_count),0) wrong, COALESCE(SUM(blank_count),0) blank "
        "FROM sessions WHERE date BETWEEN ? AND ?;",
        (start.isoformat(), end.isoformat()),
    )
    d = dict(row) if row else {"tests": 0, "correct": 0, "wrong": 0, "blank": 0}
    answered = d["correct"] + d["wrong"]
    d["accuracy_percent"] = round(100 * d["correct"] / answered, 1) if answered else None
    return d


def time_by_activity(start: date, end: date) -> list[dict]:
    rows = db.fetch_all(
        "SELECT a.id, a.name, COALESCE(a.color, '#7E8CE0') color, SUM(s.minutes) minutes "
        "FROM sessions s JOIN activities a ON a.id=s.activity_id "
        "WHERE s.date BETWEEN ? AND ? GROUP BY a.id, a.name, a.color ORDER BY minutes DESC;",
        (start.isoformat(), end.isoformat()),
    )
    return [dict(r) for r in rows]


def build_aggregate_summary(days: int = 7) -> dict:
    """A small privacy-preserving report payload. Never includes notes or raw sessions."""
    days = max(1, min(int(days), 90))
    today = now_local().date(); start = today - timedelta(days=days - 1)
    groups = time_by_group(start, today)
    tests = test_quality(start, today)
    weekly = weekly_trend(min(12, max(1, (days + 6) // 7)))
    series = exam_taraz_series()[-12:]
    total_minutes = sum(int(g.get("minutes") or 0) for g in groups)
    # Aggregate goal performance without including raw sessions or notes.
    from . import goals as goal_service
    goal_progress = []
    for period, gaps in (("daily", goal_service.daily_gaps(today)), ("weekly", goal_service.weekly_gaps(today))):
        for gap in gaps:
            target = max(0, int(gap.target_minutes))
            actual = max(0, int(gap.actual_minutes))
            goal_progress.append({
                "activity": gap.activity_name,
                "period": "روزانه" if period == "daily" else "هفتگی",
                "target_minutes": target,
                "actual_minutes": actual,
                "remaining_minutes": max(0, target - actual),
                "progress_percent": min(100, round(actual * 100 / target)) if target else None,
                "target_tests": max(0, int(gap.target_tests)),
                "actual_tests": max(0, int(gap.actual_tests)),
            })
    return {
        "report_type": "daily" if days == 1 else ("weekly" if days <= 7 else "monthly"),
        "period_start": start.isoformat(), "period_end": today.isoformat(), "days": days,
        "total_recorded_minutes": total_minutes, "minutes_by_group": [
            {"group": g["group_name"], "minutes": int(g["minutes"] or 0)} for g in groups
        ],
        "active_days": int(db.fetch_one(
            "SELECT COUNT(DISTINCT date) n FROM sessions WHERE date BETWEEN ? AND ?;",
            (start.isoformat(), today.isoformat()))["n"]),
        "data_quality_percent": data_quality((start, today)),
        "tests": tests["tests"], "correct": tests["correct"], "wrong": tests["wrong"],
        "blank": tests["blank"], "accuracy_percent": tests["accuracy_percent"],
        "weekly_trend_minutes": [int(w["minutes"]) for w in weekly],
        "goal_progress": goal_progress,
        "exam_count": len(series),
        "exam_taraz_first": series[0][1] if series else None,
        "exam_taraz_last": series[-1][1] if series else None,
    }


# --------------------------------------------------------------------------- #
# Extended analytics — monthly comparison, yearly summary, predictions
# --------------------------------------------------------------------------- #


def monthly_comparison(months: int = 3) -> list[dict]:
    """Compare study minutes across the last N months.

    Returns a list of dicts:
      [{"month": "YYYY-MM", "label": "ماه X", "minutes": int, "tests": int,
        "sessions": int, "active_days": int}]
    """
    from datetime import date as _date
    today = _date.today()
    result: list[dict] = []

    for i in range(months - 1, -1, -1):
        # Calculate month start and end
        if today.month - i <= 0:
            year = today.year - 1
            month = today.month - i + 12
        else:
            year = today.year
            month = today.month - i

        start = _date(year, month, 1)
        if month == 12:
            end = _date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = _date(year, month + 1, 1) - timedelta(days=1)
        if end > today:
            end = today

        sessions = models.list_sessions_in_range(start.isoformat(), end.isoformat())
        minutes = sum(s.minutes for s in sessions)
        tests = sum(s.tests_count for s in sessions)
        active_days = len({s.date for s in sessions})

        fa_months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                      "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        from core.fa_dates import gregorian_to_jalali
        jy, jm, _ = gregorian_to_jalali(year, month, 1)
        label = f"{fa_months[jm-1]} {to_fa(jy)}"

        result.append({
            "month": f"{year:04d}-{month:02d}",
            "label": label,
            "minutes": minutes,
            "tests": tests,
            "sessions": len(sessions),
            "active_days": active_days,
        })

    return result


def yearly_summary(year: Optional[int] = None) -> dict:
    """Summary of a full year (defaults to current year).

    Returns:
      {"total_minutes": int, "total_tests": int, "active_days": int,
       "total_sessions": int, "best_month": dict, "subjects": list}
    """
    from datetime import date as _date
    if year is None:
        year = _date.today().year

    start = _date(year, 1, 1)
    end = _date(year, 12, 31)
    sessions = models.list_sessions_in_range(start.isoformat(), end.isoformat())

    total_minutes = sum(s.minutes for s in sessions)
    total_tests = sum(s.tests_count for s in sessions)
    active_days = len({s.date for s in sessions})

    # Best month
    monthly = monthly_comparison(12)
    best_month = max(monthly, key=lambda m: m["minutes"], default=None)

    # Subject breakdown
    from collections import defaultdict
    subject_minutes: dict = defaultdict(int)
    activities = {a.id: a for a in models.list_activities(active_only=False)}
    for s in sessions:
        act = activities.get(s.activity_id)
        name = act.name if act else "سایر"
        subject_minutes[name] += s.minutes

    subjects = sorted(
        [{"name": k, "minutes": v} for k, v in subject_minutes.items()],
        key=lambda x: x["minutes"],
        reverse=True,
    )[:10]

    return {
        "year": year,
        "total_minutes": total_minutes,
        "total_tests": total_tests,
        "active_days": active_days,
        "total_sessions": len(sessions),
        "best_month": best_month,
        "subjects": subjects,
        "avg_daily": total_minutes // 365 if total_minutes > 0 else 0,
    }


def predict_goal_completion(activity_id: int, period: str = "daily",
                            today: Optional[date] = None) -> Optional[dict]:
    """Predict when a goal will be completed based on current pace.

    Returns:
      {"activity_name": str, "target": int, "actual": int, "remaining": int,
       "avg_per_day": float, "estimated_days": int, "estimated_date": str}
      or None if no goal or no history.
    """
    today = today or date.today()
    from . import goals as goal_service
    gap = goal_service.goal_gap(activity_id, period, today)
    if gap is None or gap.target_minutes <= 0:
        return None

    remaining = max(0, gap.gap_minutes)
    if remaining <= 0:
        return {
            "activity_name": gap.activity_name,
            "target": gap.target_minutes,
            "actual": gap.actual_minutes,
            "remaining": 0,
            "avg_per_day": 0,
            "estimated_days": 0,
            "estimated_date": "محقق شد",
        }

    # Calculate average per day from last 7 days
    start = today - timedelta(days=6)
    sessions = models.list_sessions_in_range(start.isoformat(), today.isoformat())
    recent_minutes = sum(s.minutes for s in sessions if s.activity_id == activity_id)
    avg_per_day = recent_minutes / 7.0

    if avg_per_day <= 0:
        estimated_days = -1  # can't predict
    else:
        estimated_days = int(remaining / avg_per_day) + 1

    if estimated_days > 0:
        estimated_date = (today + timedelta(days=estimated_days)).isoformat()
    elif estimated_days == 0:
        estimated_date = "امروز"
    else:
        estimated_date = "غیرقابل پیش‌بینی"

    return {
        "activity_name": gap.activity_name,
        "target": gap.target_minutes,
        "actual": gap.actual_minutes,
        "remaining": remaining,
        "avg_per_day": round(avg_per_day, 1),
        "estimated_days": estimated_days,
        "estimated_date": estimated_date,
    }


def subject_heatmap(days: int = 14) -> list[dict]:
    """Generate a heatmap of study activity per subject per day.

    Returns:
      [{"date": str, "subjects": {activity_name: minutes}}]
    """
    today = date.today()
    start = today - timedelta(days=days - 1)
    sessions = models.list_sessions_in_range(start.isoformat(), today.isoformat())

    activities = {a.id: a for a in models.list_activities(active_only=False)}
    by_date: dict[str, dict[str, int]] = {}

    for s in sessions:
        act = activities.get(s.activity_id)
        name = act.name if act else "سایر"
        by_date.setdefault(s.date, {})
        by_date[s.date][name] = by_date[s.date].get(name, 0) + s.minutes

    result = []
    check = start
    while check <= today:
        d = check.isoformat()
        result.append({
            "date": d,
            "subjects": by_date.get(d, {}),
            "total": sum(by_date.get(d, {}).values()),
        })
        check += timedelta(days=1)

    return result
