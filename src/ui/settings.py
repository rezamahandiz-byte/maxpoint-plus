"""Settings tab — clean, simple, expandable groups.

Design principle: Collapsed by default. The user sees 6 group titles.
Tap one to expand. No clutter.

Groups:
  1. یادآوری مطالعه — enable, quiet hours, interval, test
  2. مدیریت فعالیت‌ها — add, rename, activate/deactivate
  3. اهداف روزانه — per-activity minute target
  4. کلید OpenAI — API key + keystore
  5. پشتیبان و پاک‌سازی — JSON export/import, CSV export, clear
  6. درباره‌ی MAXPOINT — version info and feature list
"""
from __future__ import annotations

import flet as ft

from core import models
from services import backup as backup_service
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT,
    OUTLINE, SURFACE, SURFACE_HIGH, WARN,
    border_all, card, divider, filled_button, outlined_button,
    pad_sym, section_title, text_button, to_fa,
)


def build(ctx) -> ft.Control:
    return ft.ListView(
        [
            ft.Container(height=8),
            section_title("تنظیمات"),
            ft.Container(height=12),
            _theme_group(ctx),
            ft.Container(height=10),
            _reminders_group(ctx),
            ft.Container(height=10),
            _activities_group(ctx),
            ft.Container(height=10),
            _weekly_goals_matrix(ctx),
            ft.Container(height=10),
            _api_key_group(ctx),
            ft.Container(height=10),
            _backup_group(ctx),
            ft.Container(height=10),
            _about_group(ctx),
            ft.Container(height=80),
        ],
        spacing=0,
        expand=True,
        auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


# --------------------------------------------------------------------------- #
# Expandable group helper
# --------------------------------------------------------------------------- #


def _group(title: str, subtitle: str, icon: str,
           content: ft.Control) -> ft.Control:
    return ft.Container(
        bgcolor=SURFACE,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.ExpansionTile(
            title=ft.Column([
                ft.Text(title, size=15, weight=ft.FontWeight.W_600,
                        color=ON_SURFACE, rtl=True),
                ft.Text(subtitle, size=11, color=ON_SURFACE_MUT, rtl=True),
            ], spacing=2),
            leading=ft.Icon(icon, color=ACCENT, size=22),
            controls=[content],
            controls_padding=pad_sym(horizontal=12, vertical=8),
            tile_padding=pad_sym(horizontal=12, vertical=8),
            bgcolor=SURFACE,
            collapsed_bgcolor=SURFACE,
            shape=ft.RoundedRectangleBorder(radius=12),
            collapsed_shape=ft.RoundedRectangleBorder(radius=12),
        ),
    )


# --------------------------------------------------------------------------- #
# 1. Reminders
# --------------------------------------------------------------------------- #


def _reminders_group(ctx) -> ft.Control:
    from services import notifier as _n

    enabled = _n.is_enabled()
    interval = _n.get_interval()

    enable_switch = ft.Switch(
        value=enabled,
        label="فعال‌سازی یادآور",
        label_position=ft.LabelPosition.LEFT,
        on_change=lambda e: _toggle(ctx, e.control.value),
    )

    interval_dd = ft.Dropdown(
        label="فاصله یادآور", rtl=True, text_size=13, dense=True,
        options=[
            ft.DropdownOption(key="15", text=f"هر {to_fa(15)} دقیقه"),
            ft.DropdownOption(key="30", text=f"هر {to_fa(30)} دقیقه"),
            ft.DropdownOption(key="60", text=f"هر {to_fa(60)} دقیقه"),
        ],
        value=str(interval), expand=True,
        on_select=lambda e: _n.set_interval(int(interval_dd.value or 30)),
    )

    test_btn = outlined_button(
        "تست یادآور",
        on_click=lambda _: _n._show_notification(ctx),
        icon=ft.Icons.NOTIFICATIONS_OUTLINED,
    )

    return _group(
        "یادآوری مطالعه",
        "یادآوری دوره‌ای با ساعت سکوت",
        ft.Icons.NOTIFICATIONS_OUTLINED,
        ft.Column([
            enable_switch,
            ft.Container(height=8),
            ft.Text("ساعت سکوت (مثلاً خواب):", size=12,
                    color=ON_SURFACE_VAR, rtl=True),
            _quiet_hours_row(_n),
            ft.Container(height=8),
            interval_dd,
            ft.Container(height=8),
            ft.Text("با زدن «آره» یک ساعت سکوت، با زدن «نه» ۱۰ دقیقه بعد تکرار.",
                    size=10, color=ON_SURFACE_MUT, rtl=True),
            ft.Container(height=8),
            test_btn,
        ], spacing=0),
    )


def _quiet_hours_row(_n) -> ft.Control:
    opts = []
    for h in range(24):
        opts.append(ft.DropdownOption(
            key=f"{h:02d}:00",
            text=f"{to_fa(str(h).zfill(2))}:۰۰",
        ))
    start = ft.Dropdown(label="شروع", rtl=True, text_size=12, dense=True,
                        options=opts, value=_n.get_quiet_start(), expand=True,
                        on_select=lambda e: _n.set_quiet_start(start.value or "23:00"))
    end = ft.Dropdown(label="پایان", rtl=True, text_size=12, dense=True,
                      options=opts, value=_n.get_quiet_end(), expand=True,
                      on_select=lambda e: _n.set_quiet_end(end.value or "07:00"))
    return ft.Row([start, end], spacing=8)


def _toggle(ctx, value: bool) -> None:
    from services import notifier as _n
    _n.set_enabled(bool(value))
    ctx.snack("یادآور فعال شد." if value else "یادآور خاموش شد.")


# --------------------------------------------------------------------------- #
# 2. Activities
# --------------------------------------------------------------------------- #


def _activities_group(ctx) -> ft.Control:
    activities = models.list_activities(active_only=False)
    rows = []
    for a in activities:
        def _toggle(_e, item=a):
            models.set_activity_active(item.id, not item.is_active)
            ctx.refresh()

        rows.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=8),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Row([
                ft.Container(width=4, height=20, bgcolor=a.color or ACCENT,
                             border_radius=2),
                ft.Container(width=8),
                ft.Text(a.name, size=13, color=ON_SURFACE, rtl=True, expand=True),
                ft.Switch(value=bool(a.is_active), on_change=_toggle),
            ]),
        ))

    add_btn = outlined_button("افزودن فعالیت", on_click=lambda _: _add_dialog(ctx),
                              icon=ft.Icons.ADD)

    return _group(
        "مدیریت فعالیت‌ها",
        f"{to_fa(len(activities))} فعالیت",
        ft.Icons.MENU_BOOK_OUTLINED,
        ft.Column(rows + [ft.Container(height=8), add_btn], spacing=4),
    )


