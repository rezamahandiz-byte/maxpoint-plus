"""Headless regression tests for MAXPOINT Plus v0.7 merged core logic.

Run from the project root:
    python scripts/v07_smoke.py
No Flet runtime, Android SDK, or network access is required.
"""
from __future__ import annotations

import asyncio
import copy
import os
import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _old_v1_database(path: Path) -> None:
    """Create a representative v1 database with one saved session and exam."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE activity_groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL, color TEXT, priority TEXT NOT NULL CHECK(priority IN ('mandatory','priority','flexible')));
        CREATE TABLE activities (id INTEGER PRIMARY KEY, name TEXT NOT NULL, group_id INTEGER, color TEXT, icon TEXT, is_custom INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(group_id) REFERENCES activity_groups(id));
        CREATE TABLE sessions (id INTEGER PRIMARY KEY, date TEXT NOT NULL, start_time TEXT, end_time TEXT, activity_id INTEGER NOT NULL, minutes INTEGER NOT NULL DEFAULT 0, tests_count INTEGER NOT NULL DEFAULT 0, note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(activity_id) REFERENCES activities(id));
        CREATE TABLE goals (id INTEGER PRIMARY KEY, activity_id INTEGER NOT NULL, period TEXT NOT NULL CHECK(period IN ('daily','weekly')), target_minutes INTEGER NOT NULL DEFAULT 0, target_tests INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(activity_id) REFERENCES activities(id));
        CREATE TABLE exams (id INTEGER PRIMARY KEY, date TEXT NOT NULL, exam_number INTEGER NOT NULL, taraz INTEGER NOT NULL, notes TEXT);
        CREATE TABLE exam_subjects (id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL, subject TEXT NOT NULL, percent REAL, correct INTEGER, wrong INTEGER, blank INTEGER, FOREIGN KEY(exam_id) REFERENCES exams(id));
        CREATE TABLE reports (id INTEGER PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('daily','weekly','monthly')), period_start TEXT NOT NULL, period_end TEXT NOT NULL, content TEXT NOT NULL, generated_at TEXT NOT NULL);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE INDEX idx_sessions_date ON sessions(date);
        CREATE INDEX idx_sessions_activity ON sessions(activity_id);
        CREATE INDEX idx_goals_activity ON goals(activity_id);
        CREATE INDEX idx_exam_subjects_exam ON exam_subjects(exam_id);
        INSERT INTO activity_groups VALUES(1,'مطالعه','#7E8CE0','mandatory');
        INSERT INTO activities VALUES(1,'ریاضی',1,'#7E8CE0',NULL,0,1);
        INSERT INTO sessions VALUES(11,'2026-10-27','09:00','09:40',1,40,5,'داده‌ی قبلی','2026-10-27T10:00:00');
        INSERT INTO exams VALUES(21,'2026-10-25',3,5900,'آزمون قبلی');
        PRAGMA user_version=1;
        """)
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maxpoint-v07-") as tmp:
        tmp_path = Path(tmp)
        fresh_path = tmp_path / "fresh.db"
        os.environ["MAXPOINT_DB_PATH"] = str(fresh_path)

        from core import db, models, analytics, goals
        from core.ai import build_local_report
        from core.fa_dates import ascii_digits, format_jalali, normalize_date
        from services import backup
        # Guard against the reported Flet crash and keep the live clock Persian-calendar aware.
        home_source = (ROOT / "src" / "ui" / "home.py").read_text(encoding="utf-8")
        main_source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
        assert "ft.Expanded" not in home_source + main_source
        assert "jalali_label(now.date().isoformat())" in home_source
        assert "jalali_label(now.date().isoformat())" in main_source

        db.init_db()
        assert db.fetch_one("PRAGMA user_version;")[0] == 2

        # Online clock validation and offline recovery are tested without real
        # network traffic. The offline pass must not erase the last usable offset.
        from services import clock_sync
        import httpx
        from email.utils import format_datetime
        from datetime import datetime as _datetime, timedelta as _timedelta, timezone as _timezone
        server_now = _datetime.now(_timezone.utc) + _timedelta(seconds=120)
        class FakeClockResponse:
            headers = {"date": format_datetime(server_now, usegmt=True)}
        clock_mode = {"offline": False}
        class FakeClockClient:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get(self, url):
                if clock_mode["offline"]:
                    raise OSError("simulated offline")
                return FakeClockResponse()
        real_http_client = httpx.AsyncClient
        httpx.AsyncClient = FakeClockClient
        try:
            assert asyncio.run(clock_sync.sync_once()) is True
            online_offset = float(models.get_setting(clock_sync.OFFSET_KEY, "0"))
            assert 117 <= online_offset <= 121, online_offset
            assert models.get_setting(clock_sync.STATUS_KEY) == "online"
            clock_mode["offline"] = True
            assert asyncio.run(clock_sync.sync_once()) is False
            assert models.get_setting(clock_sync.STATUS_KEY) == "offline"
            assert float(models.get_setting(clock_sync.OFFSET_KEY, "0")) == online_offset
            # Even while offline, the app clock remains usable and exception-free.
            assert clock_sync.now_local().tzinfo is not None
        finally:
            httpx.AsyncClient = real_http_client
        assert models.get_setting("ai_model") == "gpt-5.4-mini"
        assert models.get_setting("reminders_enabled") == "0"
        activities = models.list_activities()
        assert activities, "default activities were not seeded"
        activity = activities[0]
        today = date.today()
        today_iso = today.isoformat()

        # Save a timed session with explicit answer outcome counts.
        session_id = models.create_session(
            today_iso, activity.id, 35, tests_count=10,
            start_time="09:00", end_time="09:35",
            correct_count=6, wrong_count=3, blank_count=1,
            topic="حد و پیوستگی", test_type="تمرینی", note="smoke",
        )
        session = models.get_session(session_id)
        assert session and session.correct_count == 6 and session.topic == "حد و پیوستگی"
        assert models.find_session_overlaps(today_iso, "09:20", "09:40")
        assert not models.find_session_overlaps(today_iso, "10:00", "10:30")
        try:
            models.create_session(today_iso, activity.id, 10, tests_count=-1)
            raise AssertionError("negative tests count should be rejected")
        except ValueError:
            pass
        # Editing answer counts cannot leave them greater than the total count.
        edit_probe = models.create_session(today_iso, activity.id, 5, tests_count=2)
        models.update_session(edit_probe, correct_count=4, wrong_count=1, blank_count=0)
        edited = models.get_session(edit_probe)
        assert edited.tests_count >= edited.correct_count + edited.wrong_count + edited.blank_count == 5
        try:
            models.update_session(edit_probe, wrong_count=-1)
            raise AssertionError("negative answer count should be rejected")
        except ValueError:
            pass

        # Goals and basic aggregates.
        models.upsert_goal(activity.id, "daily", 60, 15)
        models.upsert_goal(activity.id, "weekly", 300, 70)
        try:
            models.upsert_goal(activity.id, "daily", -1, 0)
            raise AssertionError("negative goal should be rejected")
        except ValueError:
            pass
        assert goals.goal_gap(activity.id, "daily", today).actual_minutes == 40
        week_start, week_end = goals._week_range(today)
        assert week_start.weekday() == 5 and week_end.weekday() == 4
        quality = analytics.test_quality(today, today)
        assert quality["tests"] == 15 and quality["correct"] == 10 and quality["wrong"] == 4 and quality["blank"] == 1
        assert quality["accuracy_percent"] == 71.4
        groups = analytics.time_by_group(today, today)
        assert groups and sum(row["minutes"] for row in groups) == 40

        # Exam and subject data, including rank.
        exam_id = models.create_exam(today_iso, 1, 6100, "smoke exam", 42, [
            {"subject": "ریاضی", "percent": 62.5, "correct": 10, "wrong": 4, "blank": 2}
        ])
        exam = next(x for x in models.list_exams() if x.id == exam_id)
        assert exam.rank == 42 and models.list_exam_subjects(exam_id)[0].percent == 62.5

        # Jalali and Persian-digit conversions round-trip.
        for iso in ("2000-01-01", "2024-03-20", "2025-12-31", today_iso):
            assert normalize_date(format_jalali(iso)) == iso
        assert normalize_date("۱۴۰۵-۰۸-۰۶") == "2026-10-28"
        assert ascii_digits("۱۲۳٤٥٦") == "123456"

        summary = analytics.build_aggregate_summary(7)
        assert summary["tests"] == 15 and summary["exam_count"] >= 1
        report = build_local_report(summary)
        assert "گزارش محلی MAXPOINT" in report and "دقت تست" in report

        # Backup/restore must preserve new v2 columns and data.
        backup_dict = backup.export_to_dict()
        counts_before = len(models.list_sessions_in_range(today_iso, today_iso))
        models.create_session(today_iso, activity.id, 5, note="temporary")
        backup.restore_from_dict(backup_dict)
        assert len(models.list_sessions_in_range(today_iso, today_iso)) == counts_before
        assert models.get_session(session_id).correct_count == 6
        assert models.list_exam_subjects(exam_id)[0].correct == 10

        # Invalid restores must roll back atomically instead of wiping current data.
        corrupt_backup = copy.deepcopy(backup.export_to_dict())
        if corrupt_backup["tables"]["sessions"]:
            corrupt_backup["tables"]["sessions"][0]["not_a_real_column"] = "bad"
            before_ids = [x.id for x in models.list_sessions_in_range(today_iso, today_iso)]
            try:
                backup.restore_from_dict(corrupt_backup)
                raise AssertionError("invalid backup should fail")
            except ValueError:
                pass
            after_ids = [x.id for x in models.list_sessions_in_range(today_iso, today_iso)]
            assert after_ids == before_ids, "failed backup restore was not atomic"

        # The notifier is now an in-app implementation (v0.7.1) that works
        # on all platforms without flet-android-notifications. Verify the
        # API surface is intact.
        from services import notifier
        assert notifier.init(None) is not None  # returns a truthy marker
        assert notifier.available(None) is True  # in-app always available
        ok, msg = asyncio.run(notifier.configure_reminders(None, True))
        assert ok is True and msg
        ok, msg = asyncio.run(notifier.show_test_notification(None))
        assert ok is True and msg
        ok, msg = asyncio.run(notifier.check_notification_status(None))
        assert ok is True or ok is False  # depends on enabled state
        assert msg
        ok, msg = asyncio.run(notifier.open_notification_settings(None))
        assert msg
        ok, msg = asyncio.run(notifier.handle_focus_prompt_action(None, "focus_yes"))
        assert ok is True and msg
        asyncio.run(notifier.restore_saved_settings(None))  # no-op, must not raise
        assert isinstance(notifier.MESSAGE_TONES, dict)
        assert "calm" in notifier.MESSAGE_TONES
        assert isinstance(notifier.KIND_LABELS, dict)


        # OpenAI-compatible request is tested through a mocked HTTP client only.
        import json as _json
        from core import ai
        class FakeResponse:
            def raise_for_status(self): return None
            def json(self): return {"choices": [{"message": {"content": "گزارش آزمایشی"}}]}
        class FakeClient:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def post(self, url, **kwargs):
                self.url, self.kwargs = url, kwargs
                captured["url"] = url
                captured["kwargs"] = kwargs
                return FakeResponse()
        captured = {}
        original_client = ai.httpx.AsyncClient
        ai.httpx.AsyncClient = FakeClient
        try:
            got = asyncio.run(ai.request_report("weekly", {"tests": 10, "minutes": 120}, "test-key"))
            assert got == "گزارش آزمایشی"
            req = captured["kwargs"]
            assert req["headers"]["Authorization"] == "Bearer test-key"
            sent = _json.dumps(req["json"], ensure_ascii=False)
            assert "note" not in sent and "raw_session" not in sent
            assert req["json"]["max_completion_tokens"] == 1100
        finally:
            ai.httpx.AsyncClient = original_client
        try:
            asyncio.run(ai.request_report("weekly", {}, "k", "http://remote.example/api"))
            raise AssertionError("plain HTTP remote endpoint should be rejected")
        except ValueError:
            pass

        # Persistent study timer: start/test-count/pause/resume/finish survives
        # widget rebuilds and excludes the pause interval from recorded duration.
        from core import study_session
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        fixed_start = _dt(2026, 10, 28, 9, 0, tzinfo=_tz.utc)
        active = study_session.start(activity.id, activity.name, "test", "تایمر رگرسیون", fixed_start)
        assert active.activity_id == activity.id and active.kind == "test"
        assert study_session.set_test_count("۱۲") == 12
        assert study_session.get_active().elapsed_seconds(fixed_start + _td(minutes=5)) == 300
        assert study_session.pause(fixed_start + _td(minutes=5))
        paused = study_session.get_active()
        assert paused and paused.is_paused
        assert paused.elapsed_seconds(fixed_start + _td(minutes=9)) == 300
        assert study_session.resume(fixed_start + _td(minutes=10))
        resumed = study_session.get_active()
        assert resumed and not resumed.is_paused
        assert resumed.elapsed_seconds(fixed_start + _td(minutes=15)) == 600
        finished = study_session.finish(fixed_start + _td(minutes=15))
        assert finished and finished.minutes == 10 and finished.tests_count == 12
        saved_timer = models.get_session(finished.session_id)
        assert saved_timer and saved_timer.test_type == "تست‌زنی"
        assert saved_timer.topic == "تایمر رگرسیون" and saved_timer.tests_count == 12
        assert study_session.get_active() is None

        # Fast start/stop within one wall-clock minute should still save a valid
        # one-minute entry rather than failing identical start/end validation.
        quick = study_session.start(activity.id, activity.name, "study", "", fixed_start)
        quick_result = study_session.finish(fixed_start + _td(seconds=20))
        assert quick_result and quick_result.minutes == 1
        quick_saved = models.get_session(quick_result.session_id)
        assert quick_saved and quick_saved.start_time != quick_saved.end_time

        # Cancelling a study session removes timer metadata without logging it.
        study_session.start(activity.id, activity.name, "study", "", fixed_start)
        assert study_session.cancel() and study_session.get_active() is None

        # The app must not use the unsupported ft.Expanded API anywhere in source.
        all_python = "\n".join(
            p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py")
        )
        assert "ft.Expanded" not in all_python
        home_source = (ROOT / "src" / "ui" / "home.py").read_text(encoding="utf-8")
        assert "شروع یک جلسه" in home_source and "مکث" in home_source
        assert "responsive_dialog_width" in home_source
        ui_import = home_source.split("from ui import (", 1)[1].split(")", 1)[0]
        assert "text_button" in ui_import, "home.py uses text_button in dialogs; it must be imported"

        # A realistic v1 DB must upgrade in place without losing rows.
        old_path = tmp_path / "v1.db"
        _old_v1_database(old_path)
        os.environ["MAXPOINT_DB_PATH"] = str(old_path)
        db.init_db()
        old_session = models.get_session(11)
        assert old_session and old_session.minutes == 40 and old_session.correct_count == 0
        old_exam = next(e for e in models.list_exams() if e.id == 21)
        assert old_exam.taraz == 5900 and old_exam.rank is None
        assert models.get_setting("ai_model") == "gpt-5.4-mini"
        assert db.fetch_one("PRAGMA user_version;")[0] == 2

    os.environ.pop("MAXPOINT_DB_PATH", None)
    print("MAXPOINT Plus v0.7 regression: PASS (fresh DB, v1 migration, sessions and answer-count validation, overlaps, goals, analytics, exams, Jalali dates, local report, backup round-trip and rollback, mocked GPT request, online clock validation and offline fallback, notifier stub API surface, persistent study timer/pause-resume, quick-session save, and Expanded API regression guard)")


if __name__ == "__main__":
    main()
