"""Local report generation — weekly and monthly summaries.

These reports are generated locally (no AI, no network). They aggregate
session data into human-readable Persian text summaries.

Report types:
  - daily: today's summary
  - weekly: last 7 days summary
  - monthly: last 30 days summary

Each report is saved to the `reports` table with a generated_at timestamp.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core import analytics, models, db
from core.fa_dates import jalali_label, to_fa_digits
from core import streaks


def generate_daily_report(today: Optional[date] = None) -> str:
    """Generate a Persian text summary of today's activity."""
    today = today or date.today()
    s = analytics.today_summary(today)
    sessions = models.list_sessions_for_date(today.isoformat())

    lines = [
        f"گزارش روز — {_jalali(today)}",
        f"",
        f"دقیقه مطالعه: {to_fa_digits(s['minutes'])}",
        f"تست ثبت‌شده: {to_fa_digits(s['tests'])}",
        f"پیشرفت هدف: {to_fa_digits(s['goal_percent'])}٪",
        f"تعداد جلسات: {to_fa_digits(s['sessions_count'])}",
        f"",
        f"قدم بعدی: {s['next_step_text']}",
    ]

    if sessions:
        lines.append("")
        lines.append("جلسات امروز:")
        activities = {a.id: a for a in models.list_activities(active_only=False)}
        for sess in sessions[:5]:
            act = activities.get(sess.activity_id)
            name = act.name if act else "—"
            detail = f"  • {name}: {to_fa_digits(sess.minutes)} دقیقه"
            if sess.tests_count:
                detail += f"، {to_fa_digits(sess.tests_count)} تست"
            lines.append(detail)

    content = "\n".join(lines)
    _save_report("daily", today, today, content)
    return content


def generate_weekly_report(today: Optional[date] = None) -> str:
    """Generate a Persian text summary of the last 7 days."""
    today = today or date.today()
    start = today - timedelta(days=6)
    last7 = analytics.last_7_days_minutes(today)
    total = sum(m for _, m in last7)
    tests_7d = sum(t for _, t in analytics.last_7_days_tests(today))
    dq = analytics.data_quality((start, today))
    streak = streaks.current_streak(today)
    longest = streaks.longest_streak()

    # Subject breakdown
    subject_rows = analytics.time_by_activity(start, today)
    subject_lines = []
    for row in subject_rows[:8]:
        name = row.get("activity_name", "سایر")
        minutes = int(row.get("minutes", 0) or 0)
        pct = round(100 * minutes / total) if total > 0 else 0
        subject_lines.append(f"  • {name}: {to_fa_digits(minutes)} دقیقه ({to_fa_digits(pct)}٪)")

    # Test quality
    test_stats = analytics.test_quality(start, today)
    test_lines = []
    if test_stats.get("tests", 0) > 0:
        correct = test_stats.get("correct", 0)
        wrong = test_stats.get("wrong", 0)
        blank = test_stats.get("blank", 0)
        acc = test_stats.get("accuracy_percent")
        test_lines = [
            "",
            "کیفیت تست:",
            f"  • کل: {to_fa_digits(test_stats['tests'])}",
            f"  • درست: {to_fa_digits(correct)}",
            f"  • غلط: {to_fa_digits(wrong)}",
            f"  • نزده: {to_fa_digits(blank)}",
            f"  • دقت: {to_fa_digits(acc) + '٪' if acc is not None else '—'}",
        ]

    # Exam info
    exams = models.list_exams()
    exam_lines = []
    if exams:
        last_exam = exams[-1]
        exam_lines = [
            "",
            "آخرین آزمون:",
            f"  • شماره: {to_fa_digits(last_exam.exam_number)}",
            f"  • تراز: {to_fa_digits(last_exam.taraz)}",
        ]
        if last_exam.rank:
            exam_lines.append(f"  • رتبه: {to_fa_digits(last_exam.rank)}")

    lines = [
        f"گزارش هفتگی — {_jalali(start)} تا {_jalali(today)}",
        f"",
        f"مجموع مطالعه: {to_fa_digits(total)} دقیقه",
        f"تست‌ها: {to_fa_digits(tests_7d)}",
        f"کیفیت ثبت: {to_fa_digits(dq)}٪",
        f"روزهای فعال: {to_fa_digits(sum(1 for _, m in last7 if m > 0))} از ۷",
        f"رکورد فعلی: {to_fa_digits(streak)} روز",
        f"طولانی‌ترین رکورد: {to_fa_digits(longest)} روز",
        f"",
        "سهم هر درس:",
    ] + subject_lines + test_lines + exam_lines

    content = "\n".join(lines)
    _save_report("weekly", start, today, content)
    return content


def generate_monthly_report(today: Optional[date] = None) -> str:
    """Generate a Persian text summary of the last 30 days."""
    today = today or date.today()
    start = today - timedelta(days=29)

    sessions = models.list_sessions_in_range(start.isoformat(), today.isoformat())
    total_minutes = sum(s.minutes for s in sessions)
    total_tests = sum(s.tests_count for s in sessions)
    active_days = len({s.date for s in sessions})
    dq = analytics.data_quality((start, today))
    streak = streaks.current_streak(today)
    longest = streaks.longest_streak()

    # Subject breakdown
    subject_rows = analytics.time_by_activity(start, today)
    subject_lines = []
    for row in subject_rows[:10]:
        name = row.get("activity_name", "سایر")
        minutes = int(row.get("minutes", 0) or 0)
        pct = round(100 * minutes / total_minutes) if total_minutes > 0 else 0
        subject_lines.append(f"  • {name}: {to_fa_digits(minutes)} دقیقه ({to_fa_digits(pct)}٪)")

    # Exams in this period
    exams = [e for e in models.list_exams()
             if start.isoformat() <= e.date <= today.isoformat()]
    exam_lines = []
    if exams:
        exam_lines = ["", f"آزمون‌های این ماه: {to_fa_digits(len(exams))}"]
        for e in exams:
            exam_lines.append(
                f"  • آزمون {to_fa_digits(e.exam_number)}: تراز {to_fa_digits(e.taraz)}"
            )

    lines = [
        f"گزارش ماهانه — {_jalali(start)} تا {_jalali(today)}",
        f"",
        f"مجموع مطالعه: {to_fa_digits(total_minutes)} دقیقه",
        f"میانگین روزانه: {to_fa_digits(total_minutes // 30)} دقیقه",
        f"تست‌ها: {to_fa_digits(total_tests)}",
        f"روزهای فعال: {to_fa_digits(active_days)} از ۳۰",
        f"کیفیت ثبت: {to_fa_digits(dq)}٪",
        f"رکورد فعلی: {to_fa_digits(streak)} روز",
        f"طولانی‌ترین رکورد: {to_fa_digits(longest)} روز",
        f"",
        "سهم هر درس:",
    ] + subject_lines + exam_lines

    content = "\n".join(lines)
    _save_report("monthly", start, today, content)
    return content


def list_reports(limit: int = 20) -> list:
    """List recent reports from the database."""
    return models.list_reports(limit)


def _save_report(report_type: str, start: date, end: date, content: str) -> None:
    """Save a report to the database."""
    models.save_report(report_type, start.isoformat(), end.isoformat(), content)


def _jalali(d: date) -> str:
    """Format a date as a Jalali label."""
    try:
        return jalali_label(d.isoformat())
    except Exception:
        return d.isoformat()
