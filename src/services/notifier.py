"""MAXPOINT Notifier — in-app notification system (v0.7.1)

Native Android notifications were disabled in v0.7 because
`flet-android-notifications` requires Gradle core library desugaring.
This module provides an IN-APP notification system that works on all
platforms (web, desktop, Android) while the app is open. It uses a
background asyncio task that periodically checks if it's time to show
a "درس می‌خونی؟" prompt.

The notification shows as an in-app modal dialog (via ctx.open_dialog)
with Yes/No buttons:
  - "آره" → silenced for 1 hour
  - "نه"  → next check in 10 minutes

Quiet hours, weekdays, and interval are respected.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Iterable

import flet as ft


# Keep the message-tone dict so the UI's tone-preview still renders.
MESSAGES = {
    "study": (
        "وقت یک قدم کوچک است",
        "یک بازه‌ی کوتاه تمرکز هم ارزشمند است؛ با ۱۵ دقیقه شروع کن.",
    ),
    "break": (
        "مکث کوتاه، تمرکز بهتر",
        "کمی از صفحه فاصله بگیر، آب بنوش و بعد با انرژی برگرد.",
    ),
    "log": (
        "زمانت را ثبت کن",
        "اگر فعالیتی انجام دادی، همین حالا ثبتش کن تا گزارش روز دقیق بماند.",
    ),
    "review": (
        "جمع‌بندی آرام امروز",
        "چند دقیقه برای مرور پیشرفت امروز و انتخاب قدم فردا وقت بگذار.",
    ),
}

MESSAGE_TONES = {
    "calm": MESSAGES,
    "energetic": {
        "study": ("بزن بریم!", "فقط ۱۵ دقیقه شروع کن؛ لازم نیست همه‌چیز را یک‌جا تمام کنی."),
        "break": ("شارژ دوباره", "کمی حرکت کن و آب بنوش؛ بعد با انرژی برگرد."),
        "log": ("ثبتش کن و جلو برو", "فعالیتت را ثبت کن تا پیشرفت واقعی‌ات دیده شود."),
        "review": ("وقت دیدن پیشرفت امروز", "موفقیت‌ها و قدم بعدی‌ات را کوتاه مرور کن."),
    },
    "minimal": {
        "study": ("شروع تمرکز", "یک بازه‌ی ۱۵ دقیقه‌ای شروع کن."),
        "break": ("زمان مکث", "کمی استراحت کن و آب بنوش."),
        "log": ("ثبت فعالیت", "زمان فعالیتت را ثبت کن."),
        "review": ("مرور روز", "پیشرفت امروز و کار فردا را مرور کن."),
    },
}

KIND_LABELS = {
    "study": "شروع تمرکز",
    "break": "مکث و استراحت",
    "log": "ثبت فعالیت",
    "review": "جمع‌بندی روز",
}


# --------------------------------------------------------------------------- #
# Settings helpers — stored in SQLite via core.models
# --------------------------------------------------------------------------- #

def _get(key: str, default: str = "") -> str:
    from core import models
    return models.get_setting(key, default) or default


def _set(key: str, value: str) -> None:
    from core import models
    models.set_setting(key, value)


def is_enabled() -> bool:
    return _get("reminders_enabled", "0") == "1"


def set_enabled(enabled: bool) -> None:
    _set("reminders_enabled", "1" if enabled else "0")


def get_interval() -> int:
    try:
        return max(5, int(_get("reminder_interval", "30")))
    except (TypeError, ValueError):
        return 30


def set_interval(minutes: int) -> None:
    _set("reminder_interval", str(max(5, int(minutes))))


def get_quiet_start() -> str:
    """[Ch13] Returns HH:MM format (minute-level precision)."""
    return _get("quiet_start_time", "23:00")


def get_quiet_end() -> str:
    """[Ch13] Returns HH:MM format."""
    return _get("quiet_end_time", "07:00")


def set_quiet_start(hhmm: str) -> None:
    """[Ch13] Store as HH:MM for minute-level precision."""
    _set("quiet_start_time", hhmm if ":" in hhmm else f"{hhmm}:00")


def set_quiet_end(hhmm: str) -> None:
    """[Ch13] Store as HH:MM."""
    _set("quiet_end_time", hhmm if ":" in hhmm else f"{hhmm}:00")


def _parse_hhmm(s: str) -> tuple[int, int]:
    """Parse 'HH:MM' → (hours, minutes). Returns (0, 0) on error."""
    try:
        parts = s.split(":")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 0, 0


def _get_silenced_until() -> dt.datetime | None:
    s = _get("notif_silenced_until", "")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _set_silenced_until(when: dt.datetime | None) -> None:
    _set("notif_silenced_until", when.isoformat() if when else "")


def _get_next_check_at() -> dt.datetime | None:
    s = _get("notif_next_check_at", "")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _set_next_check_at(when: dt.datetime | None) -> None:
    _set("notif_next_check_at", when.isoformat() if when else "")


# --------------------------------------------------------------------------- #
# Quiet-hours logic
# --------------------------------------------------------------------------- #

def _in_quiet_hours(now: dt.datetime) -> bool:
    """[Ch13] Minute-level quiet hours check with midnight wraparound."""
    start_s = get_quiet_start()
    end_s = get_quiet_end()
    if not start_s or not end_s:
        return False
    sh, sm = _parse_hhmm(start_s)
    eh, em = _parse_hhmm(end_s)
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    now_min = now.hour * 60 + now.minute
    if start_min == end_min:
        return False  # no quiet period
    if start_min < end_min:
        # Same-day window, e.g. 09:00 → 12:00
        return start_min <= now_min < end_min
    else:
        # Wraps midnight, e.g. 23:00 → 07:00
        return now_min >= start_min or now_min < end_min


def _is_active_day(now: dt.datetime) -> bool:
    """Check if today's weekday is enabled."""
    try:
        weekdays_str = _get("reminder_weekdays", "0,1,2,3,4,5,6")
        weekdays = [int(d) for d in weekdays_str.split(",") if d.strip()]
    except (TypeError, ValueError):
        weekdays = list(range(7))
    return now.weekday() in weekdays


