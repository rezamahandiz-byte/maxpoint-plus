"""Dedicated, visible notification center for MAXPOINT."""
from __future__ import annotations

import flet as ft
from core import models
from services import notifier as notifier_service
from ui import (
    ACCENT, ACCENT_SOFT, ON_SURFACE, ON_SURFACE_VAR, OUTLINE, SURFACE,
    SURFACE_HIGH, SUCCESS, WARN, border_all, card, divider, filled_button,
    outlined_button, pad_sym, section_title, text_button, to_fa,
)

DEFAULTS = {
    "reminders_enabled": "0", "reminder_interval": "60",
    "reminder_start": "8", "reminder_end": "22",
    "reminder_kind_study": "1", "reminder_kind_break": "1",
    "reminder_kind_log": "1", "reminder_kind_review": "0",
    "reminder_sound": "1", "reminder_sound_mode": "custom",
    "reminder_vibration": "1", "reminder_exact": "0",
    "reminder_weekdays": "0,1,2,3,4,5,6", "reminder_tone": "calm",
    "quiet_hours_enabled": "1", "quiet_start_hour": "22", "quiet_end_hour": "8",
}

KIND_META = [
    ("study", "شروع تمرکز", "یک تلنگر برای شروع یا برگشتن به درس", ft.Icons.MENU_BOOK_OUTLINED, "#8E9AFF"),
    ("break", "مکث و استراحت", "کمی کشش، آب و استراحت چشم", ft.Icons.COFFEE_OUTLINED, "#65D5C2"),
    ("log", "ثبت فعالیت", "ثبت زمان گذشته برای دقیق ماندن گزارش‌ها", ft.Icons.EDIT_NOTE_OUTLINED, "#F2C879"),
    ("review", "جمع‌بندی روز", "پیام پایانی حدود ۳۰ دقیقه پیش از پایان بازه", ft.Icons.AUTO_AWESOME, "#C8A0F2"),
]


def _setting(key: str) -> str:
    return models.get_setting(key, DEFAULTS.get(key, "0")) or DEFAULTS.get(key, "0")


