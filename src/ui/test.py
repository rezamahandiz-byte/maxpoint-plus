"""Test tab — comprehensive test analytics.

Layout:
  1. Summary stats (total / correct / wrong / blank / accuracy) — keep
  2. Quality bar (correct/wrong/blank ratio) — keep
  3. 7-day test count bar chart
  4. Subject-wise test performance (correct/wrong/blank per subject)
  5. Accuracy trend (last 7 days)
  6. Worst subjects card (subjects with most wrong answers)

Tests are recorded as part of study sessions (the tests_count, correct_count,
wrong_count, blank_count fields). This tab aggregates and visualizes them.
"""
from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from services import clock_sync
from core import analytics, db
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    CENTER, card, divider, section_title, stat_tile, to_fa, border_all,
    pad_sym,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    stats = analytics.test_quality(today - timedelta(days=6), today)
    last7_tests = analytics.last_7_days_tests(today)

    return ft.ListView(
        [
            ft.Container(height=8),
            section_title("تست"),
            ft.Container(height=12),
            _summary_card(stats),
            ft.Container(height=12),
            _quality_card(stats),
            ft.Container(height=12),
            _test_count_bar_card(today, last7_tests),
            ft.Container(height=12),
            _subject_performance_card(today),
            ft.Container(height=12),
            _accuracy_trend_card(today),
            ft.Container(height=12),
            _worst_subjects_card(today),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def _summary_card(stats: dict) -> ft.Control:
    accuracy = stats.get("accuracy_percent")
    acc_text = f"{to_fa(accuracy)}٪" if accuracy is not None else "—"
    return card([
        section_title("خلاصه‌ی ۷ روز"),
        ft.Container(height=10),
        ft.Row([
            stat_tile(to_fa(stats.get("tests", 0)), "کل تست"),
            stat_tile(to_fa(stats.get("correct", 0)), "درست", color=SUCCESS),
            stat_tile(to_fa(stats.get("wrong", 0)), "غلط", color=WARN),
            stat_tile(acc_text, "دقت", color=ACCENT),
        ], spacing=5),
    ], padding=16)


# --------------------------------------------------------------------------- #
# Quality bar
# --------------------------------------------------------------------------- #


def _quality_card(stats: dict) -> ft.Control:
    correct = int(stats.get("correct", 0) or 0)
    wrong = int(stats.get("wrong", 0) or 0)
    blank = int(stats.get("blank", 0) or 0)
    total = correct + wrong + blank

    if total == 0:
        return card([
            section_title("کیفیت تست‌ها"),
            ft.Container(height=8),
            ft.Text("هنوز تستی ثبت نشده.", size=14, color=ON_SURFACE_MUT, rtl=True),
        ], padding=16)

    correct_pct = correct / total if total > 0 else 0
    wrong_pct = wrong / total if total > 0 else 0
    blank_pct = blank / total if total > 0 else 0

    # Use expand with integer weights (proportional widths)
    # If a count is 0, use expand=0 (hidden) to avoid zero-width issues
    bar = ft.Row([
        ft.Container(expand=correct if correct > 0 else None,
                     bgcolor=SUCCESS, border_radius=4),
        ft.Container(expand=wrong if wrong > 0 else None,
                     bgcolor=WARN, border_radius=4),
        ft.Container(expand=blank if blank > 0 else None,
                     bgcolor=ON_SURFACE_MUT, border_radius=4),
    ], spacing=2)

    return card([
        section_title("کیفیت تست‌ها"),
        ft.Container(height=8),
        ft.Container(
            height=20, bgcolor=SURFACE_HIGH, border_radius=10,
            padding=pad_sym(horizontal=4, vertical=2),
            content=bar,
        ),
        ft.Container(height=8),
        ft.Row([
            ft.Row([
                ft.Container(width=10, height=10, bgcolor=SUCCESS, border_radius=2),
                ft.Text(f"درست: {to_fa(correct)}", size=12, color=ON_SURFACE, rtl=True),
            ], spacing=4),
            ft.Container(width=8),
            ft.Row([
                ft.Container(width=10, height=10, bgcolor=WARN, border_radius=2),
                ft.Text(f"غلط: {to_fa(wrong)}", size=12, color=ON_SURFACE, rtl=True),
            ], spacing=4),
            ft.Container(width=8),
            ft.Row([
                ft.Container(width=10, height=10, bgcolor=ON_SURFACE_MUT, border_radius=2),
                ft.Text(f"نزده: {to_fa(blank)}", size=12, color=ON_SURFACE, rtl=True),
            ], spacing=4),
        ], spacing=0, wrap=True),
    ], padding=16)


# --------------------------------------------------------------------------- #
# 7-day test count bar chart
# --------------------------------------------------------------------------- #


def _test_count_bar_card(today, last7_tests) -> ft.Control:
    fa_wd = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
    max_t = max((t for _, t in last7_tests), default=10) or 10
    today_iso = today.isoformat()
    PLOT_H = 100

    cols = []
    for ds, tests in last7_tests:
        d = date.fromisoformat(ds)
        wd = fa_wd[(d.weekday() + 2) % 7]
        is_today = ds == today_iso
        h = max(2, int(PLOT_H * tests / max_t)) if tests > 0 else 2
        cols.append(ft.Column([
            ft.Text(to_fa(tests) if tests > 0 else "", size=9,
                    color=ON_SURFACE_MUT, text_align=ft.TextAlign.CENTER),
            ft.Container(width=20, height=h,
                         bgcolor=ACCENT if is_today else "#577A80",
                         border_radius=4),
            ft.Container(height=4),
            ft.Text(wd, size=11, color=ON_SURFACE if is_today else ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    total = sum(t for _, t in last7_tests)
    if total == 0:
        sentence = "هیچ تستی در ۷ روز اخیر ثبت نشده."
    else:
        active_days = sum(1 for _, t in last7_tests if t > 0)
        avg = total // max(1, active_days)
        sentence = (f"۷ روز اخیر: {to_fa(total)} تست در {to_fa(active_days)} روز "
                    f"(میانگین {to_fa(avg)} تست در روزهای فعال).")

    return card([
        section_title("تست‌های ۷ روز اخیر"),
        ft.Container(height=8),
        ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ft.Container(height=6),
        ft.Text(sentence, size=12, color=ON_SURFACE_VAR, rtl=True),
    ], padding=16)


# --------------------------------------------------------------------------- #
# Subject-wise test performance
# --------------------------------------------------------------------------- #


def _subject_performance_card(today) -> ft.Control:
    start = today - timedelta(days=6)
    rows = db.fetch_all(
        """SELECT a.name, a.color,
                  SUM(s.tests_count) AS total,
                  SUM(s.correct_count) AS correct,
                  SUM(s.wrong_count) AS wrong,
                  SUM(s.blank_count) AS blank
           FROM sessions s
           JOIN activities a ON s.activity_id = a.id
           WHERE s.date BETWEEN ? AND ?
             AND s.tests_count > 0
           GROUP BY s.activity_id
           ORDER BY total DESC
           LIMIT 8;""",
        (start.isoformat(), today.isoformat()),
    )

    controls = [section_title("عملکرد تست به تفکیک درس (۷ روز)")]
    if not rows:
        controls.append(ft.Text(
            "هنوز تستی ثبت نشده. در جلسات مطالعه، تعداد تست‌ها را وارد کن.",
            size=12, color=ON_SURFACE_MUT, rtl=True,
        ))
        return card(controls, padding=16)

    for row in rows:
        name = row["name"]
        color = row["color"] or ACCENT
        total = int(row["total"] or 0)
        correct = int(row["correct"] or 0)
        wrong = int(row["wrong"] or 0)
        blank = int(row["blank"] or 0)
        acc = (round(100 * correct / (correct + wrong))
               if (correct + wrong) > 0 else None)

        controls.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=8),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Column([
                ft.Row([
                    ft.Container(width=4, height=20, bgcolor=color, border_radius=2),
                    ft.Container(width=8),
                    ft.Text(name, size=13, color=ON_SURFACE, rtl=True, expand=True,
                            weight=ft.FontWeight.W_500),
                    ft.Text(f"{to_fa(total)} تست", size=11, color=ON_SURFACE_VAR,
                            rtl=True),
                ], spacing=4),
                ft.Row([
                    ft.Text(f"درست: {to_fa(correct)}", size=10, color=SUCCESS, rtl=True),
                    ft.Container(width=6),
                    ft.Text(f"غلط: {to_fa(wrong)}", size=10, color=WARN, rtl=True),
                    ft.Container(width=6),
                    ft.Text(f"نزده: {to_fa(blank)}", size=10, color=ON_SURFACE_MUT,
                            rtl=True),
                    ft.Container(expand=True),
                    ft.Text(f"دقت: {to_fa(acc) + '٪' if acc is not None else '—'}",
                            size=10, color=ACCENT, rtl=True),
                ], spacing=0),
            ], spacing=4),
        ))

    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Accuracy trend (last 7 days)
# --------------------------------------------------------------------------- #


def _accuracy_trend_card(today) -> ft.Control:
    start = today - timedelta(days=6)
    rows = db.fetch_all(
        """SELECT date,
                  SUM(correct_count) AS correct,
                  SUM(wrong_count) AS wrong
           FROM sessions
           WHERE date BETWEEN ? AND ?
             AND (correct_count + wrong_count) > 0
           GROUP BY date
           ORDER BY date;""",
        (start.isoformat(), today.isoformat()),
    )

    controls = [section_title("روند دقت در ۷ روز اخیر")]
    if not rows:
        controls.append(ft.Text(
            "هنوز تستی با درست/غلط ثبت نشده. دقت از درست ÷ (درست + غلط) محاسبه می‌شود.",
            size=12, color=ON_SURFACE_MUT, rtl=True,
        ))
        return card(controls, padding=16)

    PLOT_H = 80
    today_iso = today.isoformat()
    fa_wd = ["ش", "ی", "د", "س", "چ", "پ", "ج"]

    points = []
    for row in rows:
        correct = int(row["correct"] or 0)
        wrong = int(row["wrong"] or 0)
        acc = round(100 * correct / (correct + wrong)) if (correct + wrong) > 0 else 0
        points.append((row["date"], acc))

    cols = []
    for ds, acc in points:
        d = date.fromisoformat(ds)
        wd = fa_wd[(d.weekday() + 2) % 7]
        is_today = ds == today_iso
        bar_h = max(2, int(PLOT_H * acc / 100))
        color = SUCCESS if acc >= 70 else (WARN if acc < 50 else ACCENT)
        cols.append(ft.Column([
            ft.Text(f"{to_fa(acc)}٪", size=9, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(width=20, height=bar_h,
                         bgcolor=color if is_today else "#577A80",
                         border_radius=4),
            ft.Container(height=4),
            ft.Text(wd, size=10, color=ON_SURFACE if is_today else ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    controls.append(ft.Row(cols, spacing=6,
                           alignment=ft.MainAxisAlignment.SPACE_AROUND))
    avg = round(sum(a for _, a in points) / len(points)) if points else 0
    controls.append(ft.Container(height=4))
    controls.append(ft.Text(
        f"میانگین دقت ۷ روز: {to_fa(avg)}٪ (از {to_fa(len(points))} روز فعال)",
        size=10, color=ON_SURFACE_MUT, rtl=True,
    ))
    controls.append(ft.Row([
        ft.Container(width=8, height=8, bgcolor=SUCCESS, border_radius=2),
        ft.Text("≥ ۷۰٪", size=9, color=ON_SURFACE_MUT, rtl=True),
        ft.Container(width=6),
        ft.Container(width=8, height=8, bgcolor=ACCENT, border_radius=2),
        ft.Text("۵۰–۷۰٪", size=9, color=ON_SURFACE_MUT, rtl=True),
        ft.Container(width=6),
        ft.Container(width=8, height=8, bgcolor=WARN, border_radius=2),
        ft.Text("< ۵۰٪", size=9, color=ON_SURFACE_MUT, rtl=True),
    ], spacing=0))

    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Worst subjects (most wrong answers)
# --------------------------------------------------------------------------- #


def _worst_subjects_card(today) -> ft.Control:
    start = today - timedelta(days=29)
    rows = db.fetch_all(
        """SELECT a.name, a.color,
                  SUM(s.wrong_count) AS wrong,
                  SUM(s.correct_count) AS correct,
                  SUM(s.tests_count) AS total
           FROM sessions s
           JOIN activities a ON s.activity_id = a.id
           WHERE s.date BETWEEN ? AND ?
             AND s.wrong_count > 0
           GROUP BY s.activity_id
           ORDER BY wrong DESC
           LIMIT 5;""",
        (start.isoformat(), today.isoformat()),
    )

    controls = [section_title("درس‌های با بیشترین غلط (۳۰ روز)")]
    if not rows:
        controls.append(ft.Text(
            "هیچ غلطی ثبت نشده. عالی!",
            size=12, color=SUCCESS, rtl=True,
        ))
        return card(controls, padding=16)

    max_wrong = max((int(r["wrong"] or 0) for r in rows), default=1) or 1
    for row in rows:
        name = row["name"]
        color = row["color"] or ACCENT
        wrong = int(row["wrong"] or 0)
        correct = int(row["correct"] or 0)
        total = int(row["total"] or 0)
        wrong_pct = round(100 * wrong / total) if total > 0 else 0
        ratio = min(1.0, wrong / max_wrong) if max_wrong else 0.0

        controls.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=8),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Column([
                ft.Row([
                    ft.Container(width=4, height=20, bgcolor=color, border_radius=2),
                    ft.Container(width=8),
                    ft.Text(name, size=13, color=ON_SURFACE, rtl=True, expand=True,
                            weight=ft.FontWeight.W_500),
                    ft.Text(f"{to_fa(wrong)} غلط", size=11, color=WARN, rtl=True),
                ]),
                ft.ProgressBar(value=ratio, color=WARN, bgcolor=OUTLINE, height=6),
                ft.Row([
                    ft.Text(f"از {to_fa(total)} تست: {to_fa(wrong_pct)}٪ غلط",
                            size=10, color=ON_SURFACE_MUT, rtl=True),
                    ft.Container(expand=True),
                    ft.Text(f"درست: {to_fa(correct)}", size=10, color=SUCCESS,
                            rtl=True),
                ]),
            ], spacing=4),
        ))

    controls.append(ft.Container(height=4))
    controls.append(ft.Text(
        "این درس‌ها را برای مرور و تحلیل خطا اولویت بده.",
        size=10, color=ON_SURFACE_MUT, rtl=True,
    ))
    return card(controls, padding=16)
