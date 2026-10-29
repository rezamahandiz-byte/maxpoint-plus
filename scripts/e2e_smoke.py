"""End-to-end smoke test: record a session, verify it shows in Home + bar chart.

This mirrors the acceptance criterion:
    "A study session can be recorded and immediately appears in Home and
     in the 7-day bar chart."
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
DB = "/tmp/mp_e2e_test.db"
if os.path.exists(DB):
    os.remove(DB)
os.environ["MAXPOINT_DB_PATH"] = DB

from core import db, models, analytics, goals


def main():
    db.init_db()
    today = date.today()

    # 1. Pick a subject (ریاضی)
    acts = models.list_activities(active_only=True)
    math = next(a for a in acts if a.name == "ریاضی")
    print(f"using activity: {math.name} (id={math.id})")

    # 2. Set a daily goal so goal_percent is meaningful
    goals.set_goal(math.id, "daily", 120, 0)
    print("set daily goal: 120 minutes")

    # 3. Record two sessions today
    sid1 = models.create_session(today.isoformat(), math.id, 25, 0, "morning")
    sid2 = models.create_session(today.isoformat(), math.id, 35, 1, "afternoon")
    print(f"recorded sessions: {sid1}, {sid2}")

    # 4. Verify today_summary reflects them
    s = analytics.today_summary(today)
    print(f"today_summary: minutes={s['minutes']}, tests={s['tests']}, "
          f"goal_percent={s['goal_percent']}, sessions={s['sessions_count']}")
    assert s["minutes"] == 60, f"expected 60, got {s['minutes']}"
    assert s["tests"] == 1, f"expected 1, got {s['tests']}"
    assert s["sessions_count"] == 2, f"expected 2, got {s['sessions_count']}"

    # 5. Verify the 7-day bar chart's last entry (today) has 60 minutes
    last7 = analytics.last_7_days_minutes(today)
    today_entry = last7[-1]
    print(f"last7 last entry: {today_entry}")
    assert today_entry[1] == 60, f"expected 60 minutes today, got {today_entry[1]}"

    # 6. Force-close simulation: re-open the DB and verify data is still there
    db2_path = db.db_path()
    print(f"db at: {db2_path}")
    sessions_after = models.list_sessions_for_date(today.isoformat())
    print(f"sessions re-read from disk: {len(sessions_after)}")
    assert len(sessions_after) == 2

    # 7. Backup round-trip
    from services import backup
    import tempfile, json
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "b.json")
        backup.export_to_file(out)
        # wipe
        with db.connect() as c:
            c.execute("DELETE FROM sessions;")
        assert len(models.list_sessions_for_date(today.isoformat())) == 0
        # restore
        counts = backup.restore_from_file(out)
        assert counts["sessions"] == 2, f"restore lost sessions: {counts}"
        sessions_restored = models.list_sessions_for_date(today.isoformat())
        assert len(sessions_restored) == 2
        print(f"backup round-trip ok: {counts}")

    # 8. Edit a session
    models.update_session(sid1, minutes=45, tests_count=2)
    s_after_edit = models.get_session(sid1)
    assert s_after_edit.minutes == 45 and s_after_edit.tests_count == 2
    print(f"edit ok: session {sid1} now {s_after_edit.minutes} min, "
          f"{s_after_edit.tests_count} tests")

    # 9. Delete a session
    models.delete_session(sid2)
    remaining = models.list_sessions_for_date(today.isoformat())
    assert len(remaining) == 1 and remaining[0].id == sid1
    print(f"delete ok: {len(remaining)} session remaining")

    # 10. Empty-data resilience — call analytics with a far-past date that
    # has no sessions. Functions must return zeros, never raise.
    empty_summary = analytics.today_summary(date(2000, 1, 1))
    assert empty_summary["minutes"] == 0
    assert empty_summary["goal_percent"] == 0.0
    assert "next_step_text" in empty_summary
    # data_quality on an empty range should be 0
    empty_dq = analytics.data_quality((date(2000, 1, 1), date(2000, 1, 7)))
    assert empty_dq == 0.0
    # exam_taraz_series is empty in this test (no exams seeded)
    empty_series = analytics.exam_taraz_series()
    assert empty_series == []
    # goal_gap on a non-existent goal returns None
    no_gap = goals.goal_gap(math.id, "weekly", date(2000, 1, 1))
    assert no_gap is None
    print("empty-data resilience ok")

    print("\nALL E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