def build(ctx) -> ft.Control:
    enabled = ft.Switch(value=_setting("reminders_enabled") == "1")
    interval = ft.Dropdown(
        label="تکرار هر", rtl=True, text_size=13, dense=True, width=145,
        value=_setting("reminder_interval"),
        options=[ft.DropdownOption(key=str(v), text=f"{to_fa(v)} دقیقه") for v in (30, 45, 60, 90, 120, 180, 240)],
    )
    start = ft.Dropdown(
        label="شروع بازه", rtl=True, text_size=13, dense=True, width=125,
        value=_setting("reminder_start"),
        options=[ft.DropdownOption(key=str(h), text=_hour_label(h)) for h in range(24)],
    )
    end = ft.Dropdown(
        label="پایان بازه", rtl=True, text_size=13, dense=True, width=125,
        value=_setting("reminder_end"),
        options=[ft.DropdownOption(key=str(h), text=_hour_label(h)) for h in range(1, 25)],
    )
    quiet_enabled = ft.Switch(value=_setting("quiet_hours_enabled") == "1")
    quiet_start = ft.Dropdown(
        label="شروع سکوت شبانه", rtl=True, text_size=13, dense=True, width=155,
        value=_setting("quiet_start_hour"),
        options=[ft.DropdownOption(key=str(h), text=_hour_label(h)) for h in range(24)],
    )
    quiet_end = ft.Dropdown(
        label="پایان سکوت", rtl=True, text_size=13, dense=True, width=145,
        value=_setting("quiet_end_hour"),
        options=[ft.DropdownOption(key=str(h), text=_hour_label(h)) for h in range(24)],
    )
    kind_switches = {
        kind: ft.Switch(value=_setting(f"reminder_kind_{kind}") == "1")
        for kind, *_ in KIND_META
    }
    sound = ft.Switch(value=_setting("reminder_sound") == "1")
    sound_mode_value = _setting("reminder_sound_mode")
    sound_mode = ft.Dropdown(
        label="نوع صدای اعلان", rtl=True, dense=True, text_size=13, width=235,
        value=sound_mode_value if sound_mode_value in {"custom", "system"} else "custom",
        options=[
            ft.DropdownOption(key="custom", text="زنگ اختصاصی MAXPOINT"),
            ft.DropdownOption(key="system", text="صدای پیش‌فرض گوشی"),
        ],
    )
    tone_value = _setting("reminder_tone")
    message_tone = ft.Dropdown(
        label="لحن پیام‌ها", rtl=True, dense=True, text_size=13, width=235,
        value=tone_value if tone_value in {"calm", "energetic", "minimal"} else "calm",
        options=[
            ft.DropdownOption(key="calm", text="آرام و بدون فشار"),
            ft.DropdownOption(key="energetic", text="پرانرژی و انگیزشی"),
            ft.DropdownOption(key="minimal", text="کوتاه و مینیمال"),
        ],
    )
    tone_preview_title = ft.Text("", size=13, color=ON_SURFACE,
                                 weight=ft.FontWeight.W_700, rtl=True)
    tone_preview_body = ft.Text("", size=11, color=ON_SURFACE_VAR, rtl=True)
    tone_preview = ft.Container(
        padding=pad_sym(horizontal=12, vertical=10), border_radius=12,
        bgcolor=SURFACE_HIGH, border=border_all(1, OUTLINE),
        content=ft.Row([
            ft.Container(width=34, height=34, border_radius=11, bgcolor=ACCENT_SOFT,
                         alignment=ft.Alignment(0, 0),
                         content=ft.Icon(ft.Icons.MESSAGE_OUTLINED, color=ACCENT, size=18)),
            ft.Column([tone_preview_title, tone_preview_body], spacing=3, expand=True),
        ], spacing=9),
    )

    def refresh_tone_preview(_e=None):
        sample = notifier_service.MESSAGE_TONES.get(
            str(message_tone.value or "calm"), notifier_service.MESSAGE_TONES["calm"]
        )["study"]
        tone_preview_title.value, tone_preview_body.value = sample
        try:
            ctx.page.update()
        except Exception:
            pass

    message_tone.on_change = refresh_tone_preview
    refresh_tone_preview()
    vibration = ft.Switch(value=_setting("reminder_vibration") == "1")
    exact = ft.Switch(value=_setting("reminder_exact") == "1")
    try:
        active_weekdays = {int(v) for v in _setting("reminder_weekdays").split(",") if v.strip()}
        active_weekdays = {v for v in active_weekdays if 0 <= v <= 6}
    except ValueError:
        active_weekdays = set(range(7))
    day_chips: dict[int, ft.Container] = {}

    status = _status_banner(bool(enabled.value), ctx)
    master_title = ft.Text(
        "اعلان‌ها روشن‌اند" if enabled.value else "فعال‌سازی اعلان‌ها",
        size=14, color=ON_SURFACE, weight=ft.FontWeight.W_700, rtl=True,
    )
    master_detail = ft.Text(
        "برنامه‌ی هفتگی روشن است؛ برای تغییر برنامه، ذخیره را بزن."
        if enabled.value else "برای شروع، این گزینه را روشن کن و در پایان «ذخیره و فعال‌سازی» را بزن.",
        size=11, color=ON_SURFACE_VAR, rtl=True,
    )
    master_icon = ft.Icon(
        ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED if enabled.value else ft.Icons.NOTIFICATIONS_OFF_OUTLINED,
        size=22, color=SUCCESS if enabled.value else WARN,
    )
    master_card = ft.Container(
        padding=14, border_radius=15,
        bgcolor="#1D332D" if enabled.value else SURFACE,
        border=border_all(1, "#315548" if enabled.value else OUTLINE),
        content=ft.Row([
            ft.Container(width=38, height=38, border_radius=12, bgcolor=SURFACE_HIGH,
                         alignment=ft.Alignment(0, 0), content=master_icon),
            ft.Column([master_title, master_detail], spacing=4, expand=True),
            enabled,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )
    preview = ft.Column(spacing=8)
    count_text = ft.Text("", size=12, color=ON_SURFACE_VAR, rtl=True)

    def selected_kinds() -> list[str]:
        return [kind for kind, switch in kind_switches.items() if bool(switch.value)]

    def selected_weekdays() -> list[int]:
        return sorted(active_weekdays)

    def update_day_chips() -> None:
        for day, chip in day_chips.items():
            chosen = day in active_weekdays
            chip.bgcolor = ACCENT_SOFT if chosen else SURFACE_HIGH
            chip.border = border_all(1, ACCENT if chosen else OUTLINE)
            if isinstance(chip.content, ft.Text):
                chip.content.color = "#F3F5FF" if chosen else ON_SURFACE_VAR

    def toggle_day(day: int):
        if day in active_weekdays:
            active_weekdays.remove(day)
        else:
            active_weekdays.add(day)
        update_day_chips()
        refresh_preview()

    # Iranian week order: Saturday → Friday. Short labels stay usable on narrow phones.
    DAY_OPTIONS = [(5, "ش", "شنبه"), (6, "ی", "یکشنبه"), (0, "د", "دوشنبه"),
                   (1, "س", "سه‌شنبه"), (2, "چ", "چهارشنبه"),
                   (3, "پ", "پنجشنبه"), (4, "ج", "جمعه")]
    for day, short_label, full_label in DAY_OPTIONS:
        day_chips[day] = ft.Container(
            width=40, height=40, border_radius=13,
            padding=4, alignment=ft.Alignment(0, 0), tooltip=full_label,
            bgcolor=ACCENT_SOFT if day in active_weekdays else SURFACE_HIGH,
            border=border_all(1, ACCENT if day in active_weekdays else OUTLINE),
            content=ft.Text(short_label, size=13, weight=ft.FontWeight.W_700,
                            color="#F3F5FF" if day in active_weekdays else ON_SURFACE_VAR,
                            text_align=ft.TextAlign.CENTER, rtl=True),
            on_click=lambda _e, d=day: toggle_day(d),
        )

    def refresh_preview(_e=None):
        status.content = _status_content(bool(enabled.value), ctx)
        master_title.value = "اعلان‌ها روشن‌اند" if enabled.value else "فعال‌سازی اعلان‌ها"
        master_detail.value = (
            "برنامه‌ی هفتگی روشن است؛ برای تغییر برنامه، ذخیره را بزن."
            if enabled.value else "برای شروع، این گزینه را روشن کن و در پایان «ذخیره و فعال‌سازی» را بزن."
        )
        master_icon.name = (ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED if enabled.value
                            else ft.Icons.NOTIFICATIONS_OFF_OUTLINED)
        master_icon.color = SUCCESS if enabled.value else WARN
        master_card.bgcolor = "#1D332D" if enabled.value else SURFACE
        master_card.border = border_all(1, "#315548" if enabled.value else OUTLINE)
        times = _preview_times(
            int(interval.value or "60"), int(start.value or "8"),
            int(end.value or "22"), selected_kinds(),
        )
        preview.controls = [_preview_row(item, i) for i, item in enumerate(times)]
        estimated_count = _actual_preview_count(
            int(interval.value or "60"), int(start.value or "8"),
            int(end.value or "22"), selected_kinds(),
        )
        weekly_count = estimated_count * len(active_weekdays)
        if enabled.value:
            count_text.value = (
                f"{to_fa(weekly_count)} نوبت در هفته · {to_fa(len(active_weekdays))} روز فعال"
                if active_weekdays else "هیچ روزی انتخاب نشده؛ برای فعال‌سازی روزهای هفته را انتخاب کن."
            )
        else:
            count_text.value = "پیش‌نمایش آماده است؛ اعلان‌ها هنوز خاموش‌اند."
        update_day_chips()
        try:
            ctx.page.update()
        except Exception:
            pass

    for control in [enabled, interval, start, end, quiet_enabled, quiet_start, quiet_end, *kind_switches.values()]:
        control.on_change = refresh_preview

    def save(_e):
        try:
            interval_value = int(interval.value or "60")
            start_value = int(start.value or "8")
            end_value = int(end.value or "22")
            if start_value >= end_value:
                raise ValueError
            kinds = selected_kinds()
            if enabled.value and not kinds:
                ctx.snack("حداقل یک نوع یادآور را روشن کن.")
                return
            quiet_start_value = int(quiet_start.value or "22")
            quiet_end_value = int(quiet_end.value or "8")
            if quiet_enabled.value and quiet_start_value == quiet_end_value:
                ctx.snack("ساعت شروع و پایان سکوت باید متفاوت باشند.")
                return
            days = selected_weekdays()
            if bool(enabled.value) and not days:
                ctx.snack("حداقل یک روز هفته را انتخاب کن؛ برای خاموش کردن همه‌ی اعلان‌ها فقط سوییچ اصلی را ببند.")
                return
        except (TypeError, ValueError):
            ctx.snack("بازه‌ی ساعت یا فاصله‌ی یادآور معتبر نیست.")
            return

        is_enabled = bool(enabled.value)
        saved = {
            "reminders_enabled": "1" if is_enabled else "0",
            "reminder_interval": str(interval_value),
            "reminder_start": str(start_value),
            "reminder_end": str(end_value),
            "reminder_sound": "1" if sound.value else "0",
            "reminder_sound_mode": str(sound_mode.value or "custom"),
            "reminder_vibration": "1" if vibration.value else "0",
            "reminder_exact": "1" if exact.value else "0",
            "reminder_weekdays": ",".join(str(day) for day in days),
            "reminder_tone": str(message_tone.value or "calm"),
            "quiet_hours_enabled": "1" if quiet_enabled.value else "0",
            "quiet_start_hour": str(quiet_start_value),
            "quiet_end_hour": str(quiet_end_value),
        }
        for kind, switch in kind_switches.items():
            saved[f"reminder_kind_{kind}"] = "1" if switch.value else "0"
        async def persist_settings():
            for key, value in saved.items():
                models.set_setting(key, value)

        async def apply_schedule():
            _ok, message = await notifier_service.configure_reminders(
                ctx.notifier, is_enabled, interval_value, start_value, end_value,
                kinds, bool(sound.value), bool(vibration.value),
                bool(exact.value), bool(exact.value),
                weekdays=days, sound_mode=str(sound_mode.value or "custom"),
                message_tone=str(message_tone.value or "calm"),
                quiet_hours_enabled=bool(quiet_enabled.value),
                quiet_start_hour=quiet_start_value, quiet_end_hour=quiet_end_value,
            )
            # Do not overwrite the last-known good plan if Android rejected the
            # new settings. Desktop still stores preferences for later APK use.
            if _ok or not notifier_service.available(ctx.notifier):
                await persist_settings()
            ctx.snack(message)
            try:
                ctx.refresh()
            except Exception:
                refresh_preview()
        ctx.page.run_task(apply_schedule)

    def test_notification(_e):
        async def send_test():
            _ok, message = await notifier_service.show_test_notification(
                ctx.notifier, bool(sound.value), bool(vibration.value),
                str(sound_mode.value or "custom"),
            )
            if _ok:
                # Show the actual test dialog
                notifier_service._show_notification(ctx)
            else:
                ctx.snack(message)
        ctx.page.run_task(send_test)

    def check_status(_e):
        async def inspect_status():
            _ok, message = await notifier_service.check_notification_status(ctx.notifier)
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("وضعیت مجوزهای اعلان", size=16,
                              weight=ft.FontWeight.W_700, rtl=True),
                content=ft.Container(
                    width=320,
                    content=ft.Text(message, size=13, color=ON_SURFACE,
                                    rtl=True, selectable=True),
                ),
                actions=[text_button("متوجه شدم", on_click=lambda _e: ctx.close_dialog(dlg))],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            ctx.open_dialog(dlg)
        ctx.page.run_task(inspect_status)

    def open_android_settings(_e):
        async def open_settings():
            _ok, message = await notifier_service.open_notification_settings(ctx.notifier)
            ctx.snack(message)
        ctx.page.run_task(open_settings)

    def reset_defaults(_e):
        enabled.value = False
        interval.value = "60"
        start.value = "8"
        end.value = "22"
        quiet_enabled.value = True
        quiet_start.value = "22"
        quiet_end.value = "8"
        for kind, switch in kind_switches.items():
            switch.value = kind != "review"
        active_weekdays.clear()
        active_weekdays.update(range(7))
        sound.value = True
        sound_mode.value = "custom"
        message_tone.value = "calm"
        vibration.value = True
        exact.value = False
        refresh_preview()
        ctx.snack("پیش‌فرض‌ها در فرم قرار گرفتند؛ برای ثبت، ذخیره را بزن.")

    hero = ft.Container(
        padding=18, border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
            colors=["#292F50", "#183B42"],
        ),
        border=border_all(1, "#3A5369"),
        content=ft.Row([
            ft.Container(
                width=54, height=54, border_radius=18, bgcolor="#34445A",
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED, size=28, color="#94F0D9"),
            ),
            ft.Column([
                ft.Text("اعلان به سبک خودت", size=19, weight=ft.FontWeight.W_700,
                        color="#FFFFFF", rtl=True),
                ft.Text("زمان، نوع پیام، صدا و لرزش را مدیریت کن.", size=12,
                        color="#D3E0EC", rtl=True),
            ], spacing=5, expand=True),
        ], spacing=13),
    )

    schedule_card = card([
        ft.Row([
            ft.Icon(ft.Icons.SCHEDULE, color=ACCENT, size=21),
            section_title("برنامه‌ی روزانه"), ft.Container(expand=True),
            ft.Container(padding=pad_sym(horizontal=10, vertical=5), border_radius=20,
                         bgcolor=ACCENT_SOFT,
                         content=ft.Text("قابل تنظیم", color="#DCE1FF", size=10, rtl=True)),
        ], spacing=8),
        ft.Text("اعلان اصلی می‌پرسد «درس می‌خونی؟»؛ با «آره» یک ساعت مکث می‌کند و با «نه» ده دقیقه بعد دوباره می‌پرسد.",
                size=12, color=ON_SURFACE_VAR, rtl=True),
        ft.Row([interval, start, end], spacing=8, wrap=True),
        divider(),
        _preference_row(ft.Icons.BEDTIME_OUTLINED, "سکوت شبانه",
                        "در این بازه اعلان پرسشی و یادآورهای دوره‌ای ارسال نمی‌شوند؛ بازه می‌تواند از نیمه‌شب عبور کند.", quiet_enabled, "#C8A0F2"),
        ft.Row([quiet_start, quiet_end], spacing=8, wrap=True),
        ft.Text("مثال: از ۲۲:۰۰ تا ۰۸:۰۰؛ صبح اعلان‌ها خودکار از سر گرفته می‌شوند.",
                size=10, color=ON_SURFACE_VAR, rtl=True),
        ft.Text("روزهای فعال · از شنبه تا جمعه", size=13, color=ON_SURFACE,
                weight=ft.FontWeight.W_600, rtl=True),
        ft.Row([day_chips[day] for day, *_ in DAY_OPTIONS], spacing=7, wrap=True),
        ft.Text("روزهای خاموش، هیچ یادآوری دوره‌ای دریافت نمی‌کنند.",
                size=11, color=ON_SURFACE_VAR, rtl=True),
        ft.Container(
            padding=pad_sym(horizontal=12, vertical=12), bgcolor=SURFACE_HIGH,
            border_radius=13,
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TIMELINE, color=ACCENT, size=18),
                    ft.Text("پیش‌نمایش نوبت‌ها", size=13, color=ON_SURFACE,
                            weight=ft.FontWeight.W_600, rtl=True),
                ], spacing=8),
                count_text, preview,
            ], spacing=8),
        ),
    ], padding=15)

    kind_rows = [_kind_row(title, description, icon, color, kind_switches[kind])
                 for kind, title, description, icon, color in KIND_META]
    kinds_card = card([
        section_title("چه چیزهایی را یادآوری کنم؟"),
        ft.Text("هر دسته را جداگانه روشن یا خاموش کن.", size=12, color=ON_SURFACE_VAR, rtl=True),
        ft.Column(kind_rows, spacing=8),
    ], padding=15)

    sound_card = card([
        section_title("صدا و بازخورد"),
        _preference_row(ft.Icons.VOLUME_UP_OUTLINED, "صدای اعلان",
                        "می‌توانی صدا را خاموش کنی یا یکی از دو نوع زنگ را انتخاب کنی.", sound, ACCENT),
        ft.Container(padding=pad_sym(horizontal=18, vertical=0), content=sound_mode),
        ft.Container(padding=pad_sym(horizontal=18, vertical=0), content=message_tone),
        tone_preview,
        divider(),
        _preference_row(ft.Icons.VIBRATION, "لرزش گوشی",
                        "برای اعلان‌های مهم، لرزش هم درخواست می‌شود.", vibration, "#65D5C2"),
        divider(),
        _preference_row(ft.Icons.SCHEDULE, "زمان‌بندی دقیق‌تر",
                        "با مجوز ویژه‌ی اندروید، تأخیر کمتر می‌شود؛ در غیر این صورت روش استاندارد استفاده می‌شود.", exact, "#F2C879"),
        ft.Text("اندروید تنظیمات کانال را نگه می‌دارد؛ اگر قبلاً صدا را از تنظیمات سیستم تغییر داده‌ای، همان‌جا هم بررسی کن.",
                size=11, color=ON_SURFACE_VAR, rtl=True),
    ], padding=15)

    actions = card([
        section_title("اعمال و آزمایش"),
        ft.Text("تغییرات پس از ذخیره در گوشی ثبت می‌شوند؛ دکمه‌ی آزمایش فقط یک اعلان فوری می‌فرستد.",
                size=12, color=ON_SURFACE_VAR, rtl=True),
        ft.Row([
            filled_button("ذخیره و فعال‌سازی", on_click=save, icon=ft.Icons.SAVE_OUTLINED),
            outlined_button("اعلان آزمایشی", on_click=test_notification,
                            icon=ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED),
        ], spacing=8, wrap=True),
        ft.Row([
            outlined_button("بررسی مجوزها", on_click=check_status, icon=ft.Icons.INFO_OUTLINE),
            text_button("تنظیمات اندروید", on_click=open_android_settings,
                        icon=ft.Icons.SETTINGS_OUTLINED),
        ], spacing=8, wrap=True),
        ft.Row([text_button("بازگشت به پیش‌فرض", on_click=reset_defaults,
                            icon=ft.Icons.RESTART_ALT)], alignment=ft.MainAxisAlignment.END),
    ], padding=15)

    refresh_preview()
    return ft.ListView(
        controls=[
            ft.Container(height=2),
            ft.Row([
                ft.Column([
                    ft.Text("مرکز اعلان‌ها", size=24, weight=ft.FontWeight.W_700,
                            color=ON_SURFACE, rtl=True),
                    ft.Text("زمان درست، یادآوری آرام و بدون فشار", size=12,
                            color=ON_SURFACE_VAR, rtl=True),
                ], spacing=3, expand=True),
                ft.Container(width=44, height=44, border_radius=15, bgcolor=ACCENT_SOFT,
                             alignment=ft.Alignment(0, 0),
                             content=ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED,
                                             color=ACCENT, size=23)),
            ]),
            ft.Container(height=12), hero, ft.Container(height=10), status,
            ft.Container(height=9), master_card, ft.Container(height=10),
            schedule_card, ft.Container(height=10),
            kinds_card, ft.Container(height=10), sound_card, ft.Container(height=10),
            actions, ft.Container(height=20),
            ft.Container(
                padding=pad_sym(horizontal=12, vertical=10), border_radius=11, bgcolor=SURFACE,
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=ON_SURFACE_VAR, size=17),
                    ft.Container(expand=True, content=ft.Text(
                        "اعلان واقعی در اندروید به مجوز اعلان، ساخت صحیح APK و محدودیت باتری گوشی وابسته است. نسخه‌ی ویندوز فقط برای تنظیم و پیش‌نمایش است.",
                        size=11, color=ON_SURFACE_VAR, rtl=True)),
                ], spacing=8),
            ),
            ft.Container(height=76),
        ], spacing=0, expand=True, auto_scroll=False,
    )


