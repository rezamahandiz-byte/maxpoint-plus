"""MAXPOINT domain models — frozen dataclasses mirroring SQLite rows.

These are pure value objects. They never touch the database themselves;
that's the job of `core.db` and the small per-table repository helpers in
this module. UI code receives these dataclasses and never sees sqlite3.Row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import db


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ActivityGroup:
    id: int
    name: str
    color: Optional[str] = None
    priority: str = "flexible"  # 'mandatory' | 'priority' | 'flexible'


@dataclass(frozen=True)
class Activity:
    id: int
    name: str
    group_id: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_custom: int = 0
    is_active: int = 1

    @property
    def active(self) -> bool:
        return bool(self.is_active)


@dataclass(frozen=True)
class Session:
    id: int
    date: str  # YYYY-MM-DD
    activity_id: int
    minutes: int = 0
    tests_count: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    note: Optional[str] = None
    correct_count: int = 0
    wrong_count: int = 0
    blank_count: int = 0
    topic: str = ""
    test_type: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class Goal:
    id: int
    activity_id: int
    period: str  # 'daily' | 'weekly'
    target_minutes: int = 0
    target_tests: int = 0


@dataclass(frozen=True)
class Exam:
    id: int
    date: str
    exam_number: int
    taraz: int
    notes: Optional[str] = None
    rank: Optional[int] = None


@dataclass(frozen=True)
class ExamSubject:
    id: int
    exam_id: int
    subject: str
    percent: Optional[float] = None
    correct: Optional[int] = None
    wrong: Optional[int] = None
    blank: Optional[int] = None


@dataclass(frozen=True)
class Report:
    id: int
    type: str  # 'daily' | 'weekly' | 'monthly'
    period_start: str
    period_end: str
    content: str
    generated_at: str


@dataclass(frozen=True)
class Setting:
    key: str
    value: str


# --------------------------------------------------------------------------- #
# Repositories — thin CRUD wrappers around db.fetch_*/execute.
# Each function returns a dataclass instance (or None / list).
# --------------------------------------------------------------------------- #


def _row_to(cls, row):
    if row is None:
        return None
    # sqlite3.Row is mapping-like; pick only the columns that match a dataclass
    # field so we don't choke on extra columns or renamed ones.
    import dataclasses as _dc
    valid = {f.name for f in _dc.fields(cls)}
    kwargs = {k: row[k] for k in row.keys() if k in valid}
    return cls(**kwargs)


# ---- ActivityGroup -------------------------------------------------------- #


def list_groups() -> list[ActivityGroup]:
    rows = db.fetch_all("SELECT * FROM activity_groups ORDER BY id;")
    return [_row_to(ActivityGroup, r) for r in rows]


def get_group(group_id: int) -> Optional[ActivityGroup]:
    return _row_to(ActivityGroup, db.fetch_one(
        "SELECT * FROM activity_groups WHERE id=?;", (group_id,)))


# ---- Activity ------------------------------------------------------------- #

# [Ch5] Read-through activity cache — avoids repeated DB queries
_activity_cache: dict[int, Activity] | None = None
_activity_cache_dirty: bool = True


def _ensure_activity_cache() -> dict[int, Activity]:
    """Load all activities into cache if dirty."""
    global _activity_cache, _activity_cache_dirty
    if _activity_cache is None or _activity_cache_dirty:
        rows = db.fetch_all("SELECT * FROM activities ORDER BY name;")
        _activity_cache = {_row_to(Activity, r).id: _row_to(Activity, r) for r in rows}
        _activity_cache_dirty = False
    return _activity_cache


def invalidate_activity_cache() -> None:
    """Mark cache as dirty — call after create/rename/deactivate activity."""
    global _activity_cache_dirty
    _activity_cache_dirty = True


def list_activities(active_only: bool = True) -> list[Activity]:
    cache = _ensure_activity_cache()
    acts = list(cache.values())
    if active_only:
        acts = [a for a in acts if a.is_active]
    return sorted(acts, key=lambda a: a.name)


def get_activity(activity_id: int) -> Optional[Activity]:
    cache = _ensure_activity_cache()
    return cache.get(activity_id)


def find_activity_by_name(name: str) -> Optional[Activity]:
    return _row_to(Activity, db.fetch_one(
        "SELECT * FROM activities WHERE name=? COLLATE NOCASE;", (name,)))


def create_activity(name: str, group_id: Optional[int],
                    color: Optional[str] = None,
                    icon: Optional[str] = None) -> int:
    result = db.execute(
        "INSERT INTO activities (name, group_id, color, icon, is_custom, is_active) "
        "VALUES (?,?,?,?,1,1);",
        (name, group_id, color, icon),
    )
    invalidate_activity_cache()
    return result


def rename_activity(activity_id: int, new_name: str) -> None:
    db.execute("UPDATE activities SET name=? WHERE id=?;", (new_name, activity_id))
    invalidate_activity_cache()


def set_activity_active(activity_id: int, is_active: bool) -> None:
    db.execute("UPDATE activities SET is_active=? WHERE id=?;",
               (1 if is_active else 0, activity_id))
    invalidate_activity_cache()


# ---- Session -------------------------------------------------------------- #


def list_sessions_for_date(date_str: str) -> list[Session]:
    rows = db.fetch_all(
        "SELECT * FROM sessions WHERE date=? ORDER BY id DESC;", (date_str,))
    return [_row_to(Session, r) for r in rows]


def list_sessions_in_range(start: str, end: str) -> list[Session]:
    rows = db.fetch_all(
        "SELECT * FROM sessions WHERE date BETWEEN ? AND ? ORDER BY date, id;",
        (start, end))
    return [_row_to(Session, r) for r in rows]


def create_session(date_str: str, activity_id: int, minutes: int,
                   tests_count: int = 0, note: Optional[str] = None,
                   start_time: Optional[str] = None, end_time: Optional[str] = None,
                   correct_count: int = 0, wrong_count: int = 0, blank_count: int = 0,
                   topic: str = "", test_type: str = "") -> int:
    from datetime import date as _date
    try:
        _date.fromisoformat(date_str)
    except (TypeError, ValueError) as exc:
        raise ValueError("تاریخ فعالیت معتبر نیست.") from exc
    mins, tests = int(minutes), int(tests_count)
    correct, wrong, blank = int(correct_count), int(wrong_count), int(blank_count)
    if mins <= 0:
        raise ValueError("مدت فعالیت باید بیشتر از صفر باشد.")
    if min(tests, correct, wrong, blank) < 0:
        raise ValueError("تعداد تست‌ها نمی‌تواند منفی باشد.")
    if correct + wrong + blank > tests:
        tests = correct + wrong + blank
    if bool(start_time) != bool(end_time): raise ValueError("برای ثبت ساعت، ساعت شروع و پایان را هر دو وارد کن.")
    if start_time and end_time:
        _validate_time_range(start_time, end_time)
    return db.execute(
        "INSERT INTO sessions (date, start_time, end_time, activity_id, minutes, tests_count, "
        "correct_count, wrong_count, blank_count, topic, test_type, note, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);",
        (date_str, start_time or None, end_time or None, activity_id, mins, tests,
         correct, wrong, blank, topic.strip(), test_type.strip(), note, db.now_iso()),
    )


def _time_minutes(value: str) -> int:
    try:
        h, m = map(int, value.split(":", 1))
    except Exception as exc: raise ValueError("ساعت باید به شکل 09:30 باشد.") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError("ساعت واردشده معتبر نیست.")
    return h * 60 + m


def _validate_time_range(start_time: str, end_time: str) -> None:
    if _time_minutes(start_time) == _time_minutes(end_time): raise ValueError("ساعت شروع و پایان یکسان است.")


def find_session_overlaps(date_str: str, start_time: str, end_time: str,
                          exclude_session_id: Optional[int] = None) -> list[Session]:
    """Find same-day time overlaps, including sessions that cross midnight."""
    if not start_time or not end_time: return []
    proposed_start = _time_minutes(start_time)
    proposed_end = _time_minutes(end_time)
    if proposed_end <= proposed_start: proposed_end += 1440
    rows = db.fetch_all("SELECT * FROM sessions WHERE date=? AND start_time IS NOT NULL AND end_time IS NOT NULL;", (date_str,))
    overlaps=[]
    for row in rows:
        if exclude_session_id is not None and row["id"] == exclude_session_id: continue
        try:
            other_start=_time_minutes(row["start_time"]); other_end=_time_minutes(row["end_time"])
            if other_end <= other_start: other_end += 1440
            if proposed_start < other_end and other_start < proposed_end:
                overlaps.append(_row_to(Session, row))
        except ValueError: continue
    return overlaps


def update_session(session_id: int, *, activity_id: Optional[int] = None,
                   minutes: Optional[int] = None, tests_count: Optional[int] = None,
                   note: Optional[str] = None, start_time: Optional[str] = None,
                   end_time: Optional[str] = None, correct_count: Optional[int] = None,
                   wrong_count: Optional[int] = None, blank_count: Optional[int] = None,
                   topic: Optional[str] = None, test_type: Optional[str] = None) -> None:
    if minutes is not None and int(minutes) <= 0:
        raise ValueError("مدت فعالیت باید بیشتر از صفر باشد.")
    numeric_counts = {
        "تعداد تست": tests_count, "درست": correct_count,
        "غلط": wrong_count, "نزده": blank_count,
    }
    for label, value in numeric_counts.items():
        if value is not None and int(value) < 0:
            raise ValueError(f"{label} نمی‌تواند منفی باشد.")
    count_fields_provided = any(v is not None for v in (tests_count, correct_count, wrong_count, blank_count))
    if count_fields_provided:
        current = db.fetch_one(
            "SELECT tests_count, correct_count, wrong_count, blank_count FROM sessions WHERE id=?;",
            (int(session_id),),
        )
        existing = dict(current) if current else {
            "tests_count": 0, "correct_count": 0, "wrong_count": 0, "blank_count": 0,
        }
        resolved_counts = {
            "correct_count": int(correct_count if correct_count is not None else existing.get("correct_count", 0) or 0),
            "wrong_count": int(wrong_count if wrong_count is not None else existing.get("wrong_count", 0) or 0),
            "blank_count": int(blank_count if blank_count is not None else existing.get("blank_count", 0) or 0),
        }
        total_answers = sum(resolved_counts.values())
        resolved_tests = int(tests_count if tests_count is not None else existing.get("tests_count", 0) or 0)
        resolved_tests = max(resolved_tests, total_answers)
        if tests_count is not None or resolved_tests != int(existing.get("tests_count", 0) or 0):
            tests_count = resolved_tests
    sets: list[str] = []; params: list = []
    for key, value in (("activity_id", activity_id), ("minutes", minutes), ("tests_count", tests_count),
                       ("note", note), ("start_time", start_time), ("end_time", end_time),
                       ("correct_count", correct_count), ("wrong_count", wrong_count),
                       ("blank_count", blank_count), ("topic", topic), ("test_type", test_type)):
        if value is not None:
            if key in ("activity_id", "minutes", "tests_count", "correct_count", "wrong_count", "blank_count"): value = int(value)
            sets.append(f"{key}=?"); params.append(value)
    if not sets: return
    params.append(session_id)
    db.execute(f"UPDATE sessions SET {', '.join(sets)} WHERE id=?;", params)


def delete_session(session_id: int) -> None:
    db.execute("DELETE FROM sessions WHERE id=?;", (session_id,))


def get_session(session_id: int) -> Optional[Session]:
    return _row_to(Session, db.fetch_one(
        "SELECT * FROM sessions WHERE id=?;", (session_id,)))


# ---- Goal ----------------------------------------------------------------- #


def list_goals() -> list[Goal]:
    rows = db.fetch_all("SELECT * FROM goals ORDER BY id;")
    return [_row_to(Goal, r) for r in rows]


def get_goal(activity_id: int, period: str) -> Optional[Goal]:
    return _row_to(Goal, db.fetch_one(
        "SELECT * FROM goals WHERE activity_id=? AND period=?;",
        (activity_id, period)))


def upsert_goal(activity_id: int, period: str,
                target_minutes: int, target_tests: int = 0) -> None:
    """[Ch6] Atomic upsert using ON CONFLICT (requires v4 unique index)."""
    if period not in ("daily", "weekly"):
        raise ValueError("نوع هدف باید روزانه یا هفتگی باشد.")
    target_minutes, target_tests = int(target_minutes), int(target_tests)
    if target_minutes < 0 or target_tests < 0:
        raise ValueError("هدف زمانی و تعداد تست نمی‌تواند منفی باشد.")
    # Try atomic upsert first (works with v4 unique index)
    try:
        db.execute(
            "INSERT INTO goals (activity_id, period, target_minutes, target_tests) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(activity_id, period) DO UPDATE SET "
            "target_minutes=excluded.target_minutes, "
            "target_tests=excluded.target_tests;",
            (activity_id, period, target_minutes, target_tests),
        )
    except Exception:
        # Fallback for pre-v4 databases without the unique index
        existing = get_goal(activity_id, period)
        if existing is None:
            db.execute(
                "INSERT INTO goals (activity_id, period, target_minutes, target_tests) "
                "VALUES (?,?,?,?);",
                (activity_id, period, target_minutes, target_tests),
            )
        else:
            db.execute(
                "UPDATE goals SET target_minutes=?, target_tests=? WHERE id=?;",
                (target_minutes, target_tests, existing.id),
            )


def delete_goal(activity_id: int, period: str) -> None:
    db.execute("DELETE FROM goals WHERE activity_id=? AND period=?;",
               (activity_id, period))


# ---- Weekly Goals (day-specific) ----------------------------------------- #

# Iranian week: 0=Saturday, 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday
WEEKLY_DAY_NAMES = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def get_weekly_goal(activity_id: int, day_of_week: int) -> int:
    """Get target minutes for a specific activity on a specific day (0-6)."""
    row = db.fetch_one(
        "SELECT target_minutes FROM weekly_goals WHERE activity_id=? AND day_of_week=?;",
        (activity_id, day_of_week),
    )
    return int(row["target_minutes"]) if row else 0


def set_weekly_goal(activity_id: int, day_of_week: int, target_minutes: int) -> None:
    """Set or update target minutes for a specific activity/day combo."""
    target_minutes = max(0, int(target_minutes))
    try:
        db.execute(
            "INSERT INTO weekly_goals (activity_id, day_of_week, target_minutes) "
            "VALUES (?,?,?) "
            "ON CONFLICT(activity_id, day_of_week) DO UPDATE SET "
            "target_minutes=excluded.target_minutes;",
            (activity_id, day_of_week, target_minutes),
        )
    except Exception:
        db.execute(
            "DELETE FROM weekly_goals WHERE activity_id=? AND day_of_week=?;",
            (activity_id, day_of_week),
        )
        if target_minutes > 0:
            db.execute(
                "INSERT INTO weekly_goals (activity_id, day_of_week, target_minutes) "
                "VALUES (?,?,?);",
                (activity_id, day_of_week, target_minutes),
            )


def get_all_weekly_goals() -> list[dict]:
    """Get all weekly goals as dicts: {activity_id, day_of_week, target_minutes}."""
    rows = db.fetch_all("SELECT * FROM weekly_goals ORDER BY activity_id, day_of_week;")
    return [dict(r) for r in rows]


def get_today_weekly_goals() -> list[dict]:
    """Get weekly goals for today's day-of-week (Iranian: 0=Saturday)."""
    from services import clock_sync
    today = clock_sync.now_local().date()
    # Python weekday: Mon=0..Sun=6 → Iranian: Sat=0..Fri=6
    iranian_dow = (today.weekday() + 2) % 7
    rows = db.fetch_all(
        """SELECT wg.activity_id, wg.target_minutes, a.name, a.color
           FROM weekly_goals wg
           JOIN activities a ON a.id = wg.activity_id
           WHERE wg.day_of_week = ? AND wg.target_minutes > 0
           ORDER BY a.name;""",
        (iranian_dow,),
    )
    return [dict(r) for r in rows]


