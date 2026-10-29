"""Analysis tab — 7-day bar chart + exam taraz line chart + local sentences.

Per spec:
    - Bar chart: last 7 days of study minutes.
    - Line chart: exam taraz over time (only if data exists).
    - Under each chart: one short local analysis sentence.
    - Assistant button (opens the AI stub dialog) — not a separate tab.

Charts are drawn with plain Flet Containers (no flet_charts dependency —
that package failed to render bars in our test environment, so we ship a
small custom bar/line renderer that's dependency-free and reliable).
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

import flet as ft

from services import clock_sync

from core import analytics, models
from core import goals as goal_service
from core.fa_dates import ascii_digits, normalize_date, format_jalali
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, OUTLINE,
    SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    card, divider, filled_button, label, outlined_button, section_title,
    stat_tile, text_button, to_fa, pad_sym, responsive_dialog_width, responsive_dialog_height,
)
from ui import assistant as _assistant


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    last7 = analytics.last_7_days_minutes(today)
    series = analytics.exam_taraz_series()

    # ---- top stats ----
    total_7d = sum(m for _, m in last7)
    tests_7d = sum(t for _, t in analytics.last_7_days_tests(today))
    dq = analytics.data_quality((today - timedelta(days=6), today))

    top_stats = ft.Row(
        [
            stat_tile(to_fa(total_7d), "دقیقه در ۷ روز"),
            stat_tile(to_fa(tests_7d), "آزمون در ۷ روز"),
            stat_tile(to_fa(dq) + "٪", "کیفیت ثبت"),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # ---- bar chart ----
    bar_chart = _build_bar_chart(last7)
    bar_sentence = _bar_sentence(last7, total_7d)

    bar_card = card(
        [
            section_title("۷ روز اخیر"),
            ft.Container(height=6),
            bar_chart,
            ft.Container(height=4),
            ft.Text(bar_sentence, size=12, color=ON_SURFACE_VAR, rtl=True),
        ],
        padding=14,
    )

    # ---- exam line chart (only if data exists) ----
    exam_card: ft.Control
    if series:
        line_chart = _build_line_chart(series)
        exam_sentence = _line_sentence(series)
        exam_card = card(
            [
                section_title("روند تراز آزمون‌ها"),
                ft.Container(height=6),
                line_chart,
                ft.Container(height=4),
                ft.Text(exam_sentence, size=12, color=ON_SURFACE_VAR, rtl=True),
            ],
            padding=14,
        )
    else:
        exam_card = card(
            [
                section_title("روند تراز آزمون‌ها"),
                ft.Container(height=6),
                ft.Container(
                    padding=12,
                    bgcolor=SURFACE_HIGH,
                    border_radius=8,
                    content=ft.Text(
                        "هنوز آزمونی ثبت نشده؛ از بخش ثبت آزمون در همین صفحه شروع کن.",
                        size=12, color=ON_SURFACE_VAR, rtl=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment(0, 0),
                ),
            ],
            padding=14,
        )

    # ---- assistant button ----
    assistant_btn = filled_button(
        "دریافت تحلیل هوشمند",
        on_click=lambda _: _assistant.open_assistant(ctx),
        icon=ft.Icons.AUTO_AWESOME,
    )

    return ft.ListView(
        [
            ft.Container(height=4),
            section_title("تحلیل"),
            ft.Container(height=8),
            top_stats,
            ft.Container(height=10),
            bar_card,
            ft.Container(height=10),
            _activity_mix_card(today),
            ft.Container(height=10),
            _test_quality_card(today),
            ft.Container(height=10),
            _weekly_goals_card(today),
            ft.Container(height=10),
            exam_card,
            ft.Container(height=10),
            _exam_management_card(ctx),
            ft.Container(height=14),
            ft.Row([assistant_btn], alignment=ft.MainAxisAlignment.END),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #


def _build_bar_chart(last7: list[tuple[str, int]]) -> ft.Control:
    """Custom 7-day bar chart built from Containers.

    Layout (top → bottom):
        - 120-px tall bar plot area (Row of 7 columns, each holding a
          bottom-aligned bar)
        - Row of 7 weekday labels under the bars
        - Row of 3 y-axis tick labels above the plot (right-aligned)
    """
    fa_weekdays_sat = ["ش", "ی", "د", "س", "چ", "پ", "ج"]

    max_m = max((m for _, m in last7), default=60) or 60
    # Round max up to a nice tick value for the y-axis labels.
    tick = _nice_interval(max_m)
    y_top = max(tick * 3, max_m, 30)

    PLOT_H = 120  # px

    bar_cols: list[ft.Control] = []
    label_cols: list[ft.Control] = []
    for date_str, mins in last7:
        d = date.fromisoformat(date_str)
        sat_idx = (d.weekday() + 2) % 7
        wd_label = fa_weekdays_sat[sat_idx]

        bar_h = max(2, int(PLOT_H * mins / y_top)) if mins > 0 else 2
        bar_color = ACCENT if mins > 0 else OUTLINE

        # Each column is a fixed-width slot with the bar bottom-aligned.
        bar_cols.append(ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 1),  # bottom-center
            content=ft.Container(
                width=18,
                height=bar_h,
                bgcolor=bar_color,
                border_radius=4,
            ),
        ))
        label_cols.append(ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),  # top-center
            content=ft.Text(value=wd_label, size=11, color=ON_SURFACE_VAR,
                            rtl=True, text_align=ft.TextAlign.CENTER),
        ))

    plot = ft.Container(
        height=PLOT_H,
        bgcolor=SURFACE_HIGH,
        border_radius=8,
        padding=ft.Padding(left=6, top=6, right=6, bottom=6),
        content=ft.Row(bar_cols, spacing=4, expand=True),
    )

    y_labels = ft.Row(
        [
            ft.Text(value=to_fa(0), size=9, color=ON_SURFACE_VAR),
            ft.Container(expand=True),
            ft.Text(value=to_fa(int(y_top / 2)), size=9, color=ON_SURFACE_VAR),
            ft.Container(expand=True),
            ft.Text(value=to_fa(int(y_top)), size=9, color=ON_SURFACE_VAR),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    return ft.Column(
        [
            y_labels,
            ft.Container(height=2),
            plot,
            ft.Container(height=4),
            ft.Row(label_cols, spacing=4),
        ],
        spacing=0,
    )


def _build_line_chart(series: list[tuple[int, int]]) -> ft.Control:
    """Custom line chart for exam taraz — dots connected by line segments.

    Uses a Stack with Positioned dots and thin rotated Containers as
    line segments. Reliable across Flet web/desktop; no chart package.
    """
    if len(series) < 2:
        # Single point — show one dot.
        series = series * 1

    n = len(series)
    ys = [t for _, t in series]
    y_min = min(ys)
    y_max = max(ys)
    if y_max == y_min:
        y_max = y_min + 1  # avoid divide-by-zero
    y_pad = (y_max - y_min) * 0.15
    y_lo = y_min - y_pad
    y_hi = y_max + y_pad

    PLOT_W = 280  # logical px; will be wrapped in expand=True container
    PLOT_H = 120
    DOT = 8
    LINE_W = 2

    # Map (i, taraz) → (x_px, y_px from top)
    def to_xy(i: int, t: int) -> tuple[float, float]:
        x = (i / max(1, n - 1)) * (PLOT_W - DOT) + DOT / 2
        # y from top: higher taraz → smaller y
        y = PLOT_H - DOT/2 - ((t - y_lo) / (y_hi - y_lo)) * (PLOT_H - DOT)
        return x, y

    points_xy = [to_xy(i, t) for i, (_, t) in enumerate(series)]

    stack_items: list[ft.Control] = [
        ft.Container(width=PLOT_W, height=PLOT_H, bgcolor=SURFACE_HIGH,
                     border_radius=8),
    ]

    # Line segments between consecutive points.
    for i in range(len(points_xy) - 1):
        x1, y1 = points_xy[i]
        x2, y2 = points_xy[i + 1]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            continue
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        # The container is rotated around its top-left corner; we then
        # translate it to (x1, y1) and offset so the rotation pivots at
        # the start of the line.
        stack_items.append(
            ft.Container(
                left=x1,
                top=y1 - LINE_W / 2,
                width=length,
                height=LINE_W,
                bgcolor=ACCENT,
                border_radius=LINE_W / 2,
                rotate=ft.Rotate(angle=angle_rad, alignment=ft.Alignment(-1, 0)),
            )
        )

    # Dots on top.
    for i, (x, y) in enumerate(points_xy):
        stack_items.append(
            ft.Container(
                left=x - DOT / 2,
                top=y - DOT / 2,
                width=DOT,
                height=DOT,
                bgcolor=ACCENT,
                shape=ft.BoxShape.CIRCLE,
            )
        )

    plot = ft.Stack(
        stack_items,
        width=PLOT_W,
        height=PLOT_H,
        expand=True,
    )

    # Y-axis: show min and max taraz on the right.
    y_labels = ft.Row(
        [
            ft.Text(value=to_fa(int(y_lo)), size=9, color=ON_SURFACE_VAR),
            ft.Container(expand=True),
            ft.Text(value=to_fa(int(y_hi)), size=9, color=ON_SURFACE_VAR),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # X-axis: exam numbers under each dot.
    x_labels = ft.Row(
        [
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(value=to_fa(n), size=10, color=ON_SURFACE_VAR,
                                rtl=True, text_align=ft.TextAlign.CENTER),
            )
            for n, _ in series
        ],
        spacing=0,
    )

    return ft.Column(
        [
            y_labels,
            ft.Container(height=2),
            ft.Container(
                content=ft.Row([plot], alignment=ft.MainAxisAlignment.CENTER),
                alignment=ft.Alignment(0, 0),
            ),
            ft.Container(height=4),
            x_labels,
        ],
        spacing=0,
    )


# --------------------------------------------------------------------------- #
# Local analysis sentences
# --------------------------------------------------------------------------- #


def _bar_sentence(last7: list[tuple[str, int]], total: int) -> str:
    if total == 0:
        return "هیچ فعالیتی در ۷ روز اخیر ثبت نشده."
    nonzero = [m for _, m in last7 if m > 0]
    avg = sum(nonzero) // len(nonzero) if nonzero else 0
    peak_date_str, peak_m = max(last7, key=lambda x: x[1])
    peak_d = date.fromisoformat(peak_date_str)
    fa_weekdays_sat = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه",
                       "چهارشنبه", "پنجشنبه", "جمعه"]
    peak_wd = fa_weekdays_sat[(peak_d.weekday() + 2) % 7]
    return (f"میانگین روزهای ثبت‌شده: {to_fa(avg)} دقیقه. "
            f"بیشترین مطالعه در {peak_wd} با {to_fa(peak_m)} دقیقه.")


def _line_sentence(series: list[tuple[int, int]]) -> str:
    if len(series) < 2:
        return "برای دیدن روند، حداقل دو آزمون لازم است."
    first_n, first_t = series[0]
    last_n, last_t = series[-1]
    diff = last_t - first_t
    if diff == 0:
        return f"تراز از آزمون {to_fa(first_n)} تا {to_fa(last_n)} ثابت بوده."
    direction = "افزایش" if diff > 0 else "کاهش"
    return (f"تراز از آزمون {to_fa(first_n)} تا {to_fa(last_n)} "
            f"{to_fa(abs(diff))} واحد {direction} داشته.")


def _nice_interval(max_value: int) -> float:
    """Pick a readable y-axis interval for the bar chart."""
    if max_value <= 0:
        return 30.0
    # Aim for ~4 grid lines.
    raw = max_value / 4
    for step in (15, 30, 60, 90, 120, 180, 240, 360, 480, 600):
        if raw <= step:
            return float(step)
    return float(int(raw))


# --------------------------------------------------------------------------- #

# Activity mix, test quality, plan progress, and full exam entry
# --------------------------------------------------------------------------- #


def _activity_mix_card(today: date) -> ft.Control:
    start = today - timedelta(days=6)
    rows = analytics.time_by_group(start, today)
    total = sum(int(row.get("minutes") or 0) for row in rows)
    controls: list[ft.Control] = [section_title("توزیع زمان در ۷ روز اخیر")]
    if not rows or total <= 0:
        controls.append(ft.Text(
            "با ثبت فعالیت‌های مطالعه، کدنویسی، کار، ورزش و استراحت، سهم هر گروه در این بخش نمایش داده می‌شود.",
            size=12, color=ON_SURFACE_VAR, rtl=True,
        ))
    else:
        for row in rows:
            minutes = max(0, int(row.get("minutes") or 0))
            ratio = min(1.0, minutes / total) if total else 0.0
            controls.append(ft.Column([
                ft.Row([
                    ft.Text(str(row.get("group_name") or "سایر"), size=12,
                            color=ON_SURFACE, rtl=True, expand=True),
                    ft.Text(f"{to_fa(minutes)} دقیقه • {to_fa(round(ratio * 100))}٪",
                            size=11, color=ON_SURFACE_VAR, rtl=True),
                ], spacing=8),
                ft.ProgressBar(value=ratio, color=row.get("color") or ACCENT,
                               bgcolor=OUTLINE, height=7),
            ], spacing=4))
    controls.append(ft.Text(
        f"مجموع زمان ثبت‌شده: {to_fa(total)} دقیقه. مقایسه فقط بر اساس داده‌های ثبت‌شده است.",
        size=10, color=ON_SURFACE_VAR, rtl=True,
    ))
    return card(controls, padding=14)


def _test_quality_card(today: date) -> ft.Control:
    stats = analytics.test_quality(today - timedelta(days=6), today)
    accuracy = stats.get("accuracy_percent")
    accuracy_text = f"{to_fa(accuracy)}٪" if accuracy is not None else "—"
    return card([
        section_title("کیفیت تست‌ها • ۷ روز اخیر"),
        ft.Row([
            stat_tile(to_fa(stats.get("tests", 0)), "کل تست"),
            stat_tile(to_fa(stats.get("correct", 0)), "درست", color=SUCCESS),
            stat_tile(to_fa(stats.get("wrong", 0)), "غلط", color=WARN),
            stat_tile(accuracy_text, "دقت پاسخ‌داده‌شده"),
        ], spacing=5),
        ft.Text(
            f"نزده: {to_fa(stats.get('blank', 0))} • دقت از درست ÷ (درست + غلط) محاسبه می‌شود.",
            size=10, color=ON_SURFACE_VAR, rtl=True,
        ),
    ], padding=14)


def _weekly_goals_card(today: date) -> ft.Control:
    gaps = goal_service.weekly_gaps(today)
    controls: list[ft.Control] = [section_title("پیشرفت هدف‌های هفتگی")]
    if not gaps:
        controls.append(ft.Text(
            "هنوز هدف هفتگی تعریف نشده؛ از تنظیمات برای هر فعالیت هدف تعیین کن.",
            size=12, color=ON_SURFACE_VAR, rtl=True,
        ))
    else:
        for gap in gaps[:6]:
            target = max(0, int(gap.target_minutes))
            actual = max(0, int(gap.actual_minutes))
            value = min(1.0, actual / target) if target else 0.0
            remaining = max(0, target - actual)
            controls.append(ft.Column([
                ft.Row([
                    ft.Text(gap.activity_name, size=12, color=ON_SURFACE, rtl=True, expand=True),
                    ft.Text(f"{to_fa(actual)} / {to_fa(target)} دقیقه",
                            size=11, color=ON_SURFACE_VAR, rtl=True),
                ], spacing=8),
                ft.ProgressBar(value=value, color=ACCENT, bgcolor=OUTLINE, height=7),
                ft.Text(
                    f"{to_fa(remaining)} دقیقه تا هدف" if remaining else "هدف زمانی ثبت‌شده کامل شده",
                    size=10, color=ON_SURFACE_VAR, rtl=True,
                ),
            ], spacing=3))
    return card(controls, padding=14)


def _exam_management_card(ctx) -> ft.Control:
    exams = list(reversed(models.list_exams()))
    rows: list[ft.Control] = [ft.Row([
        section_title("مدیریت آزمون‌ها"),
        ft.Container(expand=True),
        filled_button("ثبت آزمون", on_click=lambda _: _open_exam_dialog(ctx), icon=ft.Icons.ADD),
    ], spacing=8, wrap=True)]
    if not exams:
        rows.append(ft.Text(
            "هنوز آزمونی ثبت نشده است. تراز، رتبه و درصد هر درس را اینجا ذخیره کن.",
            size=12, color=ON_SURFACE_VAR, rtl=True,
        ))
    for exam in exams[:5]:
        subjects = models.list_exam_subjects(exam.id)
        percentages = " • ".join(
            f"{item.subject}: {to_fa(item.percent)}٪"
            for item in subjects if item.percent is not None
        )
        details = f"تراز {to_fa(exam.taraz)}"
        if exam.rank is not None:
            details += f" • رتبه {to_fa(exam.rank)}"
        if percentages:
            details += " • " + percentages
        rows.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=10),
            bgcolor=SURFACE_HIGH, border_radius=9,
            content=ft.Row([
                ft.Container(width=4, height=42, bgcolor=ACCENT, border_radius=2),
                ft.Column([
                    ft.Text(f"آزمون شماره {to_fa(exam.exam_number)}", size=13,
                            color=ON_SURFACE, weight=ft.FontWeight.W_600, rtl=True),
                    ft.Text(f"{_jalali_date_label(exam.date)} • {details}", size=11,
                            color=ON_SURFACE_VAR, rtl=True, max_lines=4),
                ], expand=True, spacing=3),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE, tooltip="حذف آزمون",
                    on_click=lambda _, item=exam: _confirm_delete_exam(ctx, item),
                    style=ft.ButtonStyle(color=ON_SURFACE_VAR),
                ),
            ], spacing=8),
        ))
    return card(rows, padding=14)


def _jalali_date_label(iso: str) -> str:
    from core.fa_dates import jalali_label
    try:
        return jalali_label(iso)
    except Exception:
        return iso


def _open_exam_dialog(ctx) -> None:
    next_number = len(models.list_exams()) + 1
    number = ft.TextField(label="شماره آزمون", rtl=True, text_size=13, dense=True,
                          value=str(next_number), keyboard_type=ft.KeyboardType.NUMBER)
    date_field = ft.TextField(label="تاریخ شمسی (سال-ماه-روز)", rtl=True, text_size=13,
                              dense=True, value=format_jalali(clock_sync.now_local().date().isoformat()),
                              hint_text="۱۴۰۵-۰۸-۰۶")
    taraz = ft.TextField(label="تراز", rtl=True, text_size=13, dense=True,
                         keyboard_type=ft.KeyboardType.NUMBER)
    rank = ft.TextField(label="رتبه (اختیاری)", rtl=True, text_size=13, dense=True,
                        keyboard_type=ft.KeyboardType.NUMBER)
    subjects = ft.TextField(
        label="درصد و نتیجه‌ی هر درس (هر درس در یک خط)", rtl=True, text_size=12,
        dense=True, multiline=True, min_lines=3, max_lines=8,
        hint_text="ریاضی=۶۵,۲۰,۸,۲\nفیزیک=۴۲,۱۲,۹,۴\nشیمی=۷۰",
    )
    notes = ft.TextField(label="تحلیل شخصی آزمون (اختیاری)", rtl=True, text_size=12,
                         dense=True, multiline=True, min_lines=2, max_lines=5, max_length=1500)

    def save_exam(_event):
        try:
            exam_number = int(ascii_digits(number.value or "").strip())
            exam_taraz = int(ascii_digits(taraz.value or "").strip())
            exam_date = normalize_date(date_field.value or "")
            rank_text = ascii_digits(rank.value or "").strip()
            exam_rank = int(rank_text) if rank_text else None
            if exam_number <= 0:
                raise ValueError("شماره‌ی آزمون باید مثبت باشد.")
            if exam_taraz < 0 or (exam_rank is not None and exam_rank < 1):
                raise ValueError("تراز یا رتبه واردشده معتبر نیست.")
            subject_rows = []
            for raw_line in (subjects.value or "").splitlines():
                line = ascii_digits(raw_line).strip()
                if not line:
                    continue
                if "=" not in line:
                    raise ValueError(f"قالب خط معتبر نیست: {raw_line}")
                name, raw_values = line.split("=", 1)
                if not name.strip():
                    raise ValueError("نام درس را قبل از علامت = وارد کن.")
                values = [x.strip().replace("٪", "").replace("%", "")
                          for x in raw_values.replace("،", ",").split(",")]
                parsed = []
                for item in values:
                    if item == "":
                        parsed.append(None)
                    else:
                        try:
                            parsed.append(float(item))
                        except ValueError as exc:
                            raise ValueError(f"عدد واردشده برای درس «{name.strip()}» معتبر نیست.") from exc
                percent = parsed[0] if parsed else None
                if percent is not None and not 0 <= percent <= 100:
                    raise ValueError(f"درصد درس «{name.strip()}» باید بین ۰ تا ۱۰۰ باشد.")
                counts = []
                for value in (parsed[1:4] + [None, None, None])[:3]:
                    if value is None:
                        counts.append(None)
                    elif value < 0 or int(value) != value:
                        raise ValueError("تعداد درست/غلط/نزده باید عدد صحیح نامنفی باشد.")
                    else:
                        counts.append(int(value))
                subject_rows.append({
                    "subject": name.strip(), "percent": percent,
                    "correct": counts[0], "wrong": counts[1], "blank": counts[2],
                })
            models.create_exam(exam_date, exam_number, exam_taraz,
                               (notes.value or "").strip() or None, exam_rank, subject_rows)
            ctx.close_dialog(dialog)
            ctx.snack("آزمون و نتایج درس‌ها ذخیره شد.")
            ctx.refresh()
        except ValueError as exc:
            ctx.snack(str(exc))
        except Exception as exc:
            ctx.snack(f"ذخیره آزمون ناموفق بود: {str(exc)[:160]}")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("ثبت آزمون", rtl=True, size=16, weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 350),
            height=responsive_dialog_height(ctx.page, 500),
            content=ft.Column([
                ft.Row([number, taraz, rank], spacing=6, wrap=True), date_field,
                subjects, notes,
                ft.Text("قالب هر خط: نام درس=درصد,درست,غلط,نزده؛ شمارنده‌ها اختیاری‌اند.",
                        size=10, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dialog)),
            filled_button("ذخیره آزمون", on_click=save_exam, icon=ft.Icons.SAVE_OUTLINED),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dialog)


def _confirm_delete_exam(ctx, exam) -> None:
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("حذف آزمون", rtl=True, size=16, weight=ft.FontWeight.W_600),
        content=ft.Text(
            f"آزمون شماره {to_fa(exam.exam_number)} و جزئیات درس‌هایش حذف شود؟",
            rtl=True, size=13, color=ON_SURFACE_VAR,
        ),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dialog)),
            filled_button("حذف آزمون", on_click=lambda _: _delete_exam(ctx, dialog, exam),
                          icon=ft.Icons.DELETE_OUTLINE),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dialog)


def _delete_exam(ctx, dialog, exam) -> None:
    models.delete_exam(exam.id)
    ctx.close_dialog(dialog)
    ctx.snack("آزمون حذف شد.")
    ctx.refresh()