def on_show(ctx) -> None:
    return None


def _hour_label(hour: int) -> str:
    return f"{to_fa(f'{hour:02d}:00')}"


def _status_banner(enabled: bool, ctx) -> ft.Container:
    return ft.Container(
        padding=pad_sym(horizontal=13, vertical=11), border_radius=12,
        bgcolor="#1D332D" if enabled else SURFACE,
        border=border_all(1, "#315548" if enabled else OUTLINE),
        content=_status_content(enabled, ctx),
    )


def _status_content(enabled: bool, ctx) -> ft.Control:
    if enabled:
        headline = "یادآور روشن است"
        detail = "هنگام باز بودن برنامه، هر از گاهی پرسش «درس می‌خوانی؟» نمایش داده می‌شود."
        color, icon = SUCCESS, ft.Icons.CHECK_CIRCLE_OUTLINED
    else:
        headline = "یادآور فعلاً خاموش است"
        detail = "ساعت‌ها و نوع پیام‌ها را تنظیم کن و بعد فعال‌سازی را بزن."
        color, icon = WARN, ft.Icons.NOTIFICATIONS_OFF_OUTLINED
    return ft.Row([
        ft.Icon(icon, color=color, size=22),
        ft.Column([
            ft.Text(headline, size=13, color=ON_SURFACE, weight=ft.FontWeight.W_600, rtl=True),
            ft.Text(detail, size=11, color=ON_SURFACE_VAR, rtl=True),
        ], spacing=3, expand=True),
    ], spacing=10)