def _add_dialog(ctx) -> None:
    name = ft.TextField(label="نام", rtl=True, text_size=14, dense=True,
                        autofocus=True, expand=True)
    groups = models.list_groups()
    group_dd = ft.Dropdown(
        label="گروه", rtl=True, text_size=14, dense=True,
        options=[ft.DropdownOption(key=str(g.id), text=g.name) for g in groups],
        value=str(groups[0].id) if groups else None, expand=True,
    )

    def _save(_e):
        n = (name.value or "").strip()
        if not n:
            ctx.snack("نام را وارد کن.")
            return
        try:
            gid = int(group_dd.value) if group_dd.value else None
        except (TypeError, ValueError):
            gid = None
        models.create_activity(n, gid, color=ACCENT)
        ctx.close_dialog(dlg)
        ctx.snack("افزوده شد.")
        ctx.refresh()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("افزودن فعالیت", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Container(width=300, content=ft.Column([name, group_dd], spacing=8)),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("افزودن", on_click=_save, icon=ft.Icons.ADD),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


# --------------------------------------------------------------------------- #
# 3. Goals
# --------------------------------------------------------------------------- #


def _goals_group(ctx) -> ft.Control:
    activities = models.list_activities(active_only=True)
    if not activities:
        return _group("اهداف روزانه", "—", ft.Icons.FLAG_OUTLINED,
                      ft.Text("اول یک فعالیت اضافه کن.", size=13,
                              color=ON_SURFACE_VAR, rtl=True))

    rows = []
    for a in activities:
        goal = models.get_goal(a.id, "daily")
        field = ft.TextField(
            label="دقیقه/روز", rtl=True, text_size=12, dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            value=str(goal.target_minutes) if goal else "0",
            width=70, text_align=ft.TextAlign.CENTER,
        )

        def _save(_e, aid=a.id, f=field):
            try:
                v = int(f.value or 0)
            except ValueError:
                v = 0
            if v <= 0:
                from core import goals as _g
                _g.remove_goal(aid, "daily")
            else:
                from core import goals as _g
                _g.set_goal(aid, "daily", v, 0)

        field.on_blur = _save

        rows.append(ft.Container(
            padding=pad_sym(horizontal=10, vertical=6),
            bgcolor=SURFACE_HIGH, border_radius=8,
            content=ft.Row([
                ft.Container(width=4, height=20, bgcolor=a.color or ACCENT,
                             border_radius=2),
                ft.Container(width=8),
                ft.Text(a.name, size=13, color=ON_SURFACE, rtl=True, expand=True),
                field,
            ]),
        ))

    return _group(
        "اهداف روزانه",
        "دقیقه در روز برای هر فعالیت",
        ft.Icons.FLAG_OUTLINED,
        ft.Column(rows, spacing=4),
    )


# --------------------------------------------------------------------------- #
# 4. API key
# --------------------------------------------------------------------------- #


def _api_key_group(ctx) -> ft.Control:
    status = ctx.secure.status_message()
    available = ctx.secure.available()
    status_color = ACCENT if available else WARN

    key_field = ft.TextField(
        label="کلید OpenAI", rtl=True, text_size=13, dense=True,
        password=True, can_reveal_password=True, expand=True,
        hint_text="sk-...",
    )

    def _save(_e):
        val = (key_field.value or "").strip()
        if not val:
            ctx.snack("کلید را وارد کن.")
            return
        async def _go():
            ok = await ctx.secure.set_async(val)
            if ok:
                key_field.value = ""
                ctx.snack("کلید ذخیره شد.")
            else:
                ctx.snack("ذخیره ممکن نشد.")
            ctx.refresh()
        ctx.page.run_task(_go)

    def _delete(_e):
        async def _go():
            ok = await ctx.secure.delete_async()
            ctx.snack("حذف شد." if ok else "حذف ممکن نشد.")
            ctx.refresh()
        ctx.page.run_task(_go)

    return _group(
        "کلید OpenAI",
        "برای تحلیل هوشمند (اختیاری)",
        ft.Icons.LOCK_OUTLINED,
        ft.Column([
            ft.Text(status, size=12, color=status_color, rtl=True),
            ft.Container(height=8),
            key_field,
            ft.Container(height=8),
            ft.Row([
                outlined_button("ذخیره", on_click=_save, icon=ft.Icons.LOCK_OUTLINE),
                text_button("حذف کلید", on_click=_delete, icon=ft.Icons.DELETE_OUTLINE),
            ], spacing=8),
        ], spacing=0),
    )


# --------------------------------------------------------------------------- #
# 5. Backup + Clear
# --------------------------------------------------------------------------- #


def _backup_group(ctx) -> ft.Control:
    file_picker = ctx.get_file_picker()
    state = {"mode": "export"}

    def _on_result(e):
        if not e.files:
            return
        if state["mode"] == "import":
            _confirm_import(ctx, e.files[0].path)

    if file_picker is not None:
        file_picker.on_result = _on_result

    def _export(_e):
        if file_picker is None:
            ctx.snack("انتخاب فایل پشتیبانی نمی‌شود.")
            return
        state["mode"] = "export"
        file_picker.save_file(file_name="maxpoint-backup.json",
                              allowed_extensions=["json"])

    def _import(_e):
        if file_picker is None:
            ctx.snack("انتخاب فایل پشتیبانی نمی‌شود.")
            return
        state["mode"] = "import"
        file_picker.pick_files(allow_multiple=False, allowed_extensions=["json"])

    # CSV export — runs the async save_file dialog and writes content directly.
    def _csv(kind: str):
        if file_picker is None:
            ctx.snack("انتخاب فایل پشتیبانی نمی‌شود.")
            return

        async def _go():
            try:
                from core import exporter
                name_map = {
                    "sessions": ("maxpoint-sessions.csv", exporter.sessions_csv),
                    "exams":    ("maxpoint-exams.csv",    exporter.exams_csv),
                    "tests":    ("maxpoint-tests.csv",    exporter.tests_csv),
                    "full":     ("maxpoint-full.csv",     exporter.full_csv),
                }
                file_name, builder = name_map[kind]
                path = await file_picker.save_file(
                    file_name=file_name, allowed_extensions=["csv"],
                )
                if not path:
                    return  # user cancelled
                content = builder()
                exporter.export_to_file(path, content)
                ctx.snack(f"CSV ذخیره شد: {path}")
            except Exception as exc:
                ctx.snack(f"خطا در صدور CSV: {str(exc)[:120]}")

        ctx.page.run_task(_go)

    def _clear(_e):
        _confirm_clear(ctx)

    return _group(
        "پشتیبان و پاک‌سازی",
        "خروجی JSON، بازیابی، صدور CSV، حذف همه",
        ft.Icons.BACKUP_OUTLINED,
        ft.Column([
            ft.Text("پشتیبان JSON کامل", size=12, color=ON_SURFACE,
                    weight=ft.FontWeight.W_600, rtl=True),
            ft.Container(height=4),
            ft.Row([
                outlined_button("خروجی", on_click=_export, icon=ft.Icons.DOWNLOAD_OUTLINED),
                outlined_button("بازیابی", on_click=_import, icon=ft.Icons.UPLOAD_OUTLINED),
            ], spacing=8),
            ft.Container(height=10),
            divider(),
            ft.Container(height=8),
            ft.Text("صدور CSV (برای اکسل یا Google Sheets)", size=12,
                    color=ON_SURFACE, weight=ft.FontWeight.W_600, rtl=True),
            ft.Container(height=4),
            ft.Row([
                outlined_button("جلسات", on_click=lambda _: _csv("sessions"),
                                icon=ft.Icons.SCHOOL_OUTLINED),
                outlined_button("آزمون‌ها", on_click=lambda _: _csv("exams"),
                                icon=ft.Icons.ASSIGNMENT_OUTLINED),
            ], spacing=8),
            ft.Row([
                outlined_button("تست‌ها", on_click=lambda _: _csv("tests"),
                                icon=ft.Icons.QUIZ_OUTLINED),
                outlined_button("همه (یک فایل)", on_click=lambda _: _csv("full"),
                                icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED),
            ], spacing=8),
            ft.Container(height=10),
            divider(),
            ft.Container(height=8),
            ft.Text("پاک‌سازی بازگشت‌ناپذیر است.", size=11, color=WARN, rtl=True),
            ft.Container(height=4),
            text_button("پاک‌سازی همه داده‌ها", on_click=_clear,
                        icon=ft.Icons.DELETE_FOREVER),
        ], spacing=0),
    )


def _confirm_import(ctx, path: str) -> None:
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("بازیابی؟", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Text("داده‌های فعلی با فایل جایگزین می‌شود.",
                        rtl=True, size=14, color=ON_SURFACE_VAR),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(dlg)),
            filled_button("بازیابی", on_click=lambda _: _do_import(ctx, dlg, path)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(dlg)


def _do_import(ctx, dlg, path: str) -> None:
    try:
        backup_service.restore_from_file(path)
        ctx.close_dialog(dlg)
        ctx.snack("بازیابی شد.")
        ctx.refresh()
    except Exception as e:
        ctx.close_dialog(dlg)
        ctx.snack(f"خطا: {e}")


def _confirm_clear(ctx) -> None:
    field = ft.TextField(label="برای تایید PAKE را بنویس", rtl=True,
                         text_size=13, dense=True, autofocus=True, expand=True)

    def _next(_e):
        if (field.value or "").strip() == "PAKE":
            ctx.close_dialog(d1)
            _final_confirm(ctx)
        else:
            ctx.snack("عبارت درست نیست.")

    d1 = ft.AlertDialog(
        modal=True,
        title=ft.Text("تایید اول", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Container(width=300, content=ft.Column([
            ft.Text("عبارت PAKE را وارد کن.", rtl=True, size=14,
                    color=ON_SURFACE_VAR),
            field,
        ], spacing=8)),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(d1)),
            filled_button("ادامه", on_click=_next),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(d1)


def _final_confirm(ctx) -> None:
    d2 = ft.AlertDialog(
        modal=True,
        title=ft.Text("تایید نهایی", rtl=True, size=18, weight=ft.FontWeight.W_600),
        content=ft.Text("همه داده‌ها حذف شود؟ بازگشت‌ناپذیر است.",
                        rtl=True, size=14, color=ON_SURFACE_VAR),
        actions=[
            text_button("انصراف", on_click=lambda _: ctx.close_dialog(d2)),
            filled_button("بله، حذف کن", on_click=lambda _: _do_clear(ctx, d2),
                          icon=ft.Icons.DELETE_FOREVER),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    ctx.open_dialog(d2)


def _do_clear(ctx, dlg) -> None:
    from core import db as _db
    with _db.connect() as c:
        for t in ["sessions", "goals", "exam_subjects", "exams",
                  "reports", "settings", "activities", "activity_groups"]:
            c.execute(f"DELETE FROM {t};")
        _db._seed(c)
    ctx.close_dialog(dlg)
    ctx.snack("همه پاک شد.")
    ctx.refresh()


# --------------------------------------------------------------------------- #
# 6. About — version info + feature list
# --------------------------------------------------------------------------- #


_APP_VERSION = "۰.۸.۲"
_BUILD_DATE = "۱۴۰۵/۰۸/۰۷"

_FEATURES = [
    ("ثبت جلسات مطالعه", "با درس، دقیقه، تست و یادداشت"),
    ("زمان‌سنج زنده", "شروع/مکث/پایان با ذخیره‌ی خودکار زمان"),
    ("ثبت آزمون خودآزمایی", "با درصد و نتیجه‌ی هر درس"),
    ("نمودار تحلیل", "۷ روز، ۴ هفته، روند تراز، کیفیت تست"),
    ("نقشه‌ی ۳۰ روزه", "روزهای متوالی و روزهای فعال"),
    ("تحلیل تست", "دقت، روند، درس‌های ضعیف، ساعات پربازده"),
    ("صدور CSV", "برای اکسل یا Google Sheets"),
    ("پشتیبان JSON", "خروجی و بازیابی کامل"),
    ("تقویم شمسی", "نمایش تاریخ و روز هفته"),
    ("یادآوری درون‌برنامه‌ای", "با ساعت سکوت و فاصله‌ی قابل تنظیم"),
    ("ساعت آنلاین", "بررسی زمان با fallback آفلاین"),
    ("تحلیل هوشمند (GPT)", "با کلید API اختیاری"),
]


def _about_group(ctx) -> ft.Control:
    content = ft.Column([
        ft.Row([
            ft.Container(
                width=48, height=48, border_radius=14, bgcolor=ACCENT_SOFT,
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(ft.Icons.SCHOOL_OUTLINED, color=ACCENT, size=26),
            ),
            ft.Container(width=12),
            ft.Column([
                ft.Text("MAXPOINT-Plus", size=16, color=ON_SURFACE,
                        weight=ft.FontWeight.W_700, rtl=True),
                ft.Text(f"نسخه {_APP_VERSION} — {_BUILD_DATE}", size=11,
                        color=ON_SURFACE_VAR, rtl=True),
            ], spacing=2, expand=True),
        ]),
        ft.Container(height=8),
        ft.Text(
            "دستیار شخصی مطالعه، مدیریت زمان و تحلیل عملکرد تحصیلی. "
            "همه‌ی داده‌ها روی دستگاهت ذخیره می‌شوند — بدون سرور، بدون ابر.",
            size=12, color=ON_SURFACE_VAR, rtl=True,
        ),
        ft.Container(height=10),
        divider(),
        ft.Container(height=10),
        ft.Text("امکانات:", size=13, color=ON_SURFACE,
                weight=ft.FontWeight.W_600, rtl=True),
        ft.Container(height=4),
        ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ACCENT, size=14),
                ft.Container(width=6),
                ft.Text(title, size=12, color=ON_SURFACE, rtl=True, expand=True),
                ft.Text(desc, size=10, color=ON_SURFACE_MUT, rtl=True),
            ], spacing=0)
            for title, desc in _FEATURES
        ], spacing=4),
        ft.Container(height=10),
        divider(),
        ft.Container(height=8),
        ft.Text(
            "ساخته‌شده با Python + Flet + SQLite. کد منبع باز و قابل بررسی است.",
            size=10, color=ON_SURFACE_MUT, rtl=True,
        ),
    ], spacing=0)

    return _group(
        "درباره‌ی MAXPOINT",
        f"نسخه {_APP_VERSION} — اطلاعات برنامه",
        ft.Icons.INFO_OUTLINED,
        content,
    )


