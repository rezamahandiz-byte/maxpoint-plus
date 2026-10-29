"""Record tab — quick form + today's sessions list with edit/delete.

Form fields:
    - subject (Dropdown of active activities)
    - minutes (TextField, digits only)
    - tests count (TextField, optional)
    - note (TextField, optional)

A separate FAB on Home and Record opens a compact quick-record dialog
reusing the same form fields. After save, the current tab refreshes.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import flet as ft

from services import clock_sync

from core import models
from core.fa_dates import ascii_digits, format_jalali, normalize_date, jalali_label
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, OUTLINE,
    SURFACE, SURFACE_HIGH, WARN,
    card, divider, filled_button, label, margin_only, outlined_button,
    pad_sym, section_title, text_button, to_fa, responsive_dialog_width, responsive_dialog_height,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    sessions = models.list_sessions_for_date(today.isoformat())
    title = section_title(f"جلسات {jalali_label(today.isoformat())} ({to_fa(len(sessions))})")
    sessions_view = ft.Container(content=_today_sessions_list(ctx, sessions))
    date_field = ft.TextField(
        label="مشاهده‌ی تاریخ شمسی", rtl=True, text_size=12, dense=True,
        value=format_jalali(today.isoformat()), expand=True, hint_text="۱۴۰۵-۰۸-۰۶",
    )

    def _show_date(_e=None):
        try:
            selected_date = normalize_date(date_field.value)
            found = models.list_sessions_for_date(selected_date)
            title.value = f"جلسات {jalali_label(selected_date)} ({to_fa(len(found))})"
            sessions_view.content = _today_sessions_list(ctx, found)
            ctx.page.update()
        except ValueError as exc:
            ctx.snack(str(exc))

    date_field.on_submit = _show_date
    return ft.ListView(bgcolor=ft.Colors.TRANSPARENT, 
        [
            ft.Container(height=4),
            section_title("ثبت سریع"),
            ft.Container(height=8),
            _quick_form_card(ctx, today),
            ft.Container(height=14),
            ft.Row([title], alignment=ft.MainAxisAlignment.START),
            ft.Row([date_field, outlined_button("نمایش", on_click=_show_date, icon=ft.Icons.CALENDAR_MONTH_OUTLINED)], spacing=8, wrap=True),
            ft.Container(height=6),
            sessions_view,
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Quick form
# --------------------------------------------------------------------------- #


def _quick_form_card(ctx, today: date) -> ft.Control:
    activities = models.list_activities(active_only=True)
    if not activities:
        return card([
            ft.Text("هنوز درسی تعریف نشده. از تنظیمات → مدیریت دروس اضافه کن.",
                    size=13, color=ON_SURFACE_VAR, rtl=True),
        ], padding=16)

    subject = ft.Dropdown(
        label="درس",
        rtl=True,
        text_size=14,
        dense=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(activities[0].id),
        expand=True,
    )
    minutes = ft.TextField(
        label="دقیقه",
        rtl=True,
        text_size=14,
        dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        value="25",
        width=90,
    )
    tests = ft.TextField(
        label="آزمون",
        rtl=True,
        text_size=14,
        dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        value="0",
        width=80,
    )
    note = ft.TextField(
        label="یادداشت (اختیاری)",
        rtl=True,
        text_size=14,
        dense=True,
        max_length=140,
        expand=True,
    )

    def _save(_e=None):
        try:
            act_id = int(subject.value) if subject.value else 0
            mins = int(ascii_digits(minutes.value or "0") or 0)
            tcount = int(ascii_digits(tests.value or "0") or 0)
        except (TypeError, ValueError):
            ctx.snack("عدد معتبر وارد کن.")
            return
        if not act_id or mins <= 0 or tcount < 0:
            ctx.snack("درس و دقیقه را درست وارد کن؛ تعداد تست نمی‌تواند منفی باشد.")
            return
        try:
            models.create_session(
                date_str=today.isoformat(),
                activity_id=act_id,
                minutes=mins,
                tests_count=tcount,
                note=(note.value or "").strip() or None,
            )
        except Exception as exc:
            ctx.snack(f"ثبت انجام نشد: {str(exc)[:160]}")
            return
        # Reset for next entry
        minutes.value = "25"
        tests.value = "0"
        note.value = ""
        ctx.snack("ثبت شد.")
        ctx.refresh()

    save_btn = filled_button("ثبت جلسه", on_click=_save,
                             icon=ft.Icons.SAVE_OUTLINED)

    return card(
        [
            ft.Row([subject], alignment=ft.MainAxisAlignment.START),
            ft.Row(
                [minutes, tests],
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
            ),
            note,
            ft.Row(
                [
                    outlined_button("ثبت پیشرفته", on_click=lambda _: open_advanced_record(ctx), icon=ft.Icons.TUNE_OUTLINED),
                    save_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
                spacing=8,
            ),
        ],
        padding=14,
    )


# --------------------------------------------------------------------------- #
# Today list
# --------------------------------------------------------------------------- #


def _today_sessions_list(ctx, sessions: list) -> ft.Control:
    if not sessions:
        return ft.Container(
            padding=20,
            bgcolor=SURFACE,
            border_radius=12,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.INBOX_OUTLINED,
                            color=ON_SURFACE_VAR, size=28),
                    ft.Text("امروز چیزی ثبت نشده.",
                            size=13, color=ON_SURFACE_VAR, rtl=True),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    activities = {a.id: a for a in models.list_activities(active_only=False)}
    rows: list[ft.Control] = []
    for s in sessions:
        rows.append(_session_row(ctx, s, activities.get(s.activity_id)))
    return ft.Column(rows, spacing=6)


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
    if getattr(s, "topic", ""):
        sub += f" • {s.topic}"
    if s.note:
        sub += f" • {s.note}"

    def _edit(_e):
        _open_edit_dialog(ctx, s)

    def _delete(_e):
        _open_delete_dialog(ctx, s)

    return ft.Container(
        padding=pad_sym(horizontal=12, vertical=10),
        bgcolor=SURFACE,
        border_radius=10,
        content=ft.Row(
            [
                ft.Container(width=4, height=36, bgcolor=color,
                             border_radius=2),
                ft.Column(
                    [
                        ft.Text(name, size=14, color=ON_SURFACE,
                                weight=ft.FontWeight.W_500, rtl=True),
                        ft.Text(sub, size=11, color=ON_SURFACE_VAR, rtl=True),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Row(
                    [
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
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


# --------------------------------------------------------------------------- #
# Dialogs
# --------------------------------------------------------------------------- #


def _open_edit_dialog(ctx, s) -> None:
    activities = models.list_activities(active_only=True)
    # If the session's activity is now inactive, include it anyway so the
    # dropdown doesn't lose its value.
    if not any(a.id == s.activity_id for a in activities):
        act = models.get_activity(s.activity_id)
        if act:
            activities = [act, *activities]

    subject = ft.Dropdown(
        label="درس",
        rtl=True,
        text_size=14,
        dense=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(s.activity_id),
        expand=True,
    )
    minutes = ft.TextField(
        label="دقیقه", rtl=True, text_size=14, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        
        value=str(s.minutes), width=90,
    )
    tests = ft.TextField(
        label="آزمون", rtl=True, text_size=14, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        
        value=str(s.tests_count), width=80,
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
            width=responsive_dialog_width(ctx.page, 320),
            content=ft.Column(
                [subject, ft.Row([minutes, tests], spacing=10), note],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("ذخیره", on_click=lambda _: _save_edit(
                ctx, dlg, s, subject, minutes, tests, note)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _save_edit(ctx, dlg, s, subject, minutes, tests, note) -> None:
    try:
        act_id = int(subject.value) if subject.value else 0
        mins = int(ascii_digits(minutes.value or "0") or 0)
        tcount = int(ascii_digits(tests.value or "0") or 0)
    except (TypeError, ValueError):
        ctx.snack("عدد معتبر وارد کن.")
        return
    if not act_id or mins <= 0 or tcount < 0:
        ctx.snack("درس و دقیقه را درست وارد کن؛ تعداد تست نمی‌تواند منفی باشد.")
        return
    models.update_session(
        s.id,
        activity_id=act_id,
        minutes=mins,
        tests_count=tcount,
        note=(note.value or "").strip(),
    )
    ctx.close_dialog(dlg)
    ctx.snack("به‌روز شد.")
    ctx.refresh()


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
# Quick record dialog (opened from FAB on Home/Record)
# --------------------------------------------------------------------------- #


def open_quick_record(ctx) -> None:
    """Open a compact record dialog from the FAB."""
    today = clock_sync.now_local().date()
    activities = models.list_activities(active_only=True)
    if not activities:
        ctx.snack("اول یک درس در تنظیمات اضافه کن.")
        return

    subject = ft.Dropdown(
        label="درس", rtl=True, text_size=14, dense=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(activities[0].id),
        expand=True,
    )
    minutes = ft.TextField(
        label="دقیقه", rtl=True, text_size=14, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        
        value="25", width=90,
    )
    tests = ft.TextField(
        label="آزمون", rtl=True, text_size=14, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        
        value="0", width=80,
    )
    note = ft.TextField(
        label="یادداشت (اختیاری)", rtl=True, text_size=14, dense=True,
        max_length=140, expand=True,
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("ثبت سریع", rtl=True, size=16,
                      weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 320),
            content=ft.Column(
                [subject, ft.Row([minutes, tests], spacing=10), note],
                spacing=10, tight=True,
            ),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("ثبت", on_click=lambda _: _save_quick(
                ctx, dlg, today, subject, minutes, tests, note),
                icon=ft.Icons.SAVE_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _save_quick(ctx, dlg, today, subject, minutes, tests, note) -> None:
    try:
        act_id = int(subject.value) if subject.value else 0
        mins = int(ascii_digits(minutes.value or "0") or 0)
        tcount = int(ascii_digits(tests.value or "0") or 0)
    except (TypeError, ValueError):
        ctx.snack("عدد معتبر وارد کن.")
        return
    if not act_id or mins <= 0 or tcount < 0:
        ctx.snack("درس و دقیقه را درست وارد کن؛ تعداد تست نمی‌تواند منفی باشد.")
        return
    models.create_session(
        date_str=today.isoformat(),
        activity_id=act_id,
        minutes=mins,
        tests_count=tcount,
        note=(note.value or "").strip() or None,
    )
    ctx.close_dialog(dlg)
    ctx.snack("ثبت شد.")
    ctx.refresh()


# --------------------------------------------------------------------------- #
# Advanced session form — Jalali date, time range, subject/topic and test quality
# --------------------------------------------------------------------------- #

def open_advanced_record(ctx) -> None:
    activities = models.list_activities(active_only=True)
    if not activities:
        ctx.snack("اول یک فعالیت در تنظیمات تعریف کن.")
        return

    activity = ft.Dropdown(
        label="فعالیت", rtl=True, text_size=13, dense=True, expand=True,
        options=[ft.DropdownOption(key=str(a.id), text=a.name) for a in activities],
        value=str(activities[0].id),
    )
    date_field = ft.TextField(
        label="تاریخ شمسی (سال-ماه-روز)", rtl=True, text_size=13, dense=True,
        value=format_jalali(clock_sync.now_local().date().isoformat()), hint_text="۱۴۰۵-۰۸-۰۶",
    )
    minutes = ft.TextField(
        label="مدت (دقیقه)", rtl=True, text_size=13, dense=True, width=112, value="25",
        keyboard_type=ft.KeyboardType.NUMBER, 
    )
    start = ft.TextField(label="شروع (اختیاری)", rtl=True, text_size=13, dense=True, width=126, hint_text="09:00")
    end = ft.TextField(label="پایان (اختیاری)", rtl=True, text_size=13, dense=True, width=126, hint_text="09:45")
    tests = ft.TextField(label="کل تست", rtl=True, text_size=13, dense=True, width=88, value="0", keyboard_type=ft.KeyboardType.NUMBER, )
    correct = ft.TextField(label="درست", rtl=True, text_size=13, dense=True, width=78, value="0", keyboard_type=ft.KeyboardType.NUMBER, )
    wrong = ft.TextField(label="غلط", rtl=True, text_size=13, dense=True, width=78, value="0", keyboard_type=ft.KeyboardType.NUMBER, )
    blank = ft.TextField(label="نزده", rtl=True, text_size=13, dense=True, width=78, value="0", keyboard_type=ft.KeyboardType.NUMBER, )
    topic = ft.TextField(label="مبحث / نوع فعالیت", rtl=True, text_size=13, dense=True, hint_text="مثلاً حد و پیوستگی")
    test_type = ft.Dropdown(
        label="نوع کار", rtl=True, text_size=13, dense=True, expand=True, value="practice",
        options=[ft.DropdownOption(key="practice", text="تمرین و مطالعه"),
                 ft.DropdownOption(key="timed", text="تست زمان‌دار"),
                 ft.DropdownOption(key="review", text="تحلیل و مرور"),
                 ft.DropdownOption(key="exam", text="آزمون")],
    )
    note = ft.TextField(label="یادداشت (اختیاری)", rtl=True, text_size=13, dense=True, multiline=True, min_lines=2, max_lines=4, max_length=500)

    def _parse_int(field, name):
        raw = ascii_digits(field.value or "0").strip() or "0"
        try: value = int(raw)
        except ValueError as exc: raise ValueError(f"فیلد «{name}» باید عدد صحیح باشد.") from exc
        if value < 0: raise ValueError(f"فیلد «{name}» نمی‌تواند منفی باشد.")
        return value

    def _persist(values):
        try:
            models.create_session(**values)
        except Exception as exc:
            ctx.snack(f"ثبت انجام نشد: {str(exc)[:160]}")
            return
        try: ctx.close_dialog(dlg)
        except Exception: pass
        ctx.snack("فعالیت با جزئیات ذخیره شد.")
        ctx.refresh()

    def _save(_e=None):
        try:
            activity_id = int(activity.value or 0)
            date_str = normalize_date(date_field.value)
            start_time = ascii_digits(start.value or "").strip()
            end_time = ascii_digits(end.value or "").strip()
            if bool(start_time) != bool(end_time):
                raise ValueError("برای ثبت زمان، ساعت شروع و پایان را هر دو وارد کن.")
            minutes_value = _parse_int(minutes, "مدت")
            if start_time and end_time:
                def to_minutes(v):
                    parts=v.split(":")
                    if len(parts)!=2: raise ValueError("ساعت باید به شکل 09:30 باشد.")
                    h,m=map(int,parts)
                    if not (0<=h<=23 and 0<=m<=59): raise ValueError("ساعت واردشده معتبر نیست.")
                    return h*60+m
                delta=to_minutes(end_time)-to_minutes(start_time)
                if delta==0: raise ValueError("ساعت شروع و پایان نمی‌توانند یکسان باشند.")
                if delta<0: delta += 1440
                minutes_value=delta
            if minutes_value<=0: raise ValueError("مدت باید بیشتر از صفر باشد.")
            test_count=_parse_int(tests, "کل تست")
            correct_count=_parse_int(correct, "درست")
            wrong_count=_parse_int(wrong, "غلط")
            blank_count=_parse_int(blank, "نزده")
            if correct_count+wrong_count+blank_count>test_count:
                test_count=correct_count+wrong_count+blank_count
                tests.value=str(test_count)
            values=dict(
                date_str=date_str, activity_id=activity_id, minutes=minutes_value,
                tests_count=test_count, correct_count=correct_count, wrong_count=wrong_count,
                blank_count=blank_count, start_time=start_time or None, end_time=end_time or None,
                topic=(topic.value or "").strip(), test_type=(test_type.value or "practice"),
                note=(note.value or "").strip() or None,
            )
            if start_time and end_time:
                overlaps=models.find_session_overlaps(date_str,start_time,end_time)
                if overlaps:
                    names=[]
                    for item in overlaps[:3]:
                        act=models.get_activity(item.activity_id)
                        names.append(f"{act.name if act else 'فعالیت دیگر'} ({item.start_time} تا {item.end_time})")
                    overlap_dlg=ft.AlertDialog(
                        modal=True,
                        title=ft.Text("هم‌پوشانی زمان",rtl=True,size=16,weight=ft.FontWeight.W_600),
                        content=ft.Container(width=responsive_dialog_width(ctx.page, 320),content=ft.Column([
                            ft.Text("این بازه با ثبت قبلی هم‌پوشانی دارد:",rtl=True,size=13),
                            ft.Text("\n".join(names),rtl=True,size=12,color=ON_SURFACE_VAR),
                            ft.Text("اگر فعالیت‌ها واقعاً هم‌زمان بوده‌اند، می‌توانی با آگاهی ادامه بدهی.",rtl=True,size=12),
                        ],tight=True,spacing=8)),
                        actions=[
                            text_button("برگشت به فرم",on_click=lambda _:ctx.close_dialog(overlap_dlg)),
                            filled_button("ثبت با وجود هم‌پوشانی",on_click=lambda _: (ctx.close_dialog(overlap_dlg),_persist(values))),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    ctx.open_dialog(overlap_dlg)
                    return
            _persist(values)
        except ValueError as exc:
            ctx.snack(str(exc))
        except Exception as exc:
            ctx.snack(f"خطا در آماده‌سازی ثبت: {str(exc)[:150]}")

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("ثبت پیشرفته‌ی فعالیت",rtl=True,size=16,weight=ft.FontWeight.W_600),
        content=ft.Container(width=responsive_dialog_width(ctx.page, 350),height=responsive_dialog_height(ctx.page, 500),content=ft.Column([
            activity, date_field,
            ft.Row([minutes, start, end],spacing=6,wrap=True),
            test_type, topic,
            ft.Text("نتیجه‌ی تست‌ها",rtl=True,size=12,color=ON_SURFACE_VAR),
            ft.Row([tests,correct,wrong,blank],spacing=5,wrap=True),
            note,
        ],spacing=10,scroll=ft.ScrollMode.AUTO)),
        actions=[
            text_button("انصراف",on_click=lambda _:ctx.close_dialog(dlg)),
            filled_button("ذخیره فعالیت",on_click=_save,icon=ft.Icons.SAVE_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)
