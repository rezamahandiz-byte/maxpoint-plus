"""CSV export module — export sessions, exams, and reports to CSV.

This module provides functions to export data from the local SQLite
database to CSV format. The CSV can be opened in Excel, Google Sheets,
or any spreadsheet application.

Exports:
  - sessions_csv: all study sessions with subject names
  - exams_csv: all exams with subject details
  - tests_csv: all test results from sessions
  - goals_csv: all goals
  - full_csv: a combined export of everything

Each function returns a string (the CSV content). The caller is
responsible for writing it to a file.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Optional

from core import db, models


def _csv_writer() -> tuple[io.StringIO, csv.writer]:
    """Create a CSV writer with UTF-8 BOM (for Excel compatibility)."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM for Excel
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    return output, writer


def sessions_csv(start: Optional[str] = None, end: Optional[str] = None) -> str:
    """Export all sessions (or a date range) to CSV.

    Args:
        start: ISO date string (inclusive), or None for all
        end: ISO date string (inclusive), or None for all

    Returns:
        CSV string with BOM for Excel.
    """
    output, writer = _csv_writer()
    writer.writerow([
        "تاریخ", "درس", "گروه", "دقیقه", "تعداد تست",
        "درست", "غلط", "نزده", "موضوع", "نوع", "یادداشت",
        "ساعت شروع", "ساعت پایان", "زمان ثبت",
    ])

    if start and end:
        sessions = models.list_sessions_in_range(start, end)
    else:
        # Get all sessions
        rows = db.fetch_all("SELECT * FROM sessions ORDER BY date DESC, id DESC;")
        sessions = [models._row_to(models.Session, r) for r in rows]

    activities = {a.id: a for a in models.list_activities(active_only=False)}
    groups = {g.id: g for g in models.list_groups()}

    for s in sessions:
        act = activities.get(s.activity_id)
        group = groups.get(act.group_id) if act and act.group_id else None
        writer.writerow([
            s.date,
            act.name if act else "—",
            group.name if group else "—",
            s.minutes,
            s.tests_count,
            getattr(s, "correct_count", 0) or 0,
            getattr(s, "wrong_count", 0) or 0,
            getattr(s, "blank_count", 0) or 0,
            getattr(s, "topic", "") or "",
            getattr(s, "test_type", "") or "",
            s.note or "",
            s.start_time or "",
            s.end_time or "",
            s.created_at or "",
        ])

    return output.getvalue()


def exams_csv() -> str:
    """Export all exams with subject details to CSV."""
    output, writer = _csv_writer()
    writer.writerow([
        "شماره آزمون", "تاریخ", "تراز", "رتبه",
        "درس", "درصد", "درست", "غلط", "نزده", "یادداشت",
    ])

    exams = models.list_exams()
    for exam in exams:
        subjects = models.list_exam_subjects(exam.id)
        if subjects:
            for sub in subjects:
                writer.writerow([
                    exam.exam_number,
                    exam.date,
                    exam.taraz,
                    exam.rank or "",
                    sub.subject,
                    sub.percent if sub.percent is not None else "",
                    sub.correct if sub.correct is not None else "",
                    sub.wrong if sub.wrong is not None else "",
                    sub.blank if sub.blank is not None else "",
                    exam.notes or "",
                ])
        else:
            writer.writerow([
                exam.exam_number, exam.date, exam.taraz,
                exam.rank or "", "", "", "", "", "", exam.notes or "",
            ])

    return output.getvalue()


def tests_csv(start: Optional[str] = None, end: Optional[str] = None) -> str:
    """Export all test results from sessions to CSV."""
    output, writer = _csv_writer()
    writer.writerow([
        "تاریخ", "درس", "کل تست", "درست", "غلط", "نزده", "دقت", "زمان ثبت",
    ])

    if not start:
        start = (date.today() - timedelta(days=365)).isoformat()
    if not end:
        end = date.today().isoformat()

    sessions = models.list_sessions_in_range(start, end)
    activities = {a.id: a for a in models.list_activities(active_only=False)}

    for s in sessions:
        if s.tests_count == 0:
            continue
        act = activities.get(s.activity_id)
        correct = int(getattr(s, "correct_count", 0) or 0)
        wrong = int(getattr(s, "wrong_count", 0) or 0)
        accuracy = round(100 * correct / (correct + wrong)) if (correct + wrong) > 0 else None
        writer.writerow([
            s.date,
            act.name if act else "—",
            s.tests_count,
            correct,
            wrong,
            int(getattr(s, "blank_count", 0) or 0),
            f"{accuracy}%" if accuracy is not None else "",
            s.created_at or "",
        ])

    return output.getvalue()


def goals_csv() -> str:
    """Export all goals to CSV."""
    output, writer = _csv_writer()
    writer.writerow(["درس", "دوره", "هدف دقیقه", "هدف تست"])

    goals = models.list_goals()
    activities = {a.id: a for a in models.list_activities(active_only=False)}

    for g in goals:
        act = activities.get(g.activity_id)
        writer.writerow([
            act.name if act else "—",
            g.period,
            g.target_minutes,
            g.target_tests,
        ])

    return output.getvalue()


def full_csv() -> str:
    """Export everything as a combined CSV (multiple sections)."""
    output = io.StringIO()
    output.write("\ufeff")

    output.write("=== جلسات مطالعه ===\n")
    output.write(sessions_csv())

    output.write("\n=== آزمون‌ها ===\n")
    output.write(exams_csv())

    output.write("\n=== تست‌ها ===\n")
    output.write(tests_csv())

    output.write("\n=== اهداف ===\n")
    output.write(goals_csv())

    return output.getvalue()


def export_to_file(path: str, content: str) -> None:
    """Write CSV content to a file."""
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