# --------------------------------------------------------------------------- #
# Theme switcher
# --------------------------------------------------------------------------- #


def _theme_group(ctx) -> ft.Control:
    """Light/Dark theme toggle using a simple Switch."""
    from ui.theme import get_theme_mode
    current = get_theme_mode()
    is_light = (current == "light")

    def _on_change(e):
        mode = "light" if e.control.value else "dark"
        ctx.switch_theme(mode)

    return _group(
        "ظاهر",
        "حالت روشن یا تیره",
        ft.Icons.PALETTE_OUTLINED,
        ft.Row([
            ft.Icon(ft.Icons.LIGHT_MODE_OUTLINED if is_light else ft.Icons.DARK_MODE_OUTLINED,
                    color=ACCENT, size=22),
            ft.Column([
                ft.Text("حالت روشن" if is_light else "حالت تیره",
                        size=14, color=ON_SURFACE, rtl=True,
                        weight=ft.FontWeight.W_600),
                ft.Text("روشن کردن پس‌زمینه",
                        size=11, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=2, expand=True),
            ft.Switch(
                value=is_light,
                on_change=_on_change,
                active_color=ACCENT,
            ),
        ], spacing=10),
    )


# --------------------------------------------------------------------------- #
# Weekly Goals Matrix (روزهای هفته × دروس)
# --------------------------------------------------------------------------- #


def _weekly_goals_matrix(ctx) -> ft.Control:
    """A grid: rows=days, columns=activities, cells=editable minute targets."""
    activities = models.list_activities(active_only=True)
    day_names = models.WEEKLY_DAY_NAMES  # ["شنبه", "یکشنبه", ...]

    # Load existing goals into a dict: {(activity_id, day): minutes}
    existing = models.get_all_weekly_goals()
    goal_map = {(g["activity_id"], g["day_of_week"]): g["target_minutes"] for g in existing}

    # Build DataTable
    columns = [
        ft.DataColumn(
            ft.Text("روز", size=13, color=ON_SURFACE_VAR, weight=ft.FontWeight.W_600, rtl=True),
        )
    ]
    for act in activities[:6]:  # max 6 subjects for screen width
        columns.append(
            ft.DataColumn(
                ft.Text(act.name, size=12, color=ON_SURFACE, rtl=True,
                        weight=ft.FontWeight.W_500),
            )
        )

    rows: list[ft.DataRow] = []
    field_refs: dict[tuple[int, int], ft.TextField] = {}

    for day_idx in range(7):
        cells: list[ft.DataCell] = []
        cells.append(ft.DataCell(
            ft.Text(day_names[day_idx], size=13, color=ON_SURFACE, rtl=True,
                    weight=ft.FontWeight.W_500)
        ))
        for act in activities[:6]:
            current_val = goal_map.get((act.id, day_idx), 0)
            field = ft.TextField(
                value=str(current_val) if current_val > 0 else "",
                width=45,
                text_size=12,
                text_align=ft.TextAlign.CENTER,
                dense=True,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.NumbersOnlyInputFilter(),
            )
            field_refs[(act.id, day_idx)] = field
            cells.append(ft.DataCell(field))
        rows.append(ft.DataRow(cells=cells))

    def _save_all(_e=None):
        saved = 0
        for (act_id, day_idx), field in field_refs.items():
            try:
                val = int(field.value or "0")
            except (TypeError, ValueError):
                val = 0
            models.set_weekly_goal(act_id, day_idx, val)
            if val > 0:
                saved += 1
        ctx.snack(f"{to_fa(saved)} هدف هفتگی ذخیره شد.")

    save_btn = filled_button("ذخیره اهداف هفتگی", on_click=_save_all,
                             icon=ft.Icons.SAVE_OUTLINED)

    content = ft.Column([
        ft.Text(
            "برای هر درس در هر روز هفته، هدف دقیقه وارد کن. ۰ یا خالی = بدون هدف.",
            size=11, color=ON_SURFACE_VAR, rtl=True,
        ),
        ft.Container(height=8),
        ft.Column(
            [ft.DataTable(
                columns=columns,
                rows=rows,
                column_spacing=8,
                horizontal_margin=4,
                heading_row_height=36,
                data_row_min_height=40,
                data_row_max_height=44,
            )],
            scroll=ft.ScrollMode.AUTO,
        ),
        ft.Container(height=8),
        save_btn,
    ], spacing=0)

    return _group(
        "اهداف هفتگی (جدول)",
        "هدف هر درس برای هر روز هفته",
        ft.Icons.GRID_VIEW_OUTLINED,
        content,
    )
