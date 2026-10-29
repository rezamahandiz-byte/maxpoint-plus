"""Local insights — pattern detection and suggestions without AI.

This module analyzes the user's data and generates human-readable
insights in Persian. No network, no AI — just local pattern matching.

Insight types:
  - "best_time": When does the user study most effectively?
  - "weak_subject": Which subject has the most wrong answers?
  - "streak_risk": Is the current streak at risk today?
  - "goal_pace": Is the user on track to meet weekly goals?
  - "balance": Is study time balanced across subjects?
  - "improvement": Has accuracy improved compared to last week?
  - "consistency": How consistent is the study schedule?
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core import db, models, analytics
from core.fa_dates import to_fa_digits


def generate_insights(today: Optional[date] = None, max_count: int = 5) -> list[dict]:
    """Generate a list of insights, sorted by relevance.

    Returns:
      [{"type": str, "title": str, "body": str, "icon": str, "color": str}]
    """
    today = today or date.today()
    insights: list[dict] = []
    ACCENT = "#4EA1A1"
    SUCCESS = "#3FB950"
    WARN = "#D29922"
    INFO = "#58A6FF"

    # 1. Best study time
    best_time = _best_study_time(today)
    if best_time:
        insights.append({
            "type": "best_time",
            "title": "بهترین زمان مطالعه",
            "body": best_time,
            "icon": "schedule",
            "color": INFO,
        })

    # 2. Weak subject
    weak = _weak_subject(today)
    if weak:
        insights.append({
            "type": "weak_subject",
            "title": "درس نیازمند توجه",
            "body": weak,
            "icon": "warning",
            "color": WARN,
        })

    # 3. Streak risk
    streak_risk = _streak_risk(today)
    if streak_risk:
        insights.append({
            "type": "streak_risk",
            "title": "ریسک قطع رکورد",
            "body": streak_risk,
            "icon": "local_fire_department",
            "color": WARN,
        })

    # 4. Goal pace
    pace = _goal_pace(today)
    if pace:
        insights.append({
            "type": "goal_pace",
            "title": "پیشرفت هدف",
            "body": pace,
            "icon": "flag",
            "color": ACCENT,
        })

    # 5. Balance
    balance = _balance_insight(today)
    if balance:
        insights.append({
            "type": "balance",
            "title": "توازن مطالعه",
            "body": balance,
            "icon": "balance",
            "color": ACCENT,
        })

    # 6. Improvement
    improvement = _improvement_insight(today)
    if improvement:
        insights.append({
            "type": "improvement",
            "title": "روند پیشرفت",
            "body": improvement,
            "icon": "trending_up",
            "color": SUCCESS,
        })

    # 7. Consistency
    consistency = _consistency_insight(today)
    if consistency:
        insights.append({
            "type": "consistency",
            "title": "نظم مطالعه",
            "body": consistency,
            "icon": "calendar_today",
            "color": INFO,
        })

    return insights[:max_count]


def _best_study_time(today: date) -> Optional[str]:
    """Find the hour with most study sessions in last 30 days."""
    start = today - timedelta(days=30)
    rows = db.fetch_all(
        """SELECT CAST(substr(created_at, 12, 2) AS INTEGER) as hour,
                  SUM(minutes) as total
           FROM sessions
           WHERE date BETWEEN ? AND ?
             AND created_at IS NOT NULL
           GROUP BY hour ORDER BY total DESC LIMIT 1;""",
        (start.isoformat(), today.isoformat()),
    )
    if not rows or not rows[0]["hour"]:
        return None
    hour = int(rows[0]["hour"])
    total = int(rows[0]["total"] or 0)
    if total < 30:
        return None
    period = "صبح" if 5 <= hour < 12 else ("ظهر" if 12 <= hour < 17 else ("عصر" if 17 <= hour < 21 else "شب"))
    return f"بیشترین مطالعه‌ات در ساعت {to_fa_digits(hour):0>2}:00 ({period}) است — {to_fa_digits(total)} دقیقه در ۳۰ روز اخیر."


def _weak_subject(today: date) -> Optional[str]:
    """Find the subject with the worst test accuracy."""
    start = today - timedelta(days=30)
    rows = db.fetch_all(
        """SELECT a.name,
                  SUM(s.correct_count) as correct,
                  SUM(s.wrong_count) as wrong,
                  SUM(s.tests_count) as total
           FROM sessions s
           JOIN activities a ON s.activity_id = a.id
           WHERE s.date BETWEEN ? AND ?
             AND s.tests_count > 0
           GROUP BY s.activity_id
           HAVING total >= 5
           ORDER BY (CAST(correct AS FLOAT) / (correct + wrong + 1)) ASC
           LIMIT 1;""",
        (start.isoformat(), today.isoformat()),
    )
    if not rows:
        return None
    row = rows[0]
    correct = int(row["correct"] or 0)
    wrong = int(row["wrong"] or 0)
    total = int(row["total"] or 0)
    if correct + wrong == 0:
        return None
    accuracy = round(100 * correct / (correct + wrong))
    if accuracy >= 70:
        return None  # not actually weak
    return f"درس «{row['name']}» با دقت {to_fa_digits(accuracy)}٪ (از {to_fa_digits(total)} تست) ضعیف‌ترین عملکرد را دارد. مرور بیشتری توصیه می‌شود."


def _streak_risk(today: date) -> Optional[str]:
    """Check if today's streak is at risk (no sessions yet today)."""
    sessions_today = models.list_sessions_for_date(today.isoformat())
    if sessions_today:
        return None  # streak is safe

    from core import streaks
    current = streaks.current_streak(today)
    if current < 2:
        return None  # no meaningful streak to risk

    return f"امروز هنوز چیزی ثبت نشده. رکورد {to_fa_digits(current)} روزه‌ات در خطر قطع است — حتی ۱۵ دقیقه ثبت کن."


