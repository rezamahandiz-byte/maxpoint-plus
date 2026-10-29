"""Charts tab — study analytics and visualizations.

Layout (top → bottom):
  1. 7-day bar chart of study minutes
  2. Subject distribution (last 7 days)
  3. Weekly goals progress
  4. 4-week trend
  5. Streak heatmap — 30-day grid (core/streaks.py)
  6. Time by group — study / leisure / work etc (analytics.time_by_group)
  7. Monthly comparison — last 3 months (analytics.monthly_comparison)
  8. Best study time analysis — which hours are most productive

No input forms here — recording happens in the "ثبت" tab.
"""
from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from services import clock_sync
from core import analytics, models, streaks, db
from core import goals as goal_service
from core.fa_dates import to_fa_digits
from ui import (
    ACCENT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, SUCCESS, WARN,
    CENTER, card, pad_sym, section_title, to_fa, border_all,
)


def build(ctx) -> ft.Control:
    today = clock_sync.now_local().date()
    last7 = analytics.last_7_days_minutes(today)

    return ft.ListView([
        ft.Container(height=8),
        section_title("نمودارها"),
        ft.Container(height=12),
        _bar_chart_card(today, last7),
        ft.Container(height=12),
        _distribution_card(today),
        ft.Container(height=12),
        _goals_card(today),
        ft.Container(height=12),
        _trend_card(today),
        ft.Container(height=12),
        _streak_heatmap_card(today),
        ft.Container(height=12),
        _time_by_group_card(today),
        ft.Container(height=12),
        _monthly_comparison_card(),
        ft.Container(height=12),
        _best_time_card(today),
        ft.Container(height=80),
    ], spacing=0, expand=True, auto_scroll=False)


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# 7-day bar chart
# --------------------------------------------------------------------------- #


def _bar_chart_card(today, last7) -> ft.Control:
    fa_wd = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
    max_m = max((m for _, m in last7), default=60) or 60
    H = 100
    today_iso = today.isoformat()

    cols = []
    for ds, mins in last7:
        d = date.fromisoformat(ds)
        wd = fa_wd[(d.weekday() + 2) % 7]
        is_today = ds == today_iso
        h = max(2, int(H * mins / max_m)) if mins > 0 else 2
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


# --------------------------------------------------------------------------- #
# Subject distribution
# --------------------------------------------------------------------------- #


def _distribution_card(today) -> ft.Control:
    start = today - timedelta(days=6)
    rows = analytics.time_by_activity(start, today)
    total = sum(int(r.get("minutes") or 0) for r in rows)

    controls = [section_title("سهم هر فعالیت در ۷ روز")]
    if not rows or total <= 0:
        controls.append(ft.Text("هنوز داده‌ای نیست.", size=13, color=ON_SURFACE_MUT, rtl=True))
    else:
        for row in rows[:8]:
            minutes = max(0, int(row.get("minutes") or 0))
            ratio = min(1.0, minutes / total) if total else 0.0
            controls.append(ft.Column([
                ft.Row([
                    ft.Text(str(row.get("activity_name") or "سایر"), size=12,
                            color=ON_SURFACE, rtl=True, expand=True),
                    ft.Text(f"{to_fa(minutes)} دقیقه • {to_fa(round(ratio * 100))}٪",
                            size=11, color=ON_SURFACE_VAR, rtl=True),
                ]),
                ft.ProgressBar(value=ratio, color=row.get("color") or ACCENT,
                               bgcolor=OUTLINE, height=6),
            ], spacing=4))
        controls.append(ft.Text(f"مجموع: {to_fa(total)} دقیقه",
                                size=10, color=ON_SURFACE_MUT, rtl=True))
    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Weekly goals
# --------------------------------------------------------------------------- #


