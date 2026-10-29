"""Home tab — calm but informative dashboard.

Layout (top → bottom):
  1. Greeting header + Jalali date
  2. Study timer widget (start button OR live timer with pause/stop)
  3. Row of quick stat tiles (today minutes / tests / goal % / streak days)
  4. Next-step card (one concrete suggestion)
  5. Mini 7-day sparkline (tiny bars, no axis labels)
  6. Recent sessions list (last 4 sessions today)
  7. Quick action buttons

The study timer is powered by `core/study_session.py` and survives tab
switches and process restarts because it is persisted in the settings table.
The live timer text is updated once a second by `_timer_tick_loop` in
`main.py`, which reads the `timer_value` control out of `ctx._handlers`.
"""
from __future__ import annotations

from datetime import date, datetime

import flet as ft

from services import clock_sync
from core import analytics, models, study_session, streaks
from core.fa_dates import jalali_label
from ui.theme import Typography, Spacing, Radius, Layout
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    CENTER, border_all, pad_sym, to_fa,
    card, section_title, filled_button, outlined_button, text_button,
    responsive_dialog_width,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    summary = analytics.today_summary(today)
    sessions = models.list_sessions_for_date(today.isoformat())
    weekly = analytics.last_7_days_minutes(today)

    return ft.ListView(
        [
            ft.Container(height=8),
            _header(today),
            ft.Container(height=14),
            _study_timer_card(ctx),
            ft.Container(height=12),
            _stat_tiles(summary, today),
            ft.Container(height=12),
            _next_step_card(summary),
            ft.Container(height=12),
            _sparkline_card(weekly),
            ft.Container(height=12),
            _recent_sessions_card(sessions),
            ft.Container(height=12),
            _quick_actions(ctx),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Header — greeting + date
# --------------------------------------------------------------------------- #


def _header(today) -> ft.Control:
    hour = clock_sync.now_local().hour
    if 5 <= hour < 12:    greeting = "صبح بخیر"
    elif 12 <= hour < 18: greeting = "ظهر بخیر"
    elif 18 <= hour < 22: greeting = "عصر بخیر"
    else:                 greeting = "شب بخیر"

    return ft.Row([
        ft.Column([
            ft.Text(greeting, size=24, weight=ft.FontWeight.W_700,
                    color=ON_SURFACE, rtl=True),
            ft.Text(jalali_label(today.isoformat()), size=13,
                    color=ON_SURFACE_VAR, rtl=True),
        ], spacing=4, expand=True),
        ft.Container(
            width=44, height=44, border_radius=Radius.lg,
            bgcolor=ACCENT_SOFT, alignment=CENTER,
            content=ft.Text("M", size=20, weight=ft.FontWeight.W_800, color=ACCENT),
        ),
    ], spacing=10)


# --------------------------------------------------------------------------- #
# Study timer widget
# --------------------------------------------------------------------------- #


def _study_timer_card(ctx) -> ft.Control:
    active = study_session.get_active()
    if active is None:
        return _idle_timer_card(ctx)
    return _active_timer_card(ctx, active)


def _idle_timer_card(ctx) -> ft.Control:
    last_id = models.get_setting(study_session.K_LAST_ACTIVITY, "") or ""
    last_kind = models.get_setting(study_session.K_LAST_KIND, "study") or "study"
    last_act = models.get_activity(int(last_id)) if last_id.isdigit() else None
    hint = (
        f"آخرین انتخاب: {last_act.name} · {'تست‌زنی' if last_kind == 'test' else 'مطالعه'}"
        if last_act else "یک جلسه‌ی مطالعه یا تست‌زنی را با زمان‌سنج شروع کن."
    )
    return ft.Container(
        padding=Spacing.lg, border_radius=Radius.lg, bgcolor=SURFACE,
        border=border_all(1, OUTLINE),
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=42, height=42, border_radius=Radius.md,
                    bgcolor=ACCENT_SOFT, alignment=CENTER,
                    content=ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, color=ACCENT, size=24),
                ),
                ft.Column([
                    ft.Text("شروع یک جلسه", size=16, color=ON_SURFACE,
                            weight=ft.FontWeight.W_700, rtl=True),
                    ft.Text("زمان‌سنج خودکار — حتی با جابه‌جایی بین صفحه‌ها حفظ می‌شود",
                            size=10, color=ON_SURFACE_VAR, rtl=True),
                ], spacing=2, expand=True),
                ft.Container(
                    padding=pad_sym(horizontal=9, vertical=5), border_radius=Radius.sm,
                    bgcolor=SURFACE_HIGH,
                    content=ft.Text("آماده", size=10, color=ON_SURFACE_VAR, rtl=True),
                ),
            ], spacing=10),
            ft.Container(height=4),
            ft.Text(hint, size=11, color=ON_SURFACE_VAR, rtl=True),
            filled_button("شروع مطالعه", on_click=lambda _: _open_start_dialog(ctx),
                          icon=ft.Icons.PLAY_ARROW),
        ], spacing=8),
    )


