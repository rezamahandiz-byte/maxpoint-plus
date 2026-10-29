"""MAXPOINT entry point.

Run:  flet run src/main.py
Web:  flet run --web src/main.py

Architecture:
    main(page) constructs an `AppContext` (page + shared services + helpers),
    sets up the dark RTL theme, mounts the bottom navigation bar, and swaps
    the active tab's view in a single content container.

Each tab module (ui/home.py, ui/record.py, ui/analysis.py, ui/settings.py)
exposes:
    build(ctx) -> ft.Control          builds the tab's root control
    on_show(ctx) -> None              (optional) called every time tab is shown

The Assistant is reachable from inside the Analysis tab (button), not a tab.
"""
from __future__ import annotations

import sys
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import flet as ft

# Make `core`, `ui`, `services` importable when launched via `flet run src/main.py`.
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core import db, study_session
from core.fa_dates import jalali_label
from services import secure as secure_service
from services import notifier as notifier_service
from services import clock_sync
from ui.theme import DarkColors, LightColors, Typography, Spacing, Radius, Layout, get_theme_mode, set_theme_mode
from ui import home as ui_home
from ui import study as ui_study
from ui import charts as ui_charts
from ui import exam as ui_exam
from ui import test as ui_test
from ui import settings as ui_settings


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #


def _build_color_scheme(c) -> ft.ColorScheme:
    """Build a ColorScheme from a color class (DarkColors or LightColors)."""
    return ft.ColorScheme(
        primary=c.accent,
        on_primary=c.accent_text,
        primary_container=c.accent_muted,
        on_primary_container=c.text_primary,
        secondary=c.accent,
        on_secondary=c.accent_text,
        secondary_container=c.surface_2,
        on_secondary_container=c.text_primary,
        tertiary=c.info,
        surface=c.bg,
        surface_container=c.surface_1,
        surface_container_high=c.surface_2,
        surface_container_highest=c.surface_3,
        on_surface=c.text_primary,
        on_surface_variant=c.text_secondary,
        outline=c.surface_3,
        outline_variant=c.surface_3,
        error=c.warning,
        error_container=c.surface_2,
        on_error=c.bg,
    )


def _build_theme_for(c) -> ft.Theme:
    """Build a full Theme from a color class."""
    return ft.Theme(
        color_scheme=_build_color_scheme(c),
        color_scheme_seed=c.accent,
        font_family="Noto Sans",
        use_material3=True,
        scaffold_bgcolor=c.bg,
        canvas_color=c.bg,
        divider_color=c.surface_3,
        navigation_bar_theme=ft.NavigationBarTheme(
            bgcolor=c.surface_1,
            indicator_color=c.accent_muted,
            label_text_style=ft.TextStyle(size=Typography.tiny, weight=ft.FontWeight.W_600),
        ),
        card_theme=ft.CardTheme(
            color=c.surface_1,
            elevation=0,
            shape=ft.RoundedRectangleBorder(radius=Radius.md),
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=c.surface_2,
            shape=ft.RoundedRectangleBorder(radius=Radius.lg),
        ),
        snackbar_theme=ft.SnackBarTheme(
            bgcolor=c.surface_2,
            content_text_style=ft.TextStyle(color=c.text_primary, size=Typography.small),
        ),
        floating_action_button_theme=ft.FloatingActionButtonTheme(
            bgcolor=c.accent,
            foreground_color=c.accent_text,
        ),
        appbar_theme=ft.AppBarTheme(
            bgcolor=c.bg,
            color=c.text_primary,
            center_title=False,
            elevation=0,
        ),
    )


def _build_theme() -> ft.Theme:
    """Build the theme for the current mode (dark or light)."""
    mode = get_theme_mode()
    return _build_theme_for(LightColors if mode == "light" else DarkColors)


# --------------------------------------------------------------------------- #
# App context
# --------------------------------------------------------------------------- #


