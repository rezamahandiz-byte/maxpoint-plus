"""Assistant dialog: local summaries first, optional AI analysis on demand."""
from __future__ import annotations
from datetime import date
from typing import Any
import flet as ft

from core import analytics, models, ai
from ui import (
    ACCENT, ON_SURFACE, ON_SURFACE_VAR, SURFACE_HIGH,
    filled_button, outlined_button, text_button, to_fa, responsive_dialog_width, responsive_dialog_height,
)


def open_assistant(ctx) -> None:
    state: dict[str, Any] = {"days": 7, "summary": analytics.build_aggregate_summary(7)}
    result = ft.Text(
        "گزارش هنوز ساخته نشده است. می‌توانی بدون اینترنت گزارش محلی بگیری.",
        size=13, color=ON_SURFACE_VAR, rtl=True,
    )
    summary_box = ft.Column(_summary_rows(state["summary"]), spacing=5)
    period = ft.Dropdown(
        label="بازه‌ی تحلیل", rtl=True, text_size=13, dense=True, expand=True,
        value="7",
        options=[
            ft.DropdownOption(key="1", text="امروز"),
            ft.DropdownOption(key="7", text="۷ روز اخیر"),
            ft.DropdownOption(key="30", text="۳۰ روز اخیر"),
            ft.DropdownOption(key="90", text="۹۰ روز اخیر"),
        ],
    )
    temporary_key = ft.TextField(
        label="کلید API موقت (فقط همین نشست)", rtl=True, text_size=13,
        password=True, can_reveal_password=True, hint_text="sk-...", expand=True,
    )
    has_secure_store = bool(ctx.secure.available())
    temp_key_row: list[ft.Control] = [] if has_secure_store else [
        ft.Text("ذخیره‌سازی امن در این محیط در دسترس نیست؛ برای تست دسکتاپ، کلید را موقت وارد کن. این فیلد کلید را ذخیره نمی‌کند.",
                size=11, color=ON_SURFACE_VAR, rtl=True),
        temporary_key,
    ]

    def _refresh_summary(_e=None):
        try:
            days = int(period.value or "7")
        except ValueError:
            days = 7
        state["days"] = days
        state["summary"] = analytics.build_aggregate_summary(days)
        summary_box.controls = _summary_rows(state["summary"])
        result.value = "خلاصه به‌روزرسانی شد؛ گزارش موردنیاز را انتخاب کن."
        try: ctx.page.update()
        except Exception: pass

    period.on_change = _refresh_summary

    def _run_local(_e=None):
        summary = analytics.build_aggregate_summary(state["days"])
        content = ai.build_local_report(summary)
        try:
            models.save_report(summary["report_type"], summary["period_start"], summary["period_end"], content)
            suffix = "\n\nاین گزارش به‌صورت محلی ذخیره شد."
        except Exception:
            suffix = ""
        result.value = content + suffix
        result.color = ON_SURFACE
        try: ctx.page.update()
        except Exception: pass

    def _run_ai(_e=None):
        summary = analytics.build_aggregate_summary(state["days"])
        result.value = "در حال ارسال آمار تجمیعی و دریافت گزارش…"
        result.color = ON_SURFACE_VAR
        try: ctx.page.update()
        except Exception: pass

        async def _go():
            api_key = (temporary_key.value or "").strip()
            if not api_key:
                api_key = (await ctx.secure.get_async()) or ""
            endpoint = models.get_setting("ai_endpoint", "https://gapgpt.app/v1/chat/completions") or "https://gapgpt.app/v1/chat/completions"
            model = models.get_setting("ai_model", "gpt-5.4-mini") or "gpt-5.4-mini"
            try:
                content = await ai.request_report(summary["report_type"], summary, api_key, endpoint, model)
                models.save_report(summary["report_type"], summary["period_start"], summary["period_end"], content)
                result.value = content + "\n\nگزارش در پایگاه داده‌ی محلی ذخیره شد."
                result.color = ON_SURFACE
            except Exception as exc:
                result.value = f"گزارش GPT آماده نشد: {exc}\n\nگزارش آفلاین همچنان قابل استفاده است."
                result.color = ON_SURFACE_VAR
            try: ctx.page.update()
            except Exception: pass
        ctx.page.run_task(_go)

    recent_reports = models.list_reports(5)
    report_history_controls: list[ft.Control] = []
    if recent_reports:
        report_history_controls = [
            ft.Text("گزارش‌های ذخیره‌شده", size=13, weight=ft.FontWeight.W_600, color=ON_SURFACE, rtl=True),
        ]
        for r in recent_reports:
            report_history_controls.append(
                ft.Container(
                    padding=8, bgcolor=SURFACE_HIGH, border_radius=8,
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{r.type} • {r.period_start} تا {r.period_end}", size=11, color=ON_SURFACE, rtl=True),
                            ft.Text((r.content or "").replace("\n", " ")[:110], size=10, color=ON_SURFACE_VAR, rtl=True, max_lines=2),
                        ], spacing=2, expand=True),
                        ft.IconButton(icon=ft.Icons.OPEN_IN_NEW, tooltip="نمایش کامل", on_click=lambda _, report=r: _open_saved_report(ctx, report)),
                    ], spacing=6),
                )
            )

    content_controls: list[ft.Control] = [
        ft.Text("آمار قبل از ارسال", size=12, color=ON_SURFACE_VAR, rtl=True),
        ft.Container(padding=12, bgcolor=SURFACE_HIGH, border_radius=10, content=summary_box),
        ft.Text("حریم خصوصی: فقط آمار تجمیعی، روندها و ترازهای ثبت‌شده ارسال می‌شود؛ یادداشت‌ها و متن خام جلسات ارسال نمی‌شوند.", size=11, color=ON_SURFACE_VAR, rtl=True),
        *temp_key_row,
        ft.Container(height=4),
        ft.Row([
            outlined_button("گزارش آفلاین", on_click=_run_local, icon=ft.Icons.OFFLINE_BOLT_OUTLINED),
            filled_button("تحلیل با GPT", on_click=_run_ai, icon=ft.Icons.AUTO_AWESOME),
        ], spacing=8, wrap=True, alignment=ft.MainAxisAlignment.END),
        ft.Divider(height=1, color="#3A3F4B"),
        result,
    ]
    if report_history_controls:
        content_controls.extend([ft.Divider(height=1, color="#3A3F4B"), *report_history_controls])

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("دستیار تحلیل MAXPOINT", rtl=True, size=16, weight=ft.FontWeight.W_600),
        content=ft.Container(
            width=responsive_dialog_width(ctx.page, 380), height=responsive_dialog_height(ctx.page, 560),
            content=ft.Column([
                period,
                *content_controls,
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[text_button("بستن", on_click=lambda _: ctx.close_dialog(dlg))],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _summary_rows(summary: dict[str, Any]) -> list[ft.Control]:
    rows = [
        ("بازه", f"{summary.get('period_start','')} تا {summary.get('period_end','')}"),
        ("زمان ثبت‌شده", f"{to_fa(summary.get('total_recorded_minutes', 0))} دقیقه"),
        ("روزهای فعال", to_fa(summary.get("active_days", 0))),
        ("تست‌ها", to_fa(summary.get("tests", 0))),
        ("درست / غلط / نزده", " / ".join(to_fa(summary.get(k, 0)) for k in ("correct", "wrong", "blank"))),
        ("دقت پاسخ‌گویی", (to_fa(summary["accuracy_percent"]) + "٪") if summary.get("accuracy_percent") is not None else "داده‌ی کافی نیست"),
        ("روزهای دارای ثبت", to_fa(summary.get("data_quality_percent", 0)) + "٪"),
        ("آزمون ثبت‌شده", to_fa(summary.get("exam_count", 0))),
    ]
    rows.extend((f"زمان {r.get('group','سایر')}", f"{to_fa(r.get('minutes', 0))} دقیقه") for r in summary.get("minutes_by_group", []))
    return [
        ft.Row([
            ft.Text(k, size=11, color=ON_SURFACE_VAR, rtl=True, expand=True),
            ft.Text(v, size=11, color=ON_SURFACE, rtl=True, text_align=ft.TextAlign.LEFT),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8)
        for k, v in rows
    ]


def _open_saved_report(ctx, report) -> None:
    body = ft.Text(report.content, size=13, color=ON_SURFACE, rtl=True, selectable=True)
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("گزارش ذخیره‌شده", rtl=True, size=16, weight=ft.FontWeight.W_600),
        content=ft.Container(width=responsive_dialog_width(ctx.page, 360), height=responsive_dialog_height(ctx.page, 480), content=ft.Column([body], scroll=ft.ScrollMode.AUTO)),
        actions=[text_button("بستن", on_click=lambda _: ctx.close_dialog(dlg))],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)