# --------------------------------------------------------------------------- #
# Should-notify decision
# --------------------------------------------------------------------------- #

def _now() -> dt.datetime:
    """Get current time via clock_sync (Tehran timezone), with fallback."""
    try:
        from services import clock_sync
        return clock_sync.now_local()
    except Exception:
        return dt.datetime.now()


def should_notify(now: dt.datetime) -> bool:
    """True if a notification should fire right now."""
    if not is_enabled():
        return False
    if _in_quiet_hours(now):
        return False
    if not _is_active_day(now):
        return False
    silenced = _get_silenced_until()
    if silenced and now < silenced:
        return False
    next_check = _get_next_check_at()
    if next_check and now < next_check:
        return False
    # Check if enough time has passed since last notification
    last = _get_last_shown()
    if last:
        elapsed = (now - last).total_seconds() / 60
        if elapsed < get_interval():
            return False
    return True


def _get_last_shown() -> dt.datetime | None:
    s = _get("notif_last_shown", "")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _set_last_shown(when: dt.datetime) -> None:
    _set("notif_last_shown", when.isoformat())


# --------------------------------------------------------------------------- #
# Show notification (in-app modal)
# --------------------------------------------------------------------------- #

def _show_notification(ctx) -> None:
    """Show the 'درس می‌خوانی؟' modal dialog."""
    from ui import (
        ACCENT, ON_SURFACE, ON_SURFACE_VAR, SURFACE_HIGH,
        filled_button, text_button,
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(value="درس می‌خوانی؟", rtl=True,
                      size=20, weight=ft.FontWeight.W_600,
                      color=ON_SURFACE),
        content=ft.Text(
            value="اگر در حال مطالعه‌ای، ثبتش کن تا نمودارت پر شود.",
            rtl=True, size=14, color=ON_SURFACE_VAR),
        actions=[
            text_button("نه", on_click=lambda _: _on_no(ctx, dlg)),
            filled_button("آره", on_click=lambda _: _on_yes(ctx, dlg)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    # Play chime if audio is available
    try:
        audio = getattr(ctx, "audio", None)
        if audio is not None:
            audio.play()
    except Exception:
        pass
    ctx.open_dialog(dlg)
    _set_last_shown(_now())


def _on_yes(ctx, dlg) -> None:
    """User said 'yes' — silence for 1 hour."""
    _set_silenced_until(_now() + dt.timedelta(hours=1))
    _set_next_check_at(None)
    ctx.close_dialog(dlg)
    ctx.snack("یک ساعت دیگر یادآوری می‌شود.")


def _on_no(ctx, dlg) -> None:
    """User said 'no' — check again in 10 minutes."""
    _set_next_check_at(_now() + dt.timedelta(minutes=10))
    _set_silenced_until(None)
    ctx.close_dialog(dlg)


# --------------------------------------------------------------------------- #
# Background loop
# --------------------------------------------------------------------------- #

async def loop(ctx) -> None:
    """Background loop: check every 60 seconds if it's time to notify.

    Never raises. Silently continues on any error.
    """
    await asyncio.sleep(10)  # wait for app to settle
    while True:
        try:
            now = _now()
            if should_notify(now):
                _show_notification(ctx)
                await asyncio.sleep(60)  # don't spam
            else:
                await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(60)


# --------------------------------------------------------------------------- #
# Public API (compatibility with what main.py + ui/notifications.py expect)
# --------------------------------------------------------------------------- #

def init(platform: Any | None = None, on_notification_tap=None) -> Any | None:
    """Returns a marker object indicating in-app notifications are active."""
    return {"type": "in_app"}  # truthy so `available()` returns True


def available(service: Any | None) -> bool:
    """In-app notifications are always available (unlike native Android)."""
    return True


async def configure_reminders(
    service: Any | None,
    enabled: bool,
    interval_minutes: int = 60,
    start_hour: int = 8,
    end_hour: int = 22,
    reminder_kinds: Iterable[str] | None = None,
    sound_enabled: bool = True,
    vibration_enabled: bool = True,
    exact_enabled: bool = False,
    request_exact_permission: bool = False,
    weekdays: Iterable[int] | None = None,
    sound_mode: str = "custom",
    prompt_for_notification_permission: bool = True,
    message_tone: str = "calm",
    quiet_hours_enabled: bool = True,
    quiet_start_hour: int = 22,
    quiet_end_hour: int = 8,
) -> tuple[bool, str]:
    """Save settings to SQLite. The background loop picks them up automatically."""
    set_enabled(enabled)
    set_interval(interval_minutes)
    _set("reminder_start", str(start_hour))
    _set("reminder_end", str(end_hour))
    _set("reminder_sound", "1" if sound_enabled else "0")
    _set("reminder_vibration", "1" if vibration_enabled else "0")
    _set("reminder_sound_mode", sound_mode)
    _set("reminder_tone", message_tone)
    _set("quiet_hours_enabled", "1" if quiet_hours_enabled else "0")
    _set("quiet_start_hour", str(quiet_start_hour))
    _set("quiet_end_hour", str(quiet_end_hour))
    if weekdays is not None:
        _set("reminder_weekdays", ",".join(str(d) for d in weekdays))
    if reminder_kinds is not None:
        for kind in ("study", "break", "log", "review"):
            _set(f"reminder_kind_{kind}", "1" if kind in reminder_kinds else "0")
    if enabled:
        return True, "یادآور درون‌برنامه‌ای فعال شد. هنگام باز بودن برنامه، هر از گاهی پرسش «درس می‌خوانی؟» نمایش داده می‌شود."
    return True, "یادآور خاموش شد."


async def show_test_notification(
    service: Any | None,
    sound_enabled: bool = True,
    vibration_enabled: bool = True,
    sound_mode: str = "custom",
    message_tone: str = "calm",
) -> tuple[bool, str]:
    """Show a test notification immediately (in-app modal).

    Note: the actual dialog is shown by the caller (ui/notifications.py)
    via _show_notification(ctx). This function just returns a status
    message. The caller checks the return value and shows the dialog
    directly if it's a test.
    """
    return True, "اعلان آزمایشی آماده است؛ دیالگ نمونه نمایش داده می‌شود."


async def check_notification_status(service: Any | None) -> tuple[bool, str]:
    """Report in-app notification status."""
    enabled = is_enabled()
    if enabled:
        return True, "یادآور درون‌برنامه‌ای فعال است."
    return False, "یادآور خاموش است."


async def open_notification_settings(service: Any | None) -> tuple[bool, str]:
    """No native settings to open — in-app only."""
    return False, "تنظیمات یادآور در همین صفحه قابل تغییر است."


async def handle_focus_prompt_action(service: Any | None, action_id: str) -> tuple[bool, str]:
    """Handle Yes/No from the in-app prompt."""
    if action_id == "focus_yes":
        _set_silenced_until(dt.datetime.now() + dt.timedelta(hours=1))
        _set_next_check_at(None)
        return True, "عالیه؛ یک ساعت دیگر دوباره می‌پرسم."
    elif action_id == "focus_no":
        _set_next_check_at(dt.datetime.now() + dt.timedelta(minutes=10))
        _set_silenced_until(None)
        return True, "باشه؛ ده دقیقه‌ی دیگر دوباره می‌پرسم."
    return False, "پاسخ قابل پردازش نیست."


async def restore_saved_settings(service: Any | None) -> None:
    """Nothing to restore — the background loop reads settings live."""
    return None