def _goals_card(today) -> ft.Control:
    gaps = goal_service.weekly_gaps(today)
    controls = [section_title("هدف‌های هفتگی")]
    if not gaps:
        controls.append(ft.Text("هنوز هدفی تعریف نشده.", size=13,
                                color=ON_SURFACE_MUT, rtl=True))
    else:
        for g in gaps[:6]:
            target = max(0, int(g.target_minutes))
            actual = max(0, int(g.actual_minutes))
            value = min(1.0, actual / target) if target else 0.0
            remaining = max(0, target - actual)
            controls.append(ft.Column([
                ft.Row([
                    ft.Text(g.activity_name, size=12, color=ON_SURFACE, rtl=True, expand=True),
                    ft.Text(f"{to_fa(actual)} / {to_fa(target)}", size=11,
                            color=ON_SURFACE_VAR, rtl=True),
                ]),
                ft.ProgressBar(value=value, color=ACCENT, bgcolor=OUTLINE, height=6),
                ft.Text(f"{to_fa(remaining)} دقیقه تا هدف" if remaining else "کامل شد",
                        size=10, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=3))
    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# 4-week trend
# --------------------------------------------------------------------------- #


def _trend_card(today) -> ft.Control:
    weekly = analytics.weekly_trend(4)
    max_w = max((w["minutes"] for w in weekly), default=1) or 1
    controls = [section_title("روند ۴ هفته")]

    cols = []
    for w in weekly:
        h = max(4, int(50 * w["minutes"] / max_w)) if w["minutes"] > 0 else 4
        cols.append(ft.Column([
            ft.Text(to_fa(w["minutes"]), size=9, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(width=28, height=h, bgcolor=ACCENT, border_radius=4),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    controls.append(ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND))
    total = sum(w["minutes"] for w in weekly)
    controls.append(ft.Text(f"مجموع ۴ هفته: {to_fa(total)} دقیقه",
                            size=10, color=ON_SURFACE_MUT, rtl=True))
    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Streak heatmap — 30-day grid
# --------------------------------------------------------------------------- #


def _streak_heatmap_card(today) -> ft.Control:
    history = streaks.streak_history(30)  # list of (date_str, has_sessions)
    current = streaks.current_streak(today)
    longest = streaks.longest_streak()
    total_active = streaks.total_active_days()

    controls: list[ft.Control] = [
        section_title("نقشه‌ی ۳۰ روز اخیر"),
        ft.Container(height=4),
        ft.Row([
            _heat_stat(to_fa(current), "روز متوالی", ACCENT),
            _heat_stat(to_fa(longest), "رکورد", SUCCESS),
            _heat_stat(to_fa(total_active), "روز فعال", ON_SURFACE_VAR),
        ], spacing=8),
        ft.Container(height=10),
    ]

    # 7 columns (Sat..Fri) — fill row by row, oldest → newest, RTL.
    fa_wd = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
    cols: list[ft.Control] = []
    for col_idx in range(7):
        cells = [ft.Text(fa_wd[col_idx], size=9, color=ON_SURFACE_MUT,
                         text_align=ft.TextAlign.CENTER)]
        for row_idx in range(5):  # 5 rows × 7 cols = 35 cells (last 30 + 5 spacer)
            idx = row_idx * 7 + col_idx
            if idx >= len(history):
                cells.append(ft.Container(width=18, height=18))
                continue
            ds, has = history[idx]
            d = date.fromisoformat(ds)
            is_today = ds == today.isoformat()
            if has:
                bg = ACCENT
                tooltip = f"{jalali_short(ds)} — ثبت شده"
            else:
                bg = SURFACE_HIGH
                tooltip = f"{jalali_short(ds)} — ثبت نشده"
            border = border_all(1, "#9BE8D7") if is_today else None
            cells.append(ft.Container(
                width=18, height=18, bgcolor=bg, border_radius=4,
                tooltip=tooltip, border=border,
            ))
        cols.append(ft.Column(cells, spacing=3,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                              expand=True))

    controls.append(ft.Row(cols, spacing=4, alignment=ft.MainAxisAlignment.SPACE_AROUND))
    controls.append(ft.Container(height=6))
    controls.append(ft.Row([
        ft.Container(width=10, height=10, bgcolor=ACCENT, border_radius=2),
        ft.Text("ثبت شده", size=10, color=ON_SURFACE_VAR, rtl=True),
        ft.Container(width=8),
        ft.Container(width=10, height=10, bgcolor=SURFACE_HIGH, border_radius=2),
        ft.Text("ثبت نشده", size=10, color=ON_SURFACE_VAR, rtl=True),
        ft.Container(width=8),
        ft.Container(width=10, height=10, bgcolor=SURFACE_HIGH,
                     border=border_all(1, "#9BE8D7"), border_radius=2),
        ft.Text("امروز", size=10, color=ON_SURFACE_VAR, rtl=True),
    ], spacing=2))
    return card(controls, padding=16)


def _heat_stat(value: str, caption: str, color: str) -> ft.Control:
    return ft.Container(
        expand=True, padding=pad_sym(horizontal=8, vertical=6),
        bgcolor=SURFACE_HIGH, border_radius=8,
        content=ft.Column([
            ft.Text(value, size=18, color=color, weight=ft.FontWeight.W_700,
                    rtl=True, text_align=ft.TextAlign.CENTER),
            ft.Text(caption, size=10, color=ON_SURFACE_MUT, rtl=True,
                    text_align=ft.TextAlign.CENTER),
        ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )


def jalali_short(iso: str) -> str:
    try:
        from core.fa_dates import gregorian_to_jalali
        d = date.fromisoformat(iso)
        y, m, day = gregorian_to_jalali(d.year, d.month, d.day)
        return f"{to_fa_digits(y)}/{to_fa_digits(f'{m:02d}')}/{to_fa_digits(f'{day:02d}')}"
    except Exception:
        return iso


# --------------------------------------------------------------------------- #
# Time by group
# --------------------------------------------------------------------------- #


def _time_by_group_card(today) -> ft.Control:
    start = today - timedelta(days=29)
    rows = analytics.time_by_group(start, today)
    total = sum(int(r.get("minutes") or 0) for r in rows)

    controls = [section_title("زمان به تفکیک گروه (۳۰ روز)")]
    if not rows or total <= 0:
        controls.append(ft.Text("هنوز داده‌ای ثبت نشده.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    for row in rows:
        name = str(row.get("group_name") or "سایر")
        minutes = max(0, int(row.get("minutes") or 0))
        sessions = max(0, int(row.get("sessions") or 0))
        ratio = min(1.0, minutes / total) if total else 0.0
        color = row.get("color") or ACCENT
        controls.append(ft.Column([
            ft.Row([
                ft.Container(width=10, height=10, bgcolor=color, border_radius=2),
                ft.Container(width=8),
                ft.Text(name, size=13, color=ON_SURFACE, rtl=True, expand=True),
                ft.Text(f"{to_fa(minutes)} دقیقه • {to_fa(sessions)} جلسه",
                        size=11, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=0),
            ft.ProgressBar(value=ratio, color=color, bgcolor=OUTLINE, height=6),
            ft.Text(f"{to_fa(round(ratio * 100))}٪ از کل زمان",
                    size=10, color=ON_SURFACE_MUT, rtl=True),
        ], spacing=3))
    controls.append(ft.Container(height=4))
    controls.append(ft.Text(f"مجموع: {to_fa(total)} دقیقه در {to_fa(len(rows))} گروه",
                            size=10, color=ON_SURFACE_MUT, rtl=True))
    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Monthly comparison
# --------------------------------------------------------------------------- #


def _monthly_comparison_card() -> ft.Control:
    months = analytics.monthly_comparison(3)
    controls = [section_title("مقایسه‌ی ۳ ماه اخیر")]
    if not months:
        controls.append(ft.Text("هنوز داده‌ای نیست.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    max_m = max((m.get("minutes", 0) for m in months), default=1) or 1
    cols = []
    for m in months:
        minutes = int(m.get("minutes", 0) or 0)
        active = int(m.get("active_days", 0) or 0)
        tests = int(m.get("tests", 0) or 0)
        h = max(4, int(70 * minutes / max_m)) if minutes > 0 else 4
        cols.append(ft.Column([
            ft.Text(to_fa(minutes), size=10, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(width=46, height=h, bgcolor=ACCENT, border_radius=6),
            ft.Container(height=4),
            ft.Text(str(m.get("label", "")), size=10, color=ON_SURFACE,
                    rtl=True, text_align=ft.TextAlign.CENTER, max_lines=1),
            ft.Text(f"{to_fa(active)} روز", size=9, color=ON_SURFACE_MUT,
                    rtl=True, text_align=ft.TextAlign.CENTER),
            ft.Text(f"{to_fa(tests)} تست", size=9, color=ON_SURFACE_MUT,
                    rtl=True, text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    controls.append(ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND))

    # Trend sentence
    if len(months) >= 2:
        first = int(months[0].get("minutes", 0) or 0)
        last = int(months[-1].get("minutes", 0) or 0)
        diff = last - first
        if diff == 0:
            trend = "ثابت"
        elif diff > 0:
            trend = f"{to_fa(diff)} دقیقه افزایش"
        else:
            trend = f"{to_fa(abs(diff))} دقیقه کاهش"
        controls.append(ft.Container(height=4))
        controls.append(ft.Text(
            f"از {months[0].get('label', '')} تا {months[-1].get('label', '')}: {trend}",
            size=11, color=ON_SURFACE_VAR, rtl=True,
        ))

    return card(controls, padding=16)


# --------------------------------------------------------------------------- #
# Best study time analysis
# --------------------------------------------------------------------------- #


def _best_time_card(today) -> ft.Control:
    start = today - timedelta(days=29)
    rows = db.fetch_all(
        """SELECT CAST(substr(created_at, 12, 2) AS INTEGER) AS hour,
                  SUM(minutes) AS total,
                  COUNT(*) AS sessions
           FROM sessions
           WHERE date BETWEEN ? AND ?
             AND created_at IS NOT NULL
           GROUP BY hour
           ORDER BY total DESC
           LIMIT 6;""",
        (start.isoformat(), today.isoformat()),
    )

    controls = [section_title("بهترین ساعات مطالعه (۳۰ روز)")]
    if not rows or not rows[0]["hour"]:
        controls.append(ft.Text("هنوز داده‌ای ثبت نشده.", size=12,
                                color=ON_SURFACE_MUT, rtl=True))
        return card(controls, padding=16)

    max_total = max((int(r["total"] or 0) for r in rows), default=1) or 1

    # Find the best hour
    best = rows[0]
    best_hour = int(best["hour"] or 0)
    best_total = int(best["total"] or 0)
    period = ("صبح" if 5 <= best_hour < 12
              else ("ظهر" if 12 <= best_hour < 17
                    else ("عصر" if 17 <= best_hour < 21 else "شب")))
    controls.append(ft.Text(
        f"بهترین ساعت مطالعه‌ات: {to_fa(f'{best_hour:02d}')}:۰۰ ({period}) "
        f"با {to_fa(best_total)} دقیقه در ۳۰ روز اخیر.",
        size=12, color=ON_SURFACE, rtl=True, weight=ft.FontWeight.W_500,
    ))
    controls.append(ft.Container(height=8))

    # Show top hours as horizontal bars (sorted by hour ascending for readability)
    sorted_rows = sorted(rows, key=lambda r: int(r["hour"] or 0))
    for r in sorted_rows:
        hour = int(r["hour"] or 0)
        total = int(r["total"] or 0)
        sessions = int(r["sessions"] or 0)
        bar_w = max(4, int(140 * total / max_total))
        period_short = ("ص" if 5 <= hour < 12 else ("ظ" if 12 <= hour < 17
                        else ("ع" if 17 <= hour < 21 else "ش")))
        controls.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=6),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Row([
                ft.Text(f"{to_fa(f'{hour:02d}')}:00", size=11, color=ON_SURFACE,
                        rtl=True, width=50),
                ft.Text(period_short, size=10, color=ON_SURFACE_MUT, width=12),
                ft.Container(width=6),
                ft.Container(width=bar_w, height=12, bgcolor=ACCENT, border_radius=3),
                ft.Container(width=8),
                ft.Text(f"{to_fa(total)} دقیقه", size=10, color=ON_SURFACE_VAR,
                        rtl=True),
                ft.Container(expand=True),
                ft.Text(f"{to_fa(sessions)} جلسه", size=9, color=ON_SURFACE_MUT,
                        rtl=True),
            ], spacing=0),
        ))

    return card(controls, padding=16)
