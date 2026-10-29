"""Headless regression tests for MAXPOINT Plus v0.6 core logic.

Run from the project root:
    python scripts/v05_smoke.py
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
    with tempfile.TemporaryDirectory(prefix="maxpoint-v06-") as tmp:
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

        # The notifier workflow is tested with a fake native bridge; this does not
        # claim real Android alarms or sound have been tested on a device.
        from services import notifier
        class FakeNotifier:
            def __init__(self):
                self.cancelled = []
                self.scheduled = []
                self.channels = []
                self.shown = []
            async def cancel(self, notification_id): self.cancelled.append(notification_id)
            async def request_permissions(self): return True
            async def create_notification_channel(self, **kwargs): self.channels.append(kwargs)
            async def schedule_notification(self, **kwargs): self.scheduled.append(kwargs)
            async def show_notification(self, **kwargs): self.shown.append(kwargs)
        fake = FakeNotifier()
        ok, message = asyncio.run(notifier.configure_reminders(
            fake, True, 60, 9, 12, weekdays=[5]
        ))
        assert ok and len(fake.scheduled) == 4, (ok, message, fake.scheduled)
        assert all(x["sound"] == notifier.SOUND_RESOURCE for x in fake.scheduled)
        fixed_slots = [x for x in fake.scheduled if x.get("match_date_time_components")]
        assert len(fixed_slots) == 3
        assert all(x["match_date_time_components"] == "day_of_week_and_time" for x in fixed_slots)
        prompt = next(x for x in fake.scheduled if x.get("payload") == "maxpoint_focus_prompt")
        assert prompt["title"] == "درس می‌خونی؟"
        assert prompt["actions"] == [{"id": "focus_yes", "title": "آره"}, {"id": "focus_no", "title": "نه"}]
        assert prompt["scheduled_time"].weekday() == 5
        ok, _ = asyncio.run(notifier.show_test_notification(fake))
        assert ok and fake.shown and fake.channels

        # The dedicated notification center's advanced choices must translate
        # into the scheduled Android alarms (mocked bridge; no real device claim).
        fake_custom = FakeNotifier()
        ok, message = asyncio.run(notifier.configure_reminders(
            fake_custom, True, 60, 9, 12,
            ["study", "review"], sound_enabled=False, vibration_enabled=False,
            weekdays=[4, 5], sound_mode="system",
        ))
        assert ok and len(fake_custom.scheduled) == 3, (ok, message, fake_custom.scheduled)
        assert all(item["play_sound"] is False and item["enable_vibration"] is False
                   and item["sound"] is None for item in fake_custom.scheduled)
        assert all(item["channel_id"].startswith("maxpoint_focus_silent_steady") for item in fake_custom.scheduled)
        assert {item["scheduled_time"].weekday() for item in fake_custom.scheduled} == {4, 5}
        assert len({item["notification_id"] for item in fake_custom.scheduled}) == 3
        assert any(item["notification_id"] == notifier._REVIEW_ID_BASE + 4
                   and item["title"] == notifier.MESSAGES["review"][0]
                   for item in fake_custom.scheduled)

        # The selected message tone changes actual scheduled copy, not just UI.
        fake_tone = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_tone, True, 60, 9, 10, ["study"], weekdays=[0],
            message_tone="minimal",
        ))
        assert ok and fake_tone.scheduled[0]["title"] == "درس می‌خونی؟"
        assert fake_tone.scheduled[0]["body"] == "یک بازه‌ی ۱۵ دقیقه‌ای شروع کن."
        assert fake_tone.scheduled[0]["actions"][0]["id"] == "focus_yes"

        # A response to the focus prompt changes the next reminder interval.
        models.set_setting("reminders_enabled", "1")
        models.set_setting("reminder_kind_study", "1")
        models.set_setting("reminder_start", "8")
        models.set_setting("reminder_end", "22")
        models.set_setting("reminder_weekdays", "0,1,2,3,4,5,6")
        models.set_setting("quiet_hours_enabled", "1")
        models.set_setting("quiet_start_hour", "22")
        models.set_setting("quiet_end_hour", "8")
        models.set_setting("reminder_sound", "1")
        models.set_setting("reminder_vibration", "1")
        models.set_setting("reminder_sound_mode", "custom")
        models.set_setting("reminder_tone", "calm")
        fake_yes = FakeNotifier()
        ok, message = asyncio.run(notifier.handle_focus_prompt_action(fake_yes, "focus_yes"))
        assert ok and fake_yes.scheduled and fake_yes.scheduled[0]["payload"] == "maxpoint_focus_prompt"
        assert fake_yes.scheduled[0]["scheduled_time"].hour >= 8 and fake_yes.scheduled[0]["scheduled_time"].hour < 22
        fake_no = FakeNotifier()
        ok, message = asyncio.run(notifier.handle_focus_prompt_action(fake_no, "focus_no"))
        assert ok and fake_no.scheduled and fake_no.scheduled[0]["actions"][1]["id"] == "focus_no"

        # The explicit overnight quiet window must not schedule regular reminders.
        fake_quiet = FakeNotifier()
        ok, message = asyncio.run(notifier.configure_reminders(
            fake_quiet, True, 60, 8, 22, ["study", "break"], weekdays=[0],
            quiet_hours_enabled=True, quiet_start_hour=22, quiet_end_hour=8,
        ))
        assert ok, message
        assert all(not (x["scheduled_time"].hour >= 22 or x["scheduled_time"].hour < 8) for x in fake_quiet.scheduled)

        # System sound stays enabled without referencing the bundled WAV resource.
        fake_system_sound = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_system_sound, True, 60, 9, 10, ["study"], weekdays=[0],
            sound_enabled=True, vibration_enabled=True, sound_mode="system",
        ))
        assert ok and len(fake_system_sound.scheduled) == 1
        assert fake_system_sound.scheduled[0]["play_sound"] is True
        assert fake_system_sound.scheduled[0]["sound"] is None
        assert "system" in fake_system_sound.scheduled[0]["channel_id"]

        # Review-only schedules are valid and should not index an empty rotation list.
        fake_review = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_review, True, 60, 9, 12, ["review"], weekdays=[0, 6]
        ))
        assert ok and len(fake_review.scheduled) == 2
        assert all(item["title"] == notifier.MESSAGES["review"][0] for item in fake_review.scheduled)

        # An exact-alarm permission prompt can upgrade scheduling; denial of the
        # ordinary notifications permission must preserve previously set alarms.
        class FakeExactNotifier(FakeNotifier):
            def __init__(self, exact=False, notifications=True):
                super().__init__()
                self.exact = exact
                self.notifications_allowed = notifications
                self.exact_requests = 0
            async def request_permissions(self): return self.notifications_allowed
            async def are_notifications_enabled(self): return self.notifications_allowed
            async def can_schedule_exact_notifications(self): return self.exact
            async def request_exact_alarm_permission(self):
                self.exact_requests += 1
                self.exact = True
                return True

        fake_exact = FakeExactNotifier()
        ok, message = asyncio.run(notifier.configure_reminders(
            fake_exact, True, 60, 9, 10, ["study"], exact_enabled=True,
            request_exact_permission=True, weekdays=[0],
        ))
        assert ok and fake_exact.exact_requests == 1
        assert fake_exact.scheduled and all(x["schedule_mode"] == "exact_allow_while_idle" for x in fake_exact.scheduled)

        fake_denied = FakeExactNotifier(notifications=False)
        fake_denied.scheduled.append({"notification_id": 4100, "title": "existing"})
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_denied, True, 60, 9, 12, ["study"], weekdays=[5]
        ))
        assert not ok and not fake_denied.cancelled and len(fake_denied.scheduled) == 1

        fake_empty = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_empty, True, 60, 9, 12, [], True, True
        ))
        assert not ok and not fake_empty.scheduled and not fake_empty.cancelled

        fake_restore_denied = FakeExactNotifier(notifications=False)
        fake_restore_denied.scheduled.append({"notification_id": 4100, "title": "existing"})
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_restore_denied, True, 60, 9, 12, ["study"], weekdays=[5],
            prompt_for_notification_permission=False,
        ))
        assert not ok and not fake_restore_denied.cancelled and len(fake_restore_denied.scheduled) == 1

        # Turning reminders off must still work even if the user previously
        # cleared every weekday; empty days are invalid only for active plans.
        fake_disable_empty = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_disable_empty, False, weekdays=[]
        ))
        assert ok and fake_disable_empty.cancelled

        # Invalid weekday/sound combinations must fail before touching pending alarms.
        fake_invalid = FakeNotifier()
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_invalid, True, 60, 9, 12, ["study"], weekdays=[7]
        ))
        assert not ok and not fake_invalid.cancelled
        ok, _ = asyncio.run(notifier.configure_reminders(
            fake_invalid, True, 60, 9, 12, ["study"], weekdays=[5], sound_mode="broken"
        ))
        assert not ok and not fake_invalid.cancelled

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
    print("MAXPOINT v0.6 regression: PASS (fresh DB, v1 migration, sessions and answer-count validation, overlaps, goals, analytics, exams, Jalali dates, local report, backup round-trip and rollback, mocked GPT request, online clock validation and offline fallback, weekly weekday-specific notification scheduling, Yes/No focus prompt snoozes, overnight quiet hours, review-only schedules, custom/system sound, vibration, three message tones, exact-alarm permission flow, permission-denial preservation and empty-category validation)")


if __name__ == "__main__":
    main()
