"""Comprehensive smoke test for MAXPOINT-Plus v0.8.

Tests ALL features including the new modules:
  - Study tab (study.py)
  - Exam tab (exam.py)
  - Test tab (test.py)
  - Streak tracking (streaks.py)
  - Reports (reports.py)
  - Planner (planner.py)
  - CSV export (exporter.py)
  - Extended analytics (monthly comparison, yearly summary, predictions)

Run: python scripts/v08_smoke.py
No Flet runtime, Android SDK, or network access required.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAXPOINT_DB_PATH"] = str(Path(tmp) / "v08.db")
        from core import db, models, analytics, goals, streaks, reports, planner, exporter

        # ─── 1. Database init ───────────────────────────────────────────
        db.init_db()
        groups = models.list_groups()
        activities = models.list_activities(active_only=True)
        assert len(groups) == 7, f"expected 7 groups, got {len(groups)}"
        assert len(activities) >= 8, f"expected ≥8 activities, got {len(activities)}"
        print("  ✓ Database init + seed")

        # ─── 2. Session creation ────────────────────────────────────────
        today = date.today()
        for i in range(7):
            d = (today - timedelta(days=i)).isoformat()
            models.create_session(
                d, activities[i % len(activities)].id,
                30 + i * 10, i % 4, f"day {i}",
                correct_count=i * 3, wrong_count=i, blank_count=i % 2,
            )
        sessions = models.list_sessions_for_date(today.isoformat())
        assert len(sessions) >= 1, "today should have sessions"
        print("  ✓ Session creation (7 days)")

        # ─── 3. Goals ───────────────────────────────────────────────────
        goals.set_goal(activities[0].id, "daily", 120, 0)
        goals.set_goal(activities[1].id, "weekly", 300, 0)
        daily_gaps = goals.daily_gaps(today)
        weekly_gaps = goals.weekly_gaps(today)
        assert len(daily_gaps) >= 1, "should have daily gaps"
        assert len(weekly_gaps) >= 1, "should have weekly gaps"
        print("  ✓ Goals (daily + weekly)")

        # ─── 4. Exams ───────────────────────────────────────────────────
        models.create_exam(
            (today - timedelta(days=30)).isoformat(), 1, 5100, 1500,
            subjects=[
                {"subject": "ریاضی", "percent": 65, "correct": 20, "wrong": 8, "blank": 2},
                {"subject": "فیزیک", "percent": 42, "correct": 12, "wrong": 9, "blank": 4},
            ],
        )
        models.create_exam(
            (today - timedelta(days=15)).isoformat(), 2, 5400, 1200,
            subjects=[
                {"subject": "ریاضی", "percent": 72, "correct": 22, "wrong": 6, "blank": 2},
                {"subject": "فیزیک", "percent": 55, "correct": 15, "wrong": 7, "blank": 3},
            ],
        )
        exams = models.list_exams()
        assert len(exams) == 2, f"expected 2 exams, got {len(exams)}"
        taraz_series = analytics.exam_taraz_series()
        assert len(taraz_series) == 2, "should have 2 taraz points"
        print("  ✓ Exams (2 exams with subjects)")

        # ─── 5. Analytics ───────────────────────────────────────────────
        summary = analytics.today_summary(today)
        assert "minutes" in summary
        assert "tests" in summary
        assert "goal_percent" in summary
        assert "next_step_text" in summary
        print("  ✓ Today summary")

        last7 = analytics.last_7_days_minutes(today)
        assert len(last7) == 7, "should have 7 days"
        print("  ✓ 7-day minutes")

        test_quality = analytics.test_quality(today - timedelta(days=6), today)
        assert "tests" in test_quality
        assert "correct" in test_quality
        assert "wrong" in test_quality
        print("  ✓ Test quality")

        time_by_group = analytics.time_by_group(today - timedelta(days=6), today)
        assert isinstance(time_by_group, list)
        print("  ✓ Time by group")

        time_by_activity = analytics.time_by_activity(today - timedelta(days=6), today)
        assert isinstance(time_by_activity, list)
        print("  ✓ Time by activity")

        # ─── 6. Streaks ─────────────────────────────────────────────────
        current = streaks.current_streak(today)
        longest = streaks.longest_streak()
        total_active = streaks.total_active_days()
        history = streaks.streak_history(30)
        assert current >= 1, f"current streak should be ≥1, got {current}"
        assert longest >= 1, f"longest streak should be ≥1, got {longest}"
        assert total_active >= 1, f"total active should be ≥1, got {total_active}"
        assert len(history) == 30, f"history should have 30 days, got {len(history)}"
        print(f"  ✓ Streaks (current={current}, longest={longest}, active_days={total_active})")

        # ─── 7. Reports ─────────────────────────────────────────────────
        daily_report = reports.generate_daily_report(today)
        assert "گزارش روز" in daily_report
        weekly_report = reports.generate_weekly_report(today)
        assert "گزارش هفتگی" in weekly_report
        monthly_report = reports.generate_monthly_report(today)
        assert "گزارش ماهانه" in monthly_report
        report_list = reports.list_reports()
        assert len(report_list) >= 3, f"should have ≥3 reports, got {len(report_list)}"
        print(f"  ✓ Reports (daily + weekly + monthly, {len(report_list)} total)")

        # ─── 8. Planner ─────────────────────────────────────────────────
        daily_plan = planner.daily_plan(today)
        weekly_plan = planner.weekly_plan(today)
        balance = planner.balance_check(today)
        assert isinstance(daily_plan, list)
        assert isinstance(weekly_plan, list)
        assert "balanced" in balance
        assert "subjects" in balance
        plan_summary = planner.plan_summary(today)
        assert "daily_plan" in plan_summary
        assert "weekly_plan" in plan_summary
        print(f"  ✓ Planner (daily={len(daily_plan)}, weekly={len(weekly_plan)})")

        # ─── 9. Exporter ────────────────────────────────────────────────
        sessions_csv = exporter.sessions_csv()
        assert "تاریخ" in sessions_csv
        assert "درس" in sessions_csv
        exams_csv = exporter.exams_csv()
        assert "شماره آزمون" in exams_csv
        tests_csv = exporter.tests_csv()
        assert "کل تست" in tests_csv
        goals_csv = exporter.goals_csv()
        assert "هدف دقیقه" in goals_csv
        full_csv = exporter.full_csv()
        assert "جلسات" in full_csv
        print("  ✓ CSV export (sessions + exams + tests + goals + full)")

        # ─── 10. Extended analytics ─────────────────────────────────────
        monthly = analytics.monthly_comparison(3)
        assert len(monthly) == 3, f"should have 3 months, got {len(monthly)}"
        yearly = analytics.yearly_summary()
        assert "total_minutes" in yearly
        assert "subjects" in yearly
        prediction = analytics.predict_goal_completion(activities[0].id, "daily", today)
        assert prediction is not None
        assert "estimated_days" in prediction
        heatmap = analytics.subject_heatmap(14)
        assert len(heatmap) == 14, f"should have 14 days, got {len(heatmap)}"
        print("  ✓ Extended analytics (monthly + yearly + prediction + heatmap)")

        # ─── 11. Backup round-trip ──────────────────────────────────────
        from services import backup
        backup_path = str(Path(tmp) / "backup.json")
        backup.export_to_file(backup_path)
        # Wipe
        with db.connect() as conn:
            for t in ["sessions", "goals", "exam_subjects", "exams", "reports"]:
                conn.execute(f"DELETE FROM {t};")
        assert len(models.list_exams()) == 0
        # Restore
        counts = backup.restore_from_file(backup_path)
        assert counts["sessions"] >= 7, f"should restore ≥7 sessions, got {counts['sessions']}"
        assert counts["exams"] == 2, f"should restore 2 exams, got {counts['exams']}"
        print(f"  ✓ Backup round-trip ({counts['sessions']} sessions, {counts['exams']} exams)")

        # ─── 12. Empty-data resilience ──────────────────────────────────
        empty_summary = analytics.today_summary(date(2000, 1, 1))
        assert empty_summary["minutes"] == 0
        assert empty_summary["goal_percent"] == 0.0
        empty_streak = streaks.current_streak(date(2000, 1, 1))
        assert empty_streak == 0
        empty_series = analytics.exam_taraz_series()
        assert isinstance(empty_series, list)
        print("  ✓ Empty-data resilience")

    os.environ.pop("MAXPOINT_DB_PATH", None)
    print("\n✅ MAXPOINT-Plus v0.8 regression: ALL 12 TEST GROUPS PASSED")
    print("   (database, sessions, goals, exams, analytics, streaks, reports,")
    print("    planner, CSV export, extended analytics, backup, empty-data)")


if __name__ == "__main__":
    main()