@dataclass
class AppContext:
    """Shared state handed to every tab module."""
    page: ft.Page
    secure: "secure_service.SecureKeyStore"
    notifier: object | None = None
    current_tab: int = 0
    file_picker: Optional[ft.FilePicker] = None
    audio: Optional[ft.Audio] = None
    _content: Optional[ft.Control] = field(default=None, repr=False)
    _handlers: dict = field(default_factory=dict, repr=False)

    def get_file_picker(self) -> ft.FilePicker:
        """Lazily create one FilePicker service per app session.

        FilePicker is a Service (auto-registers with the page); creating it
        multiple times would leak. We keep a single instance on the context.
        """
        if self.file_picker is None:
            try:
                self.file_picker = ft.FilePicker()
            except Exception:
                # Web/desktop without picker support — return a stub that
                # the caller can detect via `on_result is None`.
                self.file_picker = None
        return self.file_picker

    # ---- navigation ----
    def set_tab(self, index: int) -> None:
        self.current_tab = index
        self.page.navigation_bar.selected_index = index
        self._render()
        self._update_fab()
        self.page.update()

    # ---- content rendering ----
    def _render(self) -> None:
        # Widget references are valid only for the just-built view; clearing
        # avoids the timer loop touching controls detached by tab navigation.
        self._handlers.clear()
        view = self._build_current_view()
        if self._content is None:
            self._content = ft.Container(
                content=view,
                expand=True,
                padding=ft.Padding(left=Layout.screen_edge, top=10, right=Layout.screen_edge, bottom=10),
            )
            # remove old controls except navigation_bar/fab (managed separately)
            self.page.controls.clear()
            self.page.add(self._content)
        else:
            self._content.content = view
        # post-render hook
        mod = self._tab_module(self.current_tab)
        on_show = getattr(mod, "on_show", None)
        if on_show:
            on_show(self)

    def _build_current_view(self) -> ft.Control:
        mod = self._tab_module(self.current_tab)
        return mod.build(self)

    def _tab_module(self, index: int):
        return {
            0: ui_home,
            1: ui_study,
            2: ui_charts,
            3: ui_exam,
            4: ui_test,
            5: ui_settings,
        }[index]

    def refresh(self) -> None:
        """Rebuild the current tab (e.g. after recording a session)."""
        self._render()
        self.page.update()

    def switch_theme(self, mode: str) -> None:
        """Switch between 'dark' and 'light' theme at runtime.
        Reloads colors and rebuilds the entire page."""
        set_theme_mode(mode)
        from ui import reload_colors
        reload_colors()
        from ui.theme import active_colors
        c = active_colors()
        self.page.theme_mode = ft.ThemeMode.LIGHT if mode == "light" else ft.ThemeMode.DARK
        self.page.bgcolor = c.bg
        # Force full page rebuild — clear content and re-render
        self._content = None
        self.page.controls.clear()
        self._render()
        self._update_fab()
        self.page.update()

    # ---- FAB ----
    def _update_fab(self) -> None:
        # FAB on Home (0) and Record (1) — both benefit from quick add.
        if self.current_tab in (0, 1):
            self.page.floating_action_button = ft.FloatingActionButton(
                icon=ft.Icons.ADD,
                tooltip="ثبت سریع",
                on_click=lambda _: self.set_tab(1),
            )
        else:
            self.page.floating_action_button = None

    # ---- helpers ----
    def snack(self, msg: str) -> None:
        """Show a short SnackBar message.

        Flet 1.0.x has no `page.open()` — SnackBars go into `page.overlay`
        with `open=True` and are removed by their own dismiss timer.
        """
        snackbar = ft.SnackBar(
            content=ft.Text(value=msg, rtl=True),
            duration=2500,
            open=True,
        )
        try:
            self.page.overlay.append(snackbar)
            self.page.update()
        except Exception:
            # Last-resort: ignore — UI is non-blocking
            pass

    def open_dialog(self, dlg: ft.AlertDialog) -> None:
        """Open a modal dialog using the Flet 1.0.x API (`show_dialog`)."""
        try:
            self.page.show_dialog(dlg)
        except Exception:
            # Fallback for older/newer Flet variants that use page.open()
            try:
                self.page.open(dlg)
            except Exception:
                dlg.open = True
                self.page.dialog = dlg
                self.page.update()

    def close_dialog(self, dlg: ft.AlertDialog) -> None:
        """Close the topmost open dialog.

        Flet 1.0.x uses `page.pop_dialog()` which closes the most recently
        opened dialog. We assume dialogs are opened/closed in LIFO order
        (which is true for every flow in this app).
        """
        try:
            self.page.pop_dialog()
        except Exception:
            try:
                self.page.close(dlg)
            except Exception:
                dlg.open = False
                self.page.update()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(page: ft.Page) -> None:
    # 1. Database first — every screen depends on it.
    db.init_db()

    # 2. Page config — dual theme support.
    page.title = "MAXPOINT"
    page.dark_theme = _build_theme_for(DarkColors)
    page.theme = _build_theme_for(LightColors)
    mode = get_theme_mode()
    page.theme_mode = ft.ThemeMode.LIGHT if mode == "light" else ft.ThemeMode.DARK
    page.rtl = True
    _c = LightColors if mode == "light" else DarkColors
    page.bgcolor = _c.bg
    page.padding = 0
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.CrossAxisAlignment.START
    page.scroll = ft.ScrollMode.AUTO

    # 3. Secure storage service (auto-registers with the page on Android;
    #    on desktop the wrapper reports "unavailable" and the UI degrades).
    secure = secure_service.SecureKeyStore(page)
    notifier_holder = {"service": None}

    def notification_callback(event):
        """Handle Yes/No actions delivered by Android, including cold-start replay."""
        try:
            raw = getattr(event, "data", event)
            data = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(data, dict):
                return
            payload = str(data.get("payload", "") or "")
            action_id = str(data.get("action_id", data.get("actionId", "")) or "")
            if payload == "maxpoint_focus_prompt" and action_id in {"focus_yes", "focus_no"}:
                service = notifier_holder.get("service")
                if service is not None:
                    page.run_task(notifier_service.handle_focus_prompt_action, service, action_id)
        except Exception:
            # Notification taps must never crash the foreground app.
            return

    notifier = notifier_service.init(page.platform, on_notification_tap=notification_callback)
    notifier_holder["service"] = notifier

    ctx = AppContext(page=page, secure=secure, notifier=notifier)

    # 3b. Audio — for the notification chime. Registered once on the page overlay.
    try:
        ctx.audio = ft.Audio(src="sounds/focus_chime.wav", autoplay=False)
        page.overlay.append(ctx.audio)
    except Exception:
        ctx.audio = None  # audio unavailable — notifier silently skips it

    # 4. Bottom navigation — 6 tabs: Home, Record, Charts, Exam, Test, Settings.
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME,
                label="خانه"),
            ft.NavigationBarDestination(
                icon=ft.Icons.EDIT_NOTE_OUTLINED, selected_icon=ft.Icons.EDIT_NOTE,
                label="ثبت"),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED, selected_icon=ft.Icons.BAR_CHART,
                label="نمودار"),
            ft.NavigationBarDestination(
                icon=ft.Icons.SCHOOL_OUTLINED, selected_icon=ft.Icons.SCHOOL,
                label="آزمون"),
            ft.NavigationBarDestination(
                icon=ft.Icons.QUIZ_OUTLINED, selected_icon=ft.Icons.QUIZ,
                label="تست"),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS,
                label="تنظیمات"),
        ],
        selected_index=0,
        on_change=lambda e: ctx.set_tab(e.control.selected_index),
    )

    # 5. Initial render.
    ctx._render()
    ctx._update_fab()
    page.update()
    # Start background services:
    # - notifier.loop: in-app "درس می‌خوانی؟" reminder (works on all platforms)
    # - clock_sync.periodic_sync: online time verification
    # - _timer_tick_loop: study timer display refresh
    try:
        page.run_task(notifier_service.restore_saved_settings, notifier)
        page.run_task(notifier_service.loop, ctx)
        page.run_task(clock_sync.periodic_sync, ctx)
        page.run_task(_timer_tick_loop, ctx)
    except Exception:
        pass