def _goal_pace(today: date) -> Optional[str]:
    """Check if the user is on track for weekly goals."""
    from core import goals as goal_service
    gaps = goal_service.weekly_gaps(today)
    if not gaps:
        return None

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    days_passed = (today - monday).days + 1
    days_remaining = (sunday - today).days + 1

    at_risk = []
    for gap in gaps:
        target = gap.target_minutes
        expected = target * days_passed / 7
        if gap.actual_minutes < expected * 0.7:  # less than 70% of expected
            at_risk.append(gap.activity_name)

    if not at_risk:
        return "پیشرفت هدف‌های هفتگی متناسب با گذر زمان است. ادامه بده!"

    return f"درس‌های {', '.join(at_risk[:3])} عقب‌تر از برنامه هستند. {to_fa_digits(days_remaining)} روز فرصت داری."


def _balance_insight(today: date) -> Optional[str]:
    """Check study balance across subjects."""
    from core import planner
    balance = planner.balance_check(today)
    if not balance["subjects"] or len(balance["subjects"]) < 2:
        return None

    if balance["balanced"]:
        return "مطالعه‌ات بین درس‌ها متعادل است."

    spread = balance["max_percent"] - balance["min_percent"]
    most = balance["subjects"][0]["name"]
    least = balance["subjects"][-1]["name"]
    return f"اختلاف زیاد: «{most}» {to_fa_digits(balance['max_percent'])}٪ ولی «{least}» فقط {to_fa_digits(balance['min_percent'])}٪. سهم درس‌های کمتر را بیشتر کن."


def _improvement_insight(today: date) -> Optional[str]:
    """Compare this week's accuracy to last week's."""
    this_week_start = today - timedelta(days=6)
    last_week_start = today - timedelta(days=13)
    last_week_end = today - timedelta(days=7)

    this_stats = analytics.test_quality(this_week_start, today)
    last_stats = analytics.test_quality(last_week_start, last_week_end)

    this_acc = this_stats.get("accuracy_percent")
    last_acc = last_stats.get("accuracy_percent")

    if this_acc is None or last_acc is None:
        return None

    diff = this_acc - last_acc
    if abs(diff) < 5:
        return None  # no significant change

    if diff > 0:
        return f"دقت تست‌هایت این هفته {to_fa_digits(diff)} درصد نسبت به هفته‌ی قبل بهتر شده."
    else:
        return f"دقت تست‌هایت این هفته {to_fa_digits(abs(diff))} درصد نسبت به هفته‌ی قبل افت داشته. مرور بیشتر مفید است."


def _consistency_insight(today: date) -> Optional[str]:
    """Check study consistency."""
    from core import streaks
    history = streaks.streak_history(14)
    active_days = sum(1 for _, has in history if has)
    total_days = len(history)

    if total_days == 0:
        return None

    pct = round(100 * active_days / total_days)

    if pct >= 80:
        return f"در ۱۴ روز اخیر {to_fa_digits(active_days)} روز فعال بودی ({to_fa_digits(pct)}٪). نظم عالی!"
    elif pct >= 50:
        return f"در ۱۴ روز اخیر {to_fa_digits(active_days)} روز فعال بودی ({to_fa_digits(pct)}٪). می‌توانی منظم‌تر باشی."
    else:
        return f"در ۱۴ روز اخیر فقط {to_fa_digits(active_days)} روز فعال بودی ({to_fa_digits(pct)}٪). ثبت منظم‌تر، تحلیل بهتر."
