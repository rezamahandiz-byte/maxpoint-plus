"""Persistent study timer domain logic.

The timer is stored in local SQLite settings, not only in widget state. It
survives tab switches, a process restart, and temporary offline periods.
No Flet imports live in this module, which makes the behaviour testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from core import db, models
from core.fa_dates import ascii_digits
from services import clock_sync

TEHRAN = ZoneInfo("Asia/Tehran")
K_STARTED = "active_study_started_at"
K_ACTIVITY_ID = "active_study_activity_id"
K_ACTIVITY_NAME = "active_study_activity_name"
K_KIND = "active_study_kind"
K_TOPIC = "active_study_topic"
K_TEST_COUNT = "active_study_test_count"
K_PAUSED_AT = "active_study_paused_at"
K_PAUSED_SECONDS = "active_study_paused_seconds"
K_LAST_ACTIVITY = "study_timer_last_activity_id"
K_LAST_KIND = "study_timer_last_kind"
_ACTIVE_KEYS = (
    K_STARTED, K_ACTIVITY_ID, K_ACTIVITY_NAME, K_KIND, K_TOPIC,
    K_TEST_COUNT, K_PAUSED_AT, K_PAUSED_SECONDS,
)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return _aware_utc(datetime.fromisoformat(raw))
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class ActiveStudySession:
    activity_id: int
    activity_name: str
    kind: str
    topic: str
    started_at: datetime
    test_count: int = 0
    paused_at: Optional[datetime] = None
    paused_seconds: int = 0

    @property
    def is_paused(self) -> bool:
        return self.paused_at is not None

    def elapsed_seconds(self, now: Optional[datetime] = None) -> int:
        current = _aware_utc(now or clock_sync.now_utc())
        active_end = min(current, self.paused_at) if self.paused_at is not None else current
        total = max(0, int((active_end - self.started_at).total_seconds()))
        if self.paused_at is None:
            total -= max(0, int(self.paused_seconds))
        else:
            total -= max(0, int(self.paused_seconds))
        return max(0, total)


def get_active() -> Optional[ActiveStudySession]:
    # One read per timer tick, instead of opening a separate SQLite connection
    # for each setting. The main UI refreshes the elapsed time every second.
    placeholders = ",".join("?" for _ in _ACTIVE_KEYS)
    rows = db.fetch_all(
        f"SELECT key, value FROM settings WHERE key IN ({placeholders});",
        _ACTIVE_KEYS,
    )
    values = {str(row["key"]): str(row["value"] or "") for row in rows}
    raw_start = values.get(K_STARTED, "")
    if not raw_start:
        return None
    started = _parse_datetime(raw_start)
    try:
        activity_id = int(values.get(K_ACTIVITY_ID, "0") or 0)
    except (TypeError, ValueError):
        return None
    kind = values.get(K_KIND, "study") or "study"
    if started is None or activity_id <= 0 or kind not in {"study", "test"}:
        return None
    try:
        tests = max(0, int(ascii_digits(values.get(K_TEST_COUNT, "0") or "0") or 0))
        paused_seconds = max(0, int(values.get(K_PAUSED_SECONDS, "0") or 0))
    except (TypeError, ValueError):
        tests, paused_seconds = 0, 0
    paused_at = _parse_datetime(values.get(K_PAUSED_AT, "") or "")
    stored_name = values.get(K_ACTIVITY_NAME, "") or ""
    if not stored_name:
        known_activity = models.get_activity(activity_id)
        stored_name = known_activity.name if known_activity else "درس انتخاب‌شده"
        models.set_setting(K_ACTIVITY_NAME, stored_name)
    return ActiveStudySession(
        activity_id=activity_id,
        activity_name=stored_name,
        kind=kind,
        topic=values.get(K_TOPIC, "") or "",
        started_at=started,
        test_count=tests,
        paused_at=paused_at,
        paused_seconds=paused_seconds,
    )


def start(activity_id: int, activity_name: str, kind: str = "study", topic: str = "",
          started_at: Optional[datetime] = None) -> ActiveStudySession:
    """Start a session; refusing to silently overwrite an active session."""
    activity_id = int(activity_id)
    if activity_id <= 0:
        raise ValueError("یک درس یا فعالیت معتبر انتخاب کن.")
    if kind not in {"study", "test"}:
        raise ValueError("نوع جلسه معتبر نیست.")
    if get_active() is not None:
        raise ValueError("یک جلسه هنوز فعال است؛ ابتدا آن را پایان بده یا لغو کن.")
    # Clear an orphaned/incomplete timer before writing a complete new one.
    clear_active()
    start_utc = _aware_utc(started_at or clock_sync.now_utc())
    models.set_setting(K_STARTED, start_utc.isoformat(timespec="seconds"))
    models.set_setting(K_ACTIVITY_ID, str(activity_id))
    models.set_setting(K_ACTIVITY_NAME, (activity_name or "درس انتخاب‌شده").strip()[:80])
    models.set_setting(K_KIND, kind)
    models.set_setting(K_TOPIC, (topic or "").strip()[:140])
    models.set_setting(K_TEST_COUNT, "0")
    models.set_setting(K_PAUSED_AT, "")
    models.set_setting(K_PAUSED_SECONDS, "0")
    models.set_setting(K_LAST_ACTIVITY, str(activity_id))
    models.set_setting(K_LAST_KIND, kind)
    state = get_active()
    if state is None:
        raise RuntimeError("زمان‌سنج ذخیره نشد؛ دوباره تلاش کن.")
    return state


def set_test_count(value: str | int) -> int:
    """Persist the editable test count while a test session is running."""
    raw = ascii_digits(value).strip()
    if raw == "":
        number = 0
    else:
        try:
            number = int(raw)
        except ValueError as exc:
            raise ValueError("تعداد تست باید عدد صحیح باشد.") from exc
    if number < 0 or number > 100000:
        raise ValueError("تعداد تست باید بین صفر تا ۱۰۰۰۰۰ باشد.")
    models.set_setting(K_TEST_COUNT, str(number))
    return number


def pause(now: Optional[datetime] = None) -> bool:
    state = get_active()
    if state is None or state.is_paused:
        return False
    paused = _aware_utc(now or clock_sync.now_utc())
    models.set_setting(K_PAUSED_AT, paused.isoformat(timespec="seconds"))
    return True


def resume(now: Optional[datetime] = None) -> bool:
    state = get_active()
    if state is None or not state.is_paused or state.paused_at is None:
        return False
    resumed = _aware_utc(now or clock_sync.now_utc())
    additional_pause = max(0, int((resumed - state.paused_at).total_seconds()))
    models.set_setting(K_PAUSED_SECONDS, str(state.paused_seconds + additional_pause))
    models.set_setting(K_PAUSED_AT, "")
    return True


@dataclass(frozen=True)
class FinishedStudySession:
    session_id: int
    activity_name: str
    kind: str
    topic: str
    minutes: int
    tests_count: int
    started_at: datetime
    ended_at: datetime


def finish(now: Optional[datetime] = None) -> Optional[FinishedStudySession]:
    """Save the active session atomically from the UI's point of view.

    Active timer settings are only cleared after the DB insert succeeds, so a
    database or validation error does not destroy the in-progress session.
    """
    state = get_active()
    if state is None:
        return None
    ended = _aware_utc(now or clock_sync.now_utc())
    seconds = state.elapsed_seconds(ended)
    minutes = max(1, (seconds + 30) // 60)
    start_local = state.started_at.astimezone(TEHRAN)
    end_local = ended.astimezone(TEHRAN)
    start_time = start_local.strftime("%H:%M")
    end_time = end_local.strftime("%H:%M")
    # SQLite model validation rejects identical display times. A quick start-stop
    # is still a valid one-minute entry, so give it a one-minute display span.
    if start_time == end_time:
        end_time = (start_local + timedelta(minutes=1)).strftime("%H:%M")
    tests_count = state.test_count if state.kind == "test" else 0
    session_id = models.create_session(
        start_local.date().isoformat(),
        state.activity_id,
        minutes,
        tests_count=tests_count,
        note=state.topic or None,
        start_time=start_time,
        end_time=end_time,
        topic=state.topic,
        test_type="تست‌زنی" if state.kind == "test" else "مطالعه",
    )
    clear_active()
    return FinishedStudySession(
        session_id=session_id,
        activity_name=state.activity_name,
        kind=state.kind,
        topic=state.topic,
        minutes=minutes,
        tests_count=tests_count,
        started_at=state.started_at,
        ended_at=ended,
    )


def clear_active() -> None:
    for key in _ACTIVE_KEYS:
        models.delete_setting(key)


def cancel() -> bool:
    existed = get_active() is not None
    clear_active()
    return existed
