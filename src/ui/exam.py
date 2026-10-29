"""Exam tab — full exam management.

Layout:
  1. Add button card → opens dialog (number, date, taraz, rank +
     per-subject percent/correct/wrong/blank)
  2. Taraz trend chart (keep)
  3. Subject average card — average percent per subject across all exams
  4. Exam list (newest first); tapping a row opens a detail dialog with
     the full subject breakdown; each row also has edit + delete buttons.

The advanced exam entry dialog allows entering percent AND correct/wrong/
blank for each subject (correct+wrong+blank are optional).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import flet as ft

from services import clock_sync
from core import analytics, models
from core.fa_dates import ascii_digits, format_jalali, normalize_date, jalali_label
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    CENTER, card, divider, filled_button, outlined_button,
    pad_sym, section_title, text_button, to_fa, border_all,
    responsive_dialog_width, responsive_dialog_height,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    series = analytics.exam_taraz_series()
    exams = list(reversed(models.list_exams()))  # newest first

    return ft.ListView(
        [
            ft.Container(height=8),
            section_title("آزمون"),
            ft.Container(height=12),
            _add_button_card(ctx),
            ft.Container(height=12),
            _taraz_card(series),
            ft.Container(height=12),
            _subject_average_card(),
            ft.Container(height=12),
            _exam_list_card(ctx, exams),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Add button
# --------------------------------------------------------------------------- #


def _add_button_card(ctx) -> ft.Control:
    return card([
        ft.Row([
            ft.Column([
                ft.Text("آزمون خودآزمایی را ثبت کن", size=14, color=ON_SURFACE,
                        rtl=True),
                ft.Text("شماره، تراز و درصد هر درس با اختیاری بودن درست/غلط/نزده",
                        size=11, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=2, expand=True),
            filled_button("ثبت آزمون", on_click=lambda _: _open_dialog(ctx),
                          icon=ft.Icons.ADD),
        ], spacing=8),
    ], padding=16)


# --------------------------------------------------------------------------- #
# Taraz chart
# --------------------------------------------------------------------------- #


def _taraz_card(series) -> ft.Control:
    if not series:
        return card([
            section_title("روند تراز"),
            ft.Container(height=8),
            ft.Text("هنوز آزمونی ثبت نشده.", size=14, color=ON_SURFACE_MUT, rtl=True),
        ], padding=16)

    n = len(series)
    ys = [t for _, t in series]
    y_min, y_max = min(ys), max(ys)
    if y_max == y_min:
        y_max = y_min + 1
    PLOT_H = 100
    max_t = y_max

    cols = []
    for exam_num, taraz in series:
        h = max(4, int(PLOT_H * taraz / max_t)) if max_t > 0 else 4
        cols.append(ft.Column([
            ft.Text(to_fa(taraz), size=9, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(width=20, height=h, bgcolor=ACCENT, border_radius=4),
            ft.Container(height=4),
            ft.Text(to_fa(exam_num), size=11, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    # Trend sentence
    sentence = ""
    if len(series) >= 2:
        first_n, first_t = series[0]
        last_n, last_t = series[-1]
        diff = last_t - first_t
        if diff == 0:
            sentence = f"تراز از آزمون {to_fa(first_n)} تا {to_fa(last_n)} ثابت بوده."
        else:
            direction = "افزایش" if diff > 0 else "کاهش"
            sentence = (f"تراز از آزمون {to_fa(first_n)} تا {to_fa(last_n)} "
                        f"{to_fa(abs(diff))} واحد {direction} داشته.")

    return card([
        section_title("روند تراز"),
        ft.Container(height=8),
        ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ft.Container(height=6) if sentence else ft.Container(),
        ft.Text(sentence, size=12, color=ON_SURFACE_VAR, rtl=True) if sentence else ft.Container(),
    ], padding=16)


# --------------------------------------------------------------------------- #
# Subject average card (across all exams)
# --------------------------------------------------------------------------- #


def _subject_average_card() -> ft.Control:
    exams = models.list_exams()
    controls: list[ft.Control] = [section_title("میانگین درصد دروس")]
    if not exams:
        controls.append(ft.Text("هنوز آزمونی ثبت نشده.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    pcts: dict[str, list] = {}
    for exam in exams:
        for sub in models.list_exam_subjects(exam.id):
            if sub.percent is not None:
                pcts.setdefault(sub.subject, []).append(sub.percent)

    if not pcts:
        controls.append(ft.Text("درصد درسی ثبت نشده.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    sorted_subs = sorted(
        pcts.items(),
        key=lambda x: sum(x[1]) / len(x[1]),
        reverse=True,
    )

    for name, vals in sorted_subs[:8]:
        avg = sum(vals) / len(vals)
        best = max(vals)
        worst = min(vals)
        controls.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=8),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Column([
                ft.Row([
                    ft.Text(name, size=13, color=ON_SURFACE, rtl=True, expand=True,
                            weight=ft.FontWeight.W_500),
                    ft.Text(f"{to_fa(round(avg))}٪", size=14, color=ACCENT,
                            weight=ft.FontWeight.W_600, rtl=True),
                ]),
                ft.Container(height=4),
                ft.Row([
                    ft.Text(f"بهترین: {to_fa(round(best))}٪", size=10,
                            color=SUCCESS, rtl=True),
                    ft.Container(width=8),
                    ft.Text(f"بدترین: {to_fa(round(worst))}٪", size=10,
                            color=WARN, rtl=True),
                    ft.Container(width=8),
                    ft.Text(f"از {to_fa(len(vals))} آزمون", size=10,
                            color=ON_SURFACE_MUT, rtl=True),
                ]),
                ft.ProgressBar(value=avg / 100, color=ACCENT, bgcolor=OUTLINE, height=6),
            ], spacing=4),
        ))

    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Exam list
# --------------------------------------------------------------------------- #


def _exam_list_card(ctx, exams) -> ft.Control:
    controls: list[ft.Control] = [
        section_title(f"آزمون‌های ثبت‌شده ({to_fa(len(exams))})"),
    ]
    if not exams:
        controls.append(ft.Text("هنوز آزمونی ثبت نشده.", size=14,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    rows = []
    for exam in exams[:12]:
        subjects = models.list_exam_subjects(exam.id)
        rows.append(_exam_row(ctx, exam, subjects))

    controls.append(ft.Text("روی هر آزمون بزن تا جزئیات درس‌ها را ببینی.",
                            size=10, color=ON_SURFACE_MUT, rtl=True))
    controls.append(ft.Container(height=6))
    controls.append(ft.Column(rows, spacing=6))
    return card(controls, padding=16)


def _exam_row(ctx, exam, subjects) -> ft.Control:
    detail = f"تراز {to_fa(exam.taraz)}"
    if exam.rank:
        detail += f" • رتبه {to_fa(exam.rank)}"
    detail += f" • {_jalali_label(exam.date)}"
    pcts = [f"{s.subject}: {to_fa(s.percent)}٪" for s in subjects if s.percent is not None]
    if pcts:
        detail += " • " + "، ".join(pcts[:3])
        if len(pcts) > 3:
            detail += f" و {to_fa(len(pcts) - 3)} درس دیگر"

    def _open_detail(_e):
        _open_detail_dialog(ctx, exam, subjects)

    def _edit(_e):
        _open_edit_dialog(ctx, exam, subjects)

    def _delete(_e):
        _confirm_delete(ctx, exam)

    return ft.Container(
        padding=pad_sym(horizontal=12, vertical=10),
        bgcolor=SURFACE_HIGH, border_radius=8, on_click=_open_detail,
        content=ft.Row([
            ft.Container(width=4, height=42, bgcolor=ACCENT, border_radius=2),
            ft.Container(width=8),
            ft.Column([
                ft.Text(f"آزمون {to_fa(exam.exam_number)}", size=14,
                        color=ON_SURFACE, weight=ft.FontWeight.W_500, rtl=True),
                ft.Text(detail, size=11, color=ON_SURFACE_VAR, rtl=True, max_lines=3),
            ], spacing=2, expand=True),
            ft.Row([
                ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_size=18,
                              tooltip="ویرایش", on_click=_edit,
                              style=ft.ButtonStyle(color=ON_SURFACE_VAR)),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18,
                              tooltip="حذف", on_click=_delete,
                              style=ft.ButtonStyle(color=ON_SURFACE_VAR)),
            ], spacing=0),
        ]),
    )


def _jalali_label(iso: str) -> str:
    try:
        return jalali_label(iso)
    except Exception:
        return iso


# --------------------------------------------------------------------------- #
# Detail dialog — full subject breakdown
# --------------------------------------------------------------------------- #


def _open_detail_dialog(ctx, exam, subjects) -> None:
    controls: list[ft.Control] = [
        ft.Text(f"آزمون شماره {to_fa(exam.exam_number)}", size=15,
                color=ON_SURFACE, weight=ft.FontWeight.W_700, rtl=True),
        ft.Text(f"تاریخ: {_jalali_label(exam.date)}", size=12,
                color=ON_SURFACE_VAR, rtl=True),
        ft.Row([
            ft.Text(f"تراز: {to_fa(exam.taraz)}", size=12, color=ACCENT,
                    weight=ft.FontWeight.W_600, rtl=True),
            ft.Container(width=12),
            ft.Text(f"رتبه: {to_fa(exam.rank) if exam.rank else '—'}",
                    size=12, color=ON_SURFACE_VAR, rtl=True),
        ]),
        ft.Container(height=4),
        divider(),
        ft.Container(height=4),
    ]

    if not subjects:
        controls.append(ft.Text("درسی برای این آزمون ثبت نشده.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
    else:
        # Header row
        controls.append(ft.Row([
            ft.Text("درس", size=11, color=ON_SURFACE_MUT, rtl=True, expand=True),
            ft.Text("٪", size=11, color=ON_SURFACE_MUT, width=36,
                    text_align=ft.TextAlign.CENTER),
            ft.Text("درست", size=11, color=ON_SURFACE_MUT, width=36,
                    text_align=ft.TextAlign.CENTER),
            ft.Text("غلط", size=11, color=ON_SURFACE_MUT, width=36,
                    text_align=ft.TextAlign.CENTER),
            ft.Text("نزده", size=11, color=ON_SURFACE_MUT, width=36,
                    text_align=ft.TextAlign.CENTER),
        ]))
        for s in subjects:
            pct = f"{to_fa(round(s.percent))}٪" if s.percent is not None else "—"
            corr = to_fa(s.correct) if s.correct is not None else "—"
            wrng = to_fa(s.wrong) if s.wrong is not None else "—"
            blnk = to_fa(s.blank) if s.blank is not None else "—"
            controls.append(ft.Container(
                padding=pad_sym(horizontal=8, vertical=6),
                bgcolor=SURFACE_HIGH, border_radius=6,
                content=ft.Row([
                    ft.Text(s.subject, size=12, color=ON_SURFACE, rtl=True,
                            expand=True, weight=ft.FontWeight.W_500),
                    ft.Text(pct, size=12, color=ACCENT, width=36,
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.W_600),
                    ft.Text(corr, size=11, color=SUCCESS, width=36,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(wrng, size=11, color=WARN, width=36,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(blnk, size=11, color=ON_SURFACE_MUT, width=36,
                            text_align=ft.TextAlign.CENTER),
                ]),
            ))

    def _edit_from_detail(_e):
        ctx.close_dialog(dlg)
        _open_edit_dialog(ctx, exam, subjects)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("جزئیات آزمون", rtl=True, size=16,
                      weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 360),
            content=ft.Column(controls, spacing=6, tight=True,
                              scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("بستن", on_click=lambda _: ctx.close_dialog(dlg)),
            outlined_button("ویرایش", on_click=_edit_from_detail,
                            icon=ft.Icons.EDIT_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


# --------------------------------------------------------------------------- #
# Add dialog — advanced exam entry (percent + correct/wrong/blank per subject)
# --------------------------------------------------------------------------- #


def _open_dialog(ctx) -> None:
    activities = models.list_activities(active_only=True)
    next_num = len(models.list_exams()) + 1
    number = ft.TextField(label="شماره", rtl=True, text_size=14, dense=True,
                          value=str(next_num), keyboard_type=ft.KeyboardType.NUMBER,
                          input_filter=ft.NumbersOnlyInputFilter(), width=80)
    date_field = ft.TextField(
        label="تاریخ شمسی", rtl=True, text_size=14, dense=True,
        value=format_jalali(clock_sync.now_local().date().isoformat()),
        expand=True, hint_text="۱۴۰۵-۰۸-۰۶",
    )
    taraz = ft.TextField(label="تراز", rtl=True, text_size=14, dense=True,
                         keyboard_type=ft.KeyboardType.NUMBER,
                         input_filter=ft.NumbersOnlyInputFilter(), width=100)
    rank = ft.TextField(label="رتبه (اختیاری)", rtl=True, text_size=14, dense=True,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        input_filter=ft.NumbersOnlyInputFilter(), width=120)

    subjects_col = ft.Column(spacing=6)
    subject_rows: list[dict] = []

    def _add_row(_e=None):
        if not activities:
            ctx.snack("اول از تنظیمات یک درس اضافه کن.")
            return
        name_dd = ft.Dropdown(
            label="درس", rtl=True, text_size=12, dense=True,
            options=[ft.DropdownOption(key=a.name, text=a.name) for a in activities],
            value=activities[0].name, expand=True,
        )
        pct = ft.TextField(label="٪", rtl=True, text_size=12, dense=True,
                           keyboard_type=ft.KeyboardType.NUMBER,
                           input_filter=ft.NumbersOnlyInputFilter(),
                           width=46)
        corr = ft.TextField(label="درست", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            width=46)
        wrng = ft.TextField(label="غلط", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            width=46)
        blnk = ft.TextField(label="نزده", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            width=46)
        row = ft.Container(
            padding=pad_sym(horizontal=8, vertical=6),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Column([
                ft.Row([name_dd, pct], spacing=6),
                ft.Row([corr, wrng, blnk], spacing=4),
            ], spacing=4),
        )
        rec = {"name": name_dd, "pct": pct, "correct": corr,
               "wrong": wrng, "blank": blnk, "container": row}
        subject_rows.append(rec)
        subjects_col.controls.append(row)
        try: subjects_col.update()
        except: pass

    _add_row()  # start with one row

    def _save(_e=None):
        try:
            en = int(ascii_digits(number.value or "0"))
            et = int(ascii_digits(taraz.value or "0"))
            ed = normalize_date(date_field.value or "")
            rt = ascii_digits(rank.value or "").strip()
            er = int(rt) if rt else None
            if en <= 0 or et < 0:
                raise ValueError("شماره و تراز معتبر نیست.")
            if er is not None and er < 1:
                raise ValueError("رتبه باید یک عدد مثبت باشد.")

            subs = []
            for r in subject_rows:
                name = (r["name"].value or "").strip()
                if not name:
                    continue
                p = ascii_digits(r["pct"].value or "").strip()
                pct = float(p) if p else None
                if pct is not None and not 0 <= pct <= 100:
                    raise ValueError(f"درصد «{name}» باید ۰ تا ۱۰۰ باشد.")

                def _opt_int(field):
                    s = ascii_digits(field.value or "").strip()
                    return int(s) if s else None

                corr = _opt_int(r["correct"])
                wrng = _opt_int(r["wrong"])
                blnk = _opt_int(r["blank"])
                subs.append({"subject": name, "percent": pct,
                             "correct": corr, "wrong": wrng, "blank": blnk})

            if not subs:
                raise ValueError("حداقل یک درس وارد کن.")

            models.create_exam(ed, en, et, None, er, subs)
            ctx.close_dialog(dlg)
            ctx.snack("آزمون ثبت شد.")
            ctx.refresh()
        except ValueError as e:
            ctx.snack(str(e))
        except Exception as e:
            ctx.snack(f"خطا: {str(e)[:100]}")

    add_btn = outlined_button("افزودن درس", on_click=_add_row, icon=ft.Icons.ADD)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("ثبت آزمون", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 360),
            height=responsive_dialog_height(ctx.page, 520),
            content=ft.Column([
                ft.Row([number, date_field], spacing=8),
                ft.Row([taraz, rank], spacing=8),
                ft.Container(height=4),
                ft.Text("درصد هر درس (حداقل یک درس). درست/غلط/نزده اختیاری است.",
                        size=11, color=ON_SURFACE_VAR, rtl=True),
                subjects_col,
                add_btn,
            ], spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("ثبت", on_click=_save, icon=ft.Icons.SAVE_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


# --------------------------------------------------------------------------- #
# Edit dialog (delete + recreate — no models.update_exam available)
# --------------------------------------------------------------------------- #


def _open_edit_dialog(ctx, exam, subjects) -> None:
    activities = models.list_activities(active_only=True)
    number = ft.TextField(label="شماره", rtl=True, text_size=14, dense=True,
                          value=str(exam.exam_number),
                          keyboard_type=ft.KeyboardType.NUMBER,
                          input_filter=ft.NumbersOnlyInputFilter(), width=80)
    date_field = ft.TextField(
        label="تاریخ شمسی", rtl=True, text_size=14, dense=True,
        value=format_jalali(exam.date), expand=True, hint_text="۱۴۰۵-۰۸-۰۶",
    )
    taraz = ft.TextField(label="تراز", rtl=True, text_size=14, dense=True,
                         value=str(exam.taraz),
                         keyboard_type=ft.KeyboardType.NUMBER,
                         input_filter=ft.NumbersOnlyInputFilter(), width=100)
    rank = ft.TextField(label="رتبه (اختیاری)", rtl=True, text_size=14, dense=True,
                        value=str(exam.rank) if exam.rank is not None else "",
                        keyboard_type=ft.KeyboardType.NUMBER,
                        input_filter=ft.NumbersOnlyInputFilter(), width=120)

    subjects_col = ft.Column(spacing=6)
    subject_rows: list[dict] = []

    def _add_row(_e=None, sub=None):
        if not activities and sub is None:
            ctx.snack("اول از تنظیمات یک درس اضافه کن.")
            return
        default_name = (sub.subject if sub else (activities[0].name if activities else None))
        # If the saved subject name isn't in the current active-activity list
        # (e.g. the activity was renamed), include it as an extra option so the
        # dropdown shows the right value instead of going blank.
        opts = [ft.DropdownOption(key=a.name, text=a.name) for a in activities]
        if default_name and not any(a.name == default_name for a in activities):
            opts.append(ft.DropdownOption(key=default_name, text=default_name))
        name_dd = ft.Dropdown(
            label="درس", rtl=True, text_size=12, dense=True,
            options=opts,
            value=default_name, expand=True,
        )
        pct = ft.TextField(label="٪", rtl=True, text_size=12, dense=True,
                           keyboard_type=ft.KeyboardType.NUMBER,
                           input_filter=ft.NumbersOnlyInputFilter(),
                           value=(str(sub.percent) if sub and sub.percent is not None else ""),
                           width=46)
        corr = ft.TextField(label="درست", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            value=(str(sub.correct) if sub and sub.correct is not None else ""),
                            width=46)
        wrng = ft.TextField(label="غلط", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            value=(str(sub.wrong) if sub and sub.wrong is not None else ""),
                            width=46)
        blnk = ft.TextField(label="نزده", rtl=True, text_size=10, dense=True,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            input_filter=ft.NumbersOnlyInputFilter(),
                            value=(str(sub.blank) if sub and sub.blank is not None else ""),
                            width=46)
        row = ft.Container(
            padding=pad_sym(horizontal=8, vertical=6),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Column([
                ft.Row([name_dd, pct], spacing=6),
                ft.Row([corr, wrng, blnk], spacing=4),
            ], spacing=4),
        )
        rec = {"name": name_dd, "pct": pct, "correct": corr,
               "wrong": wrng, "blank": blnk, "container": row}
        subject_rows.append(rec)
        subjects_col.controls.append(row)
        try: subjects_col.update()
        except: pass

    # Pre-fill existing subjects.
    for sub in subjects:
        _add_row(sub=sub)
    if not subject_rows:
        _add_row()

    def _save(_e=None):
        try:
            en = int(ascii_digits(number.value or "0"))
            et = int(ascii_digits(taraz.value or "0"))
            ed = normalize_date(date_field.value or "")
            rt = ascii_digits(rank.value or "").strip()
            er = int(rt) if rt else None
            if en <= 0 or et < 0:
                raise ValueError("شماره و تراز معتبر نیست.")

            subs = []
            for r in subject_rows:
                name = (r["name"].value or "").strip()
                if not name:
                    continue
                p = ascii_digits(r["pct"].value or "").strip()
                pct = float(p) if p else None
                if pct is not None and not 0 <= pct <= 100:
                    raise ValueError(f"درصد «{name}» باید ۰ تا ۱۰۰ باشد.")

                def _opt_int(field):
                    s = ascii_digits(field.value or "").strip()
                    return int(s) if s else None

                subs.append({"subject": name, "percent": pct,
                             "correct": _opt_int(r["correct"]),
                             "wrong": _opt_int(r["wrong"]),
                             "blank": _opt_int(r["blank"])})

            if not subs:
                raise ValueError("حداقل یک درس وارد کن.")

            # Delete the old exam, then create a fresh one with the new data.
            models.delete_exam(exam.id)
            models.create_exam(ed, en, et, None, er, subs)
            ctx.close_dialog(dlg)
            ctx.snack("آزمون به‌روز شد.")
            ctx.refresh()
        except ValueError as e:
            ctx.snack(str(e))
        except Exception as e:
            ctx.snack(f"خطا: {str(e)[:100]}")

    add_btn = outlined_button("افزودن درس", on_click=lambda _: _add_row(),
                              icon=ft.Icons.ADD)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("ویرایش آزمون", rtl=True, size=18,
                      weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 360),
            height=responsive_dialog_height(ctx.page, 520),
            content=ft.Column([
                ft.Row([number, date_field], spacing=8),
                ft.Row([taraz, rank], spacing=8),
                ft.Container(height=4),
                ft.Text("درصد و درست/غلط/نزده هر درس (حداقل یک درس).",
                        size=11, color=ON_SURFACE_VAR, rtl=True),
                subjects_col,
                add_btn,
            ], spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("ذخیره", on_click=_save, icon=ft.Icons.SAVE_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


# --------------------------------------------------------------------------- #
# Delete confirmation
# --------------------------------------------------------------------------- #


def _confirm_delete(ctx, exam) -> None:
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("حذف آزمون؟", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Text(f"آزمون {to_fa(exam.exam_number)} حذف شود؟",
                        rtl=True, size=14, color=ON_SURFACE_VAR),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("حذف", on_click=lambda _: _do_delete(ctx, dlg, exam),
                          icon=ft.Icons.DELETE_OUTLINE),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _do_delete(ctx, dlg, exam) -> None:
    models.delete_exam(exam.id)
    ctx.close_dialog(dlg)
    ctx.snack("حذف شد.")
    ctx.refresh()