def _kind_row(title, description, icon, color, switch) -> ft.Control:
    return ft.Container(
        padding=pad_sym(horizontal=11, vertical=10), bgcolor=SURFACE_HIGH, border_radius=13,
        content=ft.Row([
            ft.Container(width=40, height=40, border_radius=12, bgcolor="#303746",
                         alignment=ft.Alignment(0, 0), content=ft.Icon(icon, color=color, size=21)),
            ft.Column([
                ft.Text(title, size=13, color=ON_SURFACE, weight=ft.FontWeight.W_600, rtl=True),
                ft.Text(description, size=11, color=ON_SURFACE_VAR, rtl=True),
            ], spacing=3, expand=True),
            switch,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )


def _preference_row(icon, title, description, switch, color) -> ft.Control:
    return ft.Row([
        ft.Container(width=36, height=36, border_radius=11, bgcolor=SURFACE_HIGH,
                     alignment=ft.Alignment(0, 0), content=ft.Icon(icon, color=color, size=20)),
        ft.Column([
            ft.Text(title, size=13, color=ON_SURFACE, rtl=True, weight=ft.FontWeight.W_500),
            ft.Text(description, size=11, color=ON_SURFACE_VAR, rtl=True),
        ], spacing=3, expand=True),
        switch,
    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _preview_times(interval: int, start: int, end: int, kinds: list[str]) -> list[dict]:
    if not (0 <= start < end <= 24) or interval <= 0 or not kinds:
        return []
    regular = [kind for kind in kinds if kind != "review"]
    review_minute = max(start * 60, min(end * 60 - 30, 23 * 60 + 30))
    minutes = list(range(start * 60, min(end * 60, 24 * 60), interval)) if regular else []
    rows: list[dict] = []
    for index, minute in enumerate(minutes):
        if "review" in kinds and minute == review_minute:
            continue
        kind = regular[index % len(regular)]
        hour, minute_part = divmod(minute, 60)
        rows.append({"time": f"{hour:02d}:{minute_part:02d}", "kind": kind})
    if "review" in kinds:
        hour, minute_part = divmod(review_minute, 60)
        rows.append({"time": f"{hour:02d}:{minute_part:02d}", "kind": "review"})
    rows.sort(key=lambda item: item["time"])
    if len(rows) > 6:
        rows = rows[:3] + [{"time": "…", "kind": "more"}] + rows[-2:]
    return rows


def _actual_preview_count(interval: int, start: int, end: int, kinds: list[str]) -> int:
    if not kinds or not (0 <= start < end <= 24):
        return 0
    regular = [kind for kind in kinds if kind != "review"]
    minutes = list(range(start * 60, min(end * 60, 24 * 60), interval)) if regular else []
    count = len(minutes)
    if "review" in kinds:
        review_minute = max(start * 60, min(end * 60 - 30, 23 * 60 + 30))
        if review_minute in minutes:
            count -= 1
        count += 1
    return count


def _preview_row(item: dict, index: int) -> ft.Control:
    kind = item["kind"]
    title = "چند نوبت دیگر" if kind == "more" else {
        "study": "شروع تمرکز", "break": "مکث و استراحت",
        "log": "ثبت فعالیت", "review": "جمع‌بندی روز",
    }.get(kind, kind)
    time = item["time"] if item["time"] == "…" else to_fa(item["time"])
    return ft.Row([
        ft.Container(width=8, height=8, border_radius=4,
                     bgcolor=ACCENT if index % 2 == 0 else "#65D5C2"),
        ft.Text(time, size=12, color=ON_SURFACE, weight=ft.FontWeight.W_600, rtl=True),
        ft.Container(width=1, height=14, bgcolor=OUTLINE),
        ft.Text(title, size=12, color=ON_SURFACE_VAR, rtl=True, expand=True),
    ], spacing=9)