# ---- Exam ----------------------------------------------------------------- #


def list_exams() -> list[Exam]:
    rows = db.fetch_all("SELECT * FROM exams ORDER BY date, exam_number;")
    return [_row_to(Exam, r) for r in rows]


def create_exam(date_str: str, exam_number: int, taraz: int,
                notes: Optional[str] = None, rank: Optional[int] = None,
                subjects: Optional[list[dict]] = None) -> int:
    """Create an exam and its subject details in one transaction."""
    from datetime import date as _date
    try:
        _date.fromisoformat(date_str)
    except (TypeError, ValueError) as exc:
        raise ValueError("تاریخ آزمون معتبر نیست.") from exc
    exam_number, taraz = int(exam_number), int(taraz)
    rank = int(rank) if rank is not None else None
    if exam_number <= 0 or taraz < 0 or (rank is not None and rank <= 0):
        raise ValueError("شماره، تراز یا رتبه‌ی آزمون معتبر نیست.")
    cleaned_subjects = []
    for item in (subjects or []):
        name = str(item.get("subject", "")).strip()
        if not name:
            continue
        percent = item.get("percent")
        percent = float(percent) if percent is not None else None
        counts = []
        for key in ("correct", "wrong", "blank"):
            value = item.get(key)
            if value is not None:
                value = int(value)
                if value < 0:
                    raise ValueError("تعداد درست/غلط/نزده نمی‌تواند منفی باشد.")
            counts.append(value)
        if percent is not None and not 0 <= percent <= 100:
            raise ValueError(f"درصد درس «{name}» باید بین ۰ تا ۱۰۰ باشد.")
        cleaned_subjects.append({
            "subject": name, "percent": percent, "correct": counts[0],
            "wrong": counts[1], "blank": counts[2],
        })
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO exams (date, exam_number, taraz, rank, notes) VALUES (?,?,?,?,?);",
            (date_str, int(exam_number), int(taraz), rank, notes))
        exam_id = int(cur.lastrowid)
        rows=[]
        for item in cleaned_subjects:
            rows.append((exam_id, item["subject"], item["percent"], item["correct"], item["wrong"], item["blank"]))
        if rows:
            conn.executemany("INSERT INTO exam_subjects (exam_id, subject, percent, correct, wrong, blank) VALUES (?,?,?,?,?,?);", rows)
    return exam_id