def _active_timer_card(ctx, active) -> ft.Control:
    elapsed = active.elapsed_seconds()
    timer_value = ft.Text(
        _format_elapsed(elapsed), size=32, color=ON_SURFACE,
        weight=ft.FontWeight.W_700, rtl=True, text_align=ft.TextAlign.CENTER,
    )
    is_test = active.kind == "test"
    status_label = "مکث شده" if active.is_paused else "در حال اجرا"
    badge_bg = "#433B2B" if active.is_paused else "#1D332D"
    badge_color = WARN if active.is_paused else SUCCESS

    hint_text = (
        f"{active.activity_name} · {'تست‌زنی' if is_test else 'مطالعه'}"
        + (f" · {active.topic}" if active.topic else "")
    )
    timer_hint = ft.Text(hint_text, size=11, color=ON_SURFACE_VAR, rtl=True,
                         text_align=ft.TextAlign.CENTER)

    # Register the timer text so the loop in main.py updates it once a second.
    ctx._handlers["timer_value"] = timer_value

    test_count_field = None
    if is_test:
        test_count_field = ft.TextField(
            label="تعداد تست انجام‌شده", value=str(active.test_count),
            rtl=True, text_size=13, dense=True, width=180,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: _save_timer_test_count(e.control.value),
        )

    def _finish(_e=None):
        try:
            if is_test and test_count_field is not None:
                study_session.set_test_count(test_count_field.value or "0")
            finished = study_session.finish()
            if finished is None:
                ctx.snack("جلسه‌ی فعالی برای پایان دادن وجود ندارد.")
                ctx.refresh()
                return
            ctx.snack(
                f"{finished.activity_name} · {to_fa(finished.minutes)} دقیقه ذخیره شد."
                + (f" · {to_fa(finished.tests_count)} تست" if finished.tests_count else "")
            )
            ctx.refresh()
        except Exception as exc:
            ctx.snack(f"ذخیره‌ی جلسه ناموفق بود؛ زمان‌سنج حفظ شد: {str(exc)[:90]}")

    def _toggle_pause(_e=None):
        ok = study_session.resume() if active.is_paused else study_session.pause()
        if ok:
            ctx.snack("زمان‌سنج ادامه یافت." if active.is_paused
                      else "زمان‌سنج مکث شد؛ زمان استراحت حساب نمی‌شود.")
            ctx.refresh()
        else:
            ctx.snack("تغییر وضعیت زمان‌سنج انجام نشد.")

    def _ask_cancel(_e=None):
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("جلسه لغو شود؟", size=16, weight=ft.FontWeight.W_700, rtl=True),
            content=ft.Container(
                width=responsive_dialog_width(ctx.page, 340, 260, 48),
                content=ft.Text(
                    "این جلسه هنوز ذخیره نشده است. با لغو، زمان ثبت‌نشده دور ریخته می‌شود.",
                    size=13, color=ON_SURFACE_VAR, rtl=True,
                ),
            ),
            actions=[
                text_button("ادامه‌ی جلسه", on_click=lambda _: ctx.close_dialog(dlg)),
                filled_button("لغو جلسه", on_click=lambda _: _confirm_cancel(ctx, dlg),
                              icon=ft.Icons.DELETE_OUTLINE),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ctx.open_dialog(dlg)

    controls: list[ft.Control] = [
        ft.Row([
            ft.Container(
                width=42, height=42, border_radius=Radius.md,
                bgcolor=ACCENT_SOFT, alignment=CENTER,
                content=ft.Icon(ft.Icons.TIMER_OUTLINED, color=ACCENT, size=23),
            ),
            ft.Column([
                ft.Text("جلسه‌ی فعال", size=15, color=ON_SURFACE,
                        weight=ft.FontWeight.W_700, rtl=True),
                ft.Text("مکث کن یا در پایان ذخیره کن", size=10,
                        color=ON_SURFACE_VAR, rtl=True),
            ], spacing=2, expand=True),
            ft.Container(
                padding=pad_sym(horizontal=9, vertical=5), border_radius=Radius.sm,
                bgcolor=badge_bg,
                content=ft.Text(status_label, size=10, color=badge_color, rtl=True),
            ),
        ], spacing=10),
    ]

    # Pomodoro indicator: show when 25 min reached, suggest a break
    pomodoro_count = elapsed // (25 * 60)
    if pomodoro_count > 0 and not active.is_paused:
        controls.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=6),
            bgcolor="#2A1F14", border_radius=Radius.sm,
            content=ft.Row([
                ft.Icon(ft.Icons.COFFEE_OUTLINED, color=WARN, size=16),
                ft.Text(f"پومودورو {to_fa(pomodoro_count)} کامل شد — ۵ دقیقه استراحت کن",
                        size=11, color=WARN, rtl=True),
            ], spacing=6),
        ))
    controls.append(ft.Container(
        padding=Spacing.md, border_radius=Radius.md, bgcolor=SURFACE_HIGH,
        border=border_all(1, OUTLINE),
        content=ft.Column([
            timer_value, timer_hint,
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    ))
    if test_count_field is not None:
        controls.append(ft.Row([test_count_field], alignment=ft.MainAxisAlignment.CENTER))
    # Row 1: Cancel + Pause (secondary actions, centered)
    controls.append(ft.Row([
        outlined_button("لغو", on_click=_ask_cancel, icon=ft.Icons.CLOSE),
        outlined_button("ادامه" if active.is_paused else "مکث",
                        on_click=_toggle_pause,
                        icon=ft.Icons.PLAY_ARROW if active.is_paused else ft.Icons.PAUSE),
    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER))
    # Row 2: Save & Finish — BIG, full-width, impossible to miss
    controls.append(ft.FilledButton(
        content="پایان و ذخیره",
        icon=ft.Icons.STOP_CIRCLE_OUTLINED,
        on_click=_finish,
        height=52,
        expand=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
    ))

    return ft.Container(
        padding=Spacing.lg, border_radius=Radius.lg, bgcolor=SURFACE,
        border=border_all(1, "#315458"),
        content=ft.Column(controls, spacing=10),
    )


def _save_timer_test_count(value: str) -> None:
    try:
        study_session.set_test_count(value or "0")
    except ValueError:
        # Keep typing fluid — validation happens on save.
        pass


def _open_start_dialog(ctx) -> None:
    activities = models.list_activities(active_only=True)
    if not activities:
        ctx.snack("اول از تنظیمات یک درس اضافه کن.")
        return

    last_id = models.get_setting(study_session.K_LAST_ACTIVITY, "") or ""
    default_id = (last_id if any(str(a.id) == last_id for a in activities)
                  else str(activities[0].id))
    last_kind = models.get_setting(study_session.K_LAST_KIND, "study") or "study"

    activity = ft.Dropdown(
        label="درس یا فعالیت", rtl=True, dense=True, text_size=14,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=default_id, expand=True,
    )
    kind = ft.Dropdown(
        label="نوع جلسه", rtl=True, dense=True, text_size=14,
        options=[ft.DropdownOption(key="study", text="مطالعه"),
                 ft.DropdownOption(key="test", text="تست‌زنی")],
        value=last_kind if last_kind in {"study", "test"} else "study",
        expand=True,
    )
    topic = ft.TextField(
        label="مبحث یا توضیح (اختیاری)", value="", rtl=True,
        text_size=13, dense=True, max_length=140,
    )

    def _start(_e=None):
        try:
            selected_id = int(activity.value or "0")
            selected = next((a for a in activities if a.id == selected_id), None)
            if selected is None:
                ctx.snack("یک درس معتبر انتخاب کن.")
                return
            study_session.start(
                selected.id, selected.name, str(kind.value or "study"),
                str(topic.value or "").strip(),
            )
            ctx.close_dialog(dlg)
            ctx.snack("زمان‌سنج شروع شد.")
            ctx.refresh()
        except Exception as exc:
            ctx.snack(str(exc)[:140])

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("شروع جلسه‌ی جدید", size=17,
                      weight=ft.FontWeight.W_700, rtl=True),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 360, 260, 48),
            content=ft.Column([
                ft.Text("درس و نوع فعالیت را انتخاب کن؛ زمان‌سنج حتی با جابه‌جایی بین صفحه‌ها حفظ می‌شود.",
                        size=12, color=ON_SURFACE_VAR, rtl=True),
                activity, kind, topic,
            ], spacing=11, tight=True, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("شروع زمان‌سنج", on_click=_start, icon=ft.Icons.PLAY_ARROW),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _confirm_cancel(ctx, dlg) -> None:
    ctx.close_dialog(dlg)
    study_session.cancel()
    ctx.snack("جلسه لغو شد و در گزارش ذخیره نشد.")
    ctx.refresh()


def _format_elapsed(seconds: int) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    return to_fa(f"{hours:02d}:{minutes:02d}:{secs:02d}")


# --------------------------------------------------------------------------- #
# Quick stat tiles
# --------------------------------------------------------------------------- #


def _stat_tiles(summary: dict, today) -> ft.Control:
    percent = max(0.0, min(100.0, float(summary.get("goal_percent", 0) or 0)))
    streak = streaks.current_streak(today)
    return ft.Row([
        _stat_tile(ft.Icons.TIMER_OUTLINED, to_fa(summary["minutes"]),
                   "دقیقه امروز", ACCENT),
        _stat_tile(ft.Icons.CHECKLIST_OUTLINED, to_fa(summary["tests"]),
                   "تست امروز", "#65D5C2"),
        _stat_tile(ft.Icons.FLAG_OUTLINED, f"{to_fa(int(percent))}٪",
                   "هدف روزانه", SUCCESS if percent >= 100 else WARN),
        _stat_tile(ft.Icons.LOCAL_FIRE_DEPARTMENT_OUTLINED, to_fa(streak),
                   "روز متوالی", "#F2A65A"),
    ], spacing=6)


def _stat_tile(icon, value: str, caption: str, color: str) -> ft.Control:
    return ft.Container(
        expand=True, padding=Spacing.md, bgcolor=SURFACE, border_radius=Radius.md,
        border=border_all(1, OUTLINE),
        content=ft.Column([
            ft.Row([ft.Icon(icon, size=16, color=color), ft.Container(expand=True)]),
            ft.Text(value, size=20, color=ON_SURFACE,
                    weight=ft.FontWeight.W_700, rtl=True, max_lines=1),
            ft.Text(caption, size=10, color=ON_SURFACE_VAR, rtl=True),
        ], spacing=4),
    )


# --------------------------------------------------------------------------- #
# Next-step card
# --------------------------------------------------------------------------- #


def _next_step_card(summary: dict) -> ft.Control:
    return ft.Container(
        padding=Spacing.lg, border_radius=Radius.md, bgcolor=SURFACE,
        border=border_all(1, OUTLINE),
        content=ft.Row([
            ft.Container(
                width=36, height=36, border_radius=Radius.md,
                bgcolor=ACCENT_SOFT, alignment=CENTER,
                content=ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=ACCENT, size=20),
            ),
            ft.Container(width=12),
            ft.Column([
                ft.Text("قدم بعدی", size=12, color=ON_SURFACE_VAR, rtl=True),
                ft.Text(summary["next_step_text"], size=15, color=ON_SURFACE,
                        rtl=True, weight=ft.FontWeight.W_500, max_lines=3),
            ], spacing=2, expand=True),
        ], spacing=0),
    )


# --------------------------------------------------------------------------- #
# Mini 7-day sparkline
# --------------------------------------------------------------------------- #


def _sparkline_card(weekly: list[tuple[str, int]]) -> ft.Control:
    today_iso = clock_sync.now_local().date().isoformat()
    max_m = max((m for _, m in weekly), default=1) or 1
    bars = []
    for ds, mins in weekly:
        is_today = ds == today_iso
        h = max(4, int(40 * mins / max_m)) if mins > 0 else 4
        color = ACCENT if is_today else "#577A80"
        bars.append(ft.Column([
            ft.Container(width=10, height=h, bgcolor=color, border_radius=3),
        ], alignment=ft.MainAxisAlignment.END,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True))
    total = sum(m for _, m in weekly)
    return ft.Container(
        padding=Spacing.lg, border_radius=Radius.md, bgcolor=SURFACE,
        border=border_all(1, OUTLINE),
        content=ft.Column([
            ft.Row([
                ft.Text("۷ روز اخیر", size=13, color=ON_SURFACE,
                        weight=ft.FontWeight.W_600, rtl=True),
                ft.Container(expand=True),
                ft.Text(f"{to_fa(total)} دقیقه", size=12, color=ACCENT,
                        weight=ft.FontWeight.W_600, rtl=True),
            ]),
            ft.Container(height=6),
            ft.Row(bars, spacing=6, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                   vertical_alignment=ft.CrossAxisAlignment.END, height=48),
        ], spacing=4),
    )


# --------------------------------------------------------------------------- #
# Recent sessions
# --------------------------------------------------------------------------- #


def _recent_sessions_card(sessions) -> ft.Control:
    activities = {a.id: a for a in models.list_activities(active_only=False)}
    recent = sessions[:4]

    controls: list[ft.Control] = [
        ft.Row([
            section_title("جلسات امروز"),
            ft.Container(expand=True),
            ft.Text(f"{to_fa(len(sessions))} مورد", size=11,
                    color=ON_SURFACE_VAR, rtl=True),
        ]),
    ]
    if not recent:
        controls.append(ft.Container(
            padding=Spacing.lg, bgcolor=SURFACE_HIGH, border_radius=Radius.md,
            content=ft.Row([
                ft.Icon(ft.Icons.INBOX_OUTLINED, color=ON_SURFACE_MUT, size=18),
                ft.Container(width=8),
                ft.Text("هنوز چیزی برای امروز ثبت نشده.",
                        size=12, color=ON_SURFACE_MUT, rtl=True),
            ]),
        ))
    else:
        rows = []
        for s in recent:
            act = activities.get(s.activity_id)
            name = act.name if act else "—"
            color = act.color if act and act.color else ACCENT
            sub = f"{to_fa(s.minutes)} دقیقه"
            if s.tests_count:
                sub += f" • {to_fa(s.tests_count)} تست"
            if s.start_time and s.end_time:
                sub = f"{s.start_time}–{s.end_time} • " + sub
            elif s.topic:
                sub += f" • {s.topic}"
            elif s.note:
                sub += f" • {s.note}"
            rows.append(ft.Container(
                padding=pad_sym(horizontal=10, vertical=8), bgcolor=SURFACE_HIGH,
                border_radius=Radius.sm,
                content=ft.Row([
                    ft.Container(width=4, height=24, bgcolor=color, border_radius=2),
                    ft.Container(width=8),
                    ft.Column([
                        ft.Text(name, size=13, color=ON_SURFACE,
                                weight=ft.FontWeight.W_500, rtl=True),
                        ft.Text(sub, size=10, color=ON_SURFACE_VAR, rtl=True,
                                max_lines=1),
                    ], spacing=1, expand=True),
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINED, size=15, color=color),
                ], spacing=0),
            ))
        controls.append(ft.Column(rows, spacing=5))

    return card(controls, padding=Spacing.lg)


# --------------------------------------------------------------------------- #
# Quick actions
# --------------------------------------------------------------------------- #


def _quick_actions(ctx) -> ft.Control:
    def _go_study(_e):
        ctx.set_tab(1)  # ثبت

    def _go_exam(_e):
        ctx.set_tab(3)  # آزمون

    return ft.Row([
        ft.FilledButton(
            content="ثبت مطالعه",
            icon=ft.Icons.MENU_BOOK_OUTLINED,
            on_click=_go_study,
            height=Layout.button_height, expand=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Radius.md)),
        ),
        ft.FilledTonalButton(
            content="ثبت آزمون",
            icon=ft.Icons.SCHOOL_OUTLINED,
            on_click=_go_exam,
            height=Layout.button_height, expand=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Radius.md)),
        ),
    ], spacing=8)
