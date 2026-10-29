"""Study tab — full-featured recording.

Layout:
  1. Quick form (subject + minutes + note) with a collapsible
     "ثبت پیشرفته" section for tests_count, correct/wrong/blank.
  2. Date picker: a TextField showing the Jalali date + "نمایش" button
     to view sessions for any other day.
  3. Session list for the selected day, with edit + delete buttons on
     each row.
  4. 7-day bar chart at the bottom.
"""
from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from services import clock_sync
from core import analytics, models
from core.fa_dates import ascii_digits, format_jalali, normalize_date, jalali_label
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    CENTER, border_all, card, divider, filled_button, outlined_button,
    pad_sym, section_title, text_button, to_fa,
    responsive_dialog_width, responsive_dialog_height,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    sessions = models.list_sessions_for_date(today.isoformat())
    last7 = analytics.last_7_days_minutes(today)

    # The list section is rendered into a mutable container so the date
    # picker can swap its contents without rebuilding the whole tab.
    date_field = ft.TextField(
        label="مشاهده‌ی تاریخ شمسی", rtl=True, text_size=12, dense=True,
        value=format_jalali(today.isoformat()), expand=True,
        hint_text="۱۴۰۵-۰۸-۰۶",
    )
    list_title = ft.Text(
        f"جلسات {jalali_label(today.isoformat())} ({to_fa(len(sessions))})",
        size=14, weight=ft.FontWeight.W_600, color=ON_SURFACE, rtl=True,
    )
    list_view = ft.Container(content=_sessions_list(ctx, sessions))

    def _show_date(_e=None):
        try:
            selected = normalize_date(date_field.value)
        except ValueError as exc:
            ctx.snack(str(exc))
            return
        found = models.list_sessions_for_date(selected)
        list_title.value = (
            f"جلسات {jalali_label(selected)} ({to_fa(len(found))})"
        )
        list_view.content = _sessions_list(ctx, found)
        try:
            ctx.page.update()
        except Exception:
            pass

    date_field.on_submit = _show_date

    return ft.ListView(
        [
            ft.Container(height=8),
            section_title("مطالعه"),
            ft.Container(height=12),
            _form_card(ctx, today),
            ft.Container(height=12),
            ft.Row([list_title], alignment=ft.MainAxisAlignment.START),
            ft.Row([
                date_field,
                outlined_button("نمایش", on_click=_show_date,
                                icon=ft.Icons.CALENDAR_MONTH_OUTLINED),
            ], spacing=8, wrap=True),
            ft.Container(height=6),
            list_view,
            ft.Container(height=12),
            _week_chart_card(today, last7),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Form (quick + advanced collapsible section)
# --------------------------------------------------------------------------- #


def _form_card(ctx, today) -> ft.Control:
    activities = models.list_activities(active_only=True)
    if not activities:
        return card([
            ft.Text("اول از تنظیمات یک درس اضافه کن.",
                    size=14, color=ON_SURFACE_VAR, rtl=True),
        ], padding=16)

    subject = ft.Dropdown(
        label="فعالیت", rtl=True, text_size=15, dense=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(activities[0].id), expand=True,
    )
    minutes = ft.TextField(
        label="دقیقه", rtl=True, text_size=15, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value="25", width=100,
    )
    note = ft.TextField(
        label="یادداشت (اختیاری)", rtl=True, text_size=14, dense=True,
        max_length=140, expand=True,
    )

    # Collapsible advanced section — tests_count + correct/wrong/blank.
    adv_tests = ft.TextField(
        label="کل تست", rtl=True, text_size=13, dense=True, width=80,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(), value="0",
    )
    adv_correct = ft.TextField(
        label="درست", rtl=True, text_size=13, dense=True, width=70,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(), value="0",
    )
    adv_wrong = ft.TextField(
        label="غلط", rtl=True, text_size=13, dense=True, width=70,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(), value="0",
    )
    adv_blank = ft.TextField(
        label="نزده", rtl=True, text_size=13, dense=True, width=70,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(), value="0",
    )
    adv_topic = ft.TextField(
        label="مبحث (اختیاری)", rtl=True, text_size=13, dense=True,
        expand=True, max_length=80,
    )

    advanced_tile = ft.ExpansionTile(
        title=ft.Text("ثبت پیشرفته", size=13, color=ON_SURFACE,
                      weight=ft.FontWeight.W_600, rtl=True),
        subtitle=ft.Text("تعداد تست، درست/غلط/نزده و مبحث", size=10,
                         color=ON_SURFACE_MUT, rtl=True),
        leading=ft.Icon(ft.Icons.TUNE_OUTLINED, color=ACCENT, size=18),
        controls=[
            ft.Container(
                padding=pad_sym(horizontal=4, vertical=4),
                content=ft.Column([
                    ft.Row([adv_tests, adv_correct, adv_wrong, adv_blank],
                           spacing=6, wrap=True),
                    adv_topic,
                    ft.Text("اگر مجموع درست+غلط+نزده بیشتر از کل تست باشد، کل تست خودکار اصلاح می‌شود.",
                            size=10, color=ON_SURFACE_MUT, rtl=True),
                ], spacing=6),
            ),
        ],
        controls_padding=pad_sym(horizontal=4, vertical=4),
        tile_padding=pad_sym(horizontal=4, vertical=2),
        bgcolor=SURFACE_HIGH,
        collapsed_bgcolor=SURFACE_HIGH,
        shape=ft.RoundedRectangleBorder(radius=8),
        collapsed_shape=ft.RoundedRectangleBorder(radius=8),
        expanded=False,
    )

    def _save(_e=None):
        try:
            act_id = int(subject.value) if subject.value else 0
            mins = int(ascii_digits(minutes.value or "0") or 0)
        except (TypeError, ValueError):
            ctx.snack("عدد معتبر وارد کن.")
            return
        if not act_id or mins <= 0:
            ctx.snack("فعالیت و دقیقه را پر کن.")
            return
        try:
            tcount = max(0, int(ascii_digits(adv_tests.value or "0") or 0))
            corr = max(0, int(ascii_digits(adv_correct.value or "0") or 0))
            wrng = max(0, int(ascii_digits(adv_wrong.value or "0") or 0))
            blnk = max(0, int(ascii_digits(adv_blank.value or "0") or 0))
        except (TypeError, ValueError):
            ctx.snack("عدد تست معتبر نیست.")
            return
        if corr + wrng + blnk > tcount:
            tcount = corr + wrng + blnk
        topic = (adv_topic.value or "").strip()

        try:
            models.create_session(
                date_str=today.isoformat(),
                activity_id=act_id,
                minutes=mins,
                tests_count=tcount,
                correct_count=corr, wrong_count=wrng, blank_count=blnk,
                topic=topic,
                note=(note.value or "").strip() or None,
            )
        except Exception as exc:
            ctx.snack(f"ثبت انجام نشد: {str(exc)[:140]}")
            return

        # Reset for the next entry.
        minutes.value = "25"
        note.value = ""
        adv_tests.value = "0"
        adv_correct.value = "0"
        adv_wrong.value = "0"
        adv_blank.value = "0"
        adv_topic.value = ""
        ctx.snack("ثبت شد.")
        ctx.refresh()

    return card([
        ft.Row([subject], alignment=ft.MainAxisAlignment.START),
        ft.Container(height=8),
        ft.Row([minutes], alignment=ft.MainAxisAlignment.START),
        ft.Container(height=8),
        note,
        ft.Container(height=8),
        advanced_tile,
        ft.Container(height=8),
        filled_button("ثبت", on_click=_save, icon=ft.Icons.SAVE_OUTLINED),
    ], padding=16)


# --------------------------------------------------------------------------- #
# Sessions list for a given day
# --------------------------------------------------------------------------- #


def _sessions_list(ctx, sessions) -> ft.Control:
    if not sessions:
        # Clean empty state — transparent background, blends with page
        return ft.Container(
            padding=20,
            alignment=CENTER,
            content=ft.Column([
                ft.Icon(ft.Icons.INBOX_OUTLINED, color=ON_SURFACE_MUT, size=32),
                ft.Text("هنوز چیزی ثبت نکردی.",
                        size=14, color=ON_SURFACE_MUT, rtl=True,
                        weight=ft.FontWeight.W_500),
                ft.Text("با دکمه + شروع کن.",
                        size=12, color=ON_SURFACE_MUT, rtl=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        )
    activities = {a.id: a for a in models.list_activities(active_only=False)}
    rows = []
    for s in sessions:
        rows.append(_session_row(ctx, s, activities.get(s.activity_id)))
    return ft.Column(rows, spacing=6)


def Spacing_md():
    return pad_sym(horizontal=20, vertical=18)


def _session_row(ctx, s, act) -> ft.Control:
    name = act.name if act else "—"
    color = act.color if act and act.color else ACCENT
    sub = f"{to_fa(s.minutes)} دقیقه"
    if s.tests_count:
        sub += f" • {to_fa(s.tests_count)} تست"
    answered = int(getattr(s, "correct_count", 0) or 0) + int(getattr(s, "wrong_count", 0) or 0)
    if answered:
        sub += f" • درست {to_fa(getattr(s, 'correct_count', 0))} / غلط {to_fa(getattr(s, 'wrong_count', 0))}"
    if getattr(s, "start_time", None) and getattr(s, "end_time", None):
        sub = f"{s.start_time} تا {s.end_time} • " + sub
    topic = getattr(s, "topic", "") or ""
    if topic:
        sub += f" • {topic}"
    if s.note:
        sub += f" • {s.note}"

    def _edit(_e):
        _open_edit_dialog(ctx, s)

    def _delete(_e):
        _open_delete_dialog(ctx, s)

    return ft.Container(
        padding=pad_sym(horizontal=12, vertical=10),
        bgcolor=SURFACE, border_radius=10, border=border_all(1, OUTLINE),
        content=ft.Row([
            ft.Container(width=4, height=36, bgcolor=color, border_radius=2),
            ft.Container(width=8),
            ft.Column([
                ft.Text(name, size=14, color=ON_SURFACE,
                        weight=ft.FontWeight.W_500, rtl=True),
                ft.Text(sub, size=11, color=ON_SURFACE_VAR, rtl=True, max_lines=2),
            ], spacing=2, expand=True),
            ft.Row([
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED, icon_size=18,
                    tooltip="ویرایش", on_click=_edit,
                    style=ft.ButtonStyle(color=ON_SURFACE_VAR),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE, icon_size=18,
                    tooltip="حذف", on_click=_delete,
                    style=ft.ButtonStyle(color=ON_SURFACE_VAR),
                ),
            ], spacing=0),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    )


# --------------------------------------------------------------------------- #
# Edit dialog
# --------------------------------------------------------------------------- #


def _open_edit_dialog(ctx, s) -> None:
    activities = models.list_activities(active_only=True)
    if not any(a.id == s.activity_id for a in activities):
        act = models.get_activity(s.activity_id)
        if act:
            activities = [act, *activities]

    subject = ft.Dropdown(
        label="فعالیت", rtl=True, text_size=14, dense=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(s.activity_id), expand=True,
    )
    minutes = ft.TextField(
        label="دقیقه", rtl=True, text_size=14, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value=str(s.minutes), width=90,
    )
    tests = ft.TextField(
        label="کل تست", rtl=True, text_size=13, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value=str(getattr(s, "tests_count", 0) or 0), width=80,
    )
    correct = ft.TextField(
        label="درست", rtl=True, text_size=13, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value=str(getattr(s, "correct_count", 0) or 0), width=70,
    )
    wrong = ft.TextField(
        label="غلط", rtl=True, text_size=13, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value=str(getattr(s, "wrong_count", 0) or 0), width=70,
    )
    blank = ft.TextField(
        label="نزده", rtl=True, text_size=13, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.NumbersOnlyInputFilter(),
        value=str(getattr(s, "blank_count", 0) or 0), width=70,
    )
    topic = ft.TextField(
        label="مبحث", rtl=True, text_size=13, dense=True,
        value=getattr(s, "topic", "") or "", expand=True, max_length=80,
    )
    note = ft.TextField(
        label="یادداشت", rtl=True, text_size=14, dense=True,
        value=s.note or "", expand=True, max_length=140,
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("ویرایش جلسه", rtl=True, size=16,
                      weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 340),
            content=ft.Column([
                subject,
                ft.Row([minutes, tests], spacing=10),
                ft.Row([correct, wrong, blank], spacing=6),
                topic,
                note,
            ], spacing=10, tight=True, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("ذخیره", on_click=lambda _: _save_edit(
                ctx, dlg, s, subject, minutes, tests, correct, wrong, blank, topic, note)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _save_edit(ctx, dlg, s, subject, minutes, tests, correct, wrong, blank, topic, note) -> None:
    try:
        act_id = int(subject.value) if subject.value else 0
        mins = int(ascii_digits(minutes.value or "0") or 0)
        tcount = int(ascii_digits(tests.value or "0") or 0)
        corr = int(ascii_digits(correct.value or "0") or 0)
        wrng = int(ascii_digits(wrong.value or "0") or 0)
        blnk = int(ascii_digits(blank.value or "0") or 0)
    except (TypeError, ValueError):
        ctx.snack("عدد معتبر وارد کن.")
        return
    if not act_id or mins <= 0:
        ctx.snack("فعالیت و دقیقه را درست وارد کن.")
        return
    if min(tcount, corr, wrng, blnk) < 0:
        ctx.snack("اعداد نمی‌توانند منفی باشند.")
        return
    if corr + wrng + blnk > tcount:
        tcount = corr + wrng + blnk

    try:
        models.update_session(
            s.id,
            activity_id=act_id,
            minutes=mins,
            tests_count=tcount,
            correct_count=corr, wrong_count=wrng, blank_count=blnk,
            topic=(topic.value or "").strip(),
            note=(note.value or "").strip(),
        )
    except Exception as exc:
        ctx.snack(f"ذخیره انجام نشد: {str(exc)[:140]}")
        return
    ctx.close_dialog(dlg)
    ctx.snack("به‌روز شد.")
    ctx.refresh()


# --------------------------------------------------------------------------- #
# Delete dialog
# --------------------------------------------------------------------------- #


def _open_delete_dialog(ctx, s) -> None:
    act = models.get_activity(s.activity_id)
    name = act.name if act else "این جلسه"
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("حذف جلسه", rtl=True, size=16,
                      weight=ft.FontWeight.W_600),
        content=ft.Text(
            f"«{name}» ({to_fa(s.minutes)} دقیقه) حذف شود؟",
            rtl=True, size=14, color=ON_SURFACE_VAR),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("حذف", on_click=lambda _: _do_delete(ctx, dlg, s),
                          icon=ft.Icons.DELETE_OUTLINE),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _do_delete(ctx, dlg, s) -> None:
    models.delete_session(s.id)
    ctx.close_dialog(dlg)
    ctx.snack("حذف شد.")
    ctx.refresh()


# --------------------------------------------------------------------------- #
# 7-day chart
# --------------------------------------------------------------------------- #


def _week_chart_card(today, last7) -> ft.Control:
    fa_weekdays = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
    max_m = max((m for _, m in last7), default=60) or 60
    PLOT_H = 100
    today_iso = today.isoformat()

    cols = []
    for date_str, mins in last7:
        d = date.fromisoformat(date_str)
        wd = fa_weekdays[(d.weekday() + 2) % 7]
        is_today = date_str == today_iso
        h = max(2, int(PLOT_H * mins / max_m)) if mins > 0 else 2
        cols.append(ft.Column([
            ft.Text(to_fa(mins) if mins > 0 else "", size=9,
                    color=ON_SURFACE_MUT, text_align=ft.TextAlign.CENTER),
            ft.Container(width=20, height=h,
                         bgcolor=ACCENT if is_today else "#577A80",
                         border_radius=4),
            ft.Container(height=4),
            ft.Text(wd, size=11, color=ON_SURFACE if is_today else ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    total = sum(m for _, m in last7)
    sentence = f"مجموع ۷ روز: {to_fa(total)} دقیقه" if total > 0 else "هنوز ثبت نشده"

    return card([
        section_title("۷ روز اخیر"),
        ft.Container(height=8),
        ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ft.Container(height=6),
        ft.Text(sentence, size=12, color=ON_SURFACE_VAR, rtl=True),
    ], padding=16)