def delete_exam(exam_id: int) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM exam_subjects WHERE exam_id=?;", (int(exam_id),))
        conn.execute("DELETE FROM exams WHERE id=?;", (int(exam_id),))


def list_exam_subjects(exam_id: int) -> list[ExamSubject]:
    rows = db.fetch_all("SELECT * FROM exam_subjects WHERE exam_id=?;", (exam_id,))
    return [_row_to(ExamSubject, r) for r in rows]


# ---- Report --------------------------------------------------------------- #


def save_report(report_type: str, period_start: str, period_end: str,
                content: str) -> int:
    return db.execute(
        "INSERT INTO reports (type, period_start, period_end, content, generated_at) "
        "VALUES (?,?,?,?,?);",
        (report_type, period_start, period_end, content, db.now_iso()))


def list_reports(limit: int = 20) -> list[Report]:
    rows = db.fetch_all(
        "SELECT * FROM reports ORDER BY generated_at DESC LIMIT ?;", (limit,))
    return [_row_to(Report, r) for r in rows]


# ---- Settings ------------------------------------------------------------- #


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = db.fetch_one("SELECT value FROM settings WHERE key=?;", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?);",
               (key, value))


def delete_setting(key: str) -> None:
    db.execute("DELETE FROM settings WHERE key=?;", (key,))


def all_settings() -> list[Setting]:
    rows = db.fetch_all("SELECT * FROM settings ORDER BY key;")
    return [_row_to(Setting, r) for r in rows]