async def _timer_tick_loop(ctx: AppContext) -> None:
    """Refresh the visible timer once a second without rebuilding the whole UI."""
    while True:
        try:
            if ctx.current_tab == 0:
                handlers = ctx._handlers
                session = study_session.get_active()
                timer_text = handlers.get("timer_value")
                if session is not None and timer_text is not None:
                    seconds = session.elapsed_seconds(clock_sync.now_utc())
                    hours, rem = divmod(seconds, 3600)
                    minutes, secs = divmod(rem, 60)
                    timer_text.value = str(f"{hours:02d}:{minutes:02d}:{secs:02d}").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
                clock_title = handlers.get("clock_title")
                if clock_title is not None:
                    now = clock_sync.now_local()
                    from ui import to_fa
                    clock_title.value = f"{to_fa(now.strftime('%H:%M:%S'))} · {jalali_label(now.date().isoformat())}"
                # Reflect online/offline transitions without rebuilding the home
                # screen: a full rebuild here would reset fields the user is editing.
                clock_detail = handlers.get("clock_detail")
                status_icon = handlers.get("clock_status_icon")
                status_badge = handlers.get("clock_status_badge")
                status_text = handlers.get("clock_status_text")
                if clock_detail is not None:
                    status, synced_at = clock_sync.sync_status()
                    online = status == "online"
                    new_detail = (
                        f"زمان آنلاین آخرین بار ساعت {to_fa(synced_at)} بررسی شده؛ در نبود اینترنت از ساعت دستگاه استفاده می‌شود."
                        if online else "آفلاین یا هنوز همگام‌سازی نشده؛ برنامه بدون خطا از ساعت دستگاه استفاده می‌کند و با اتصال دوباره بررسی می‌کند."
                    )
                    if clock_detail.value != new_detail:
                        clock_detail.value = new_detail
                    if status_icon is not None:
                        status_icon.name = ft.Icons.SYNC if online else ft.Icons.SCHEDULE
                        status_icon.color = ACCENT if online else WARN
                    if status_badge is not None:
                        status_badge.bgcolor = "#1D332D" if online else SURFACE_HIGH
                    if status_text is not None:
                        status_text.value = "آنلاین تأیید شد" if online else "حالت آفلاین"
                        status_text.color = SUCCESS if online else ON_SURFACE_VAR
                if timer_text is not None or clock_title is not None or clock_detail is not None:
                    ctx.page.update()
        except Exception:
            pass
        await asyncio.sleep(1)


if __name__ == "__main__":
    ft.run(main)
