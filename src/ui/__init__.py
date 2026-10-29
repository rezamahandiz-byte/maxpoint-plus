"""MAXPOINT UI package — bottom-tab screens.

Color constants are plain strings resolved at import time from the saved
theme. When the user switches theme, call reload_colors() to update them,
then rebuild the page.
"""
from __future__ import annotations

from typing import Iterable, Optional

import flet as ft

from core import analytics as _analytics
from ui.theme import DarkColors, LightColors, Typography, Spacing, Radius, Motion, Layout


def _resolve_colors():
    """Read the current theme and set all module-level color strings."""
    global ACCENT, ACCENT_SOFT, BG_DARK, SURFACE, SURFACE_HIGH
    global ON_SURFACE, ON_SURFACE_VAR, ON_SURFACE_MUT, OUTLINE
    global SUCCESS, WARN, INFO

    from ui.theme import active_colors
    c = active_colors()
    ACCENT = c.accent
    ACCENT_SOFT = c.accent_muted
    BG_DARK = c.bg
    SURFACE = c.surface_1
    SURFACE_HIGH = c.surface_2
    ON_SURFACE = c.text_primary
    ON_SURFACE_VAR = c.text_secondary
    ON_SURFACE_MUT = c.text_muted
    OUTLINE = c.surface_3
    SUCCESS = c.success
    WARN = c.warning
    INFO = c.info


# Resolve immediately at import time
_resolve_colors()


def reload_colors():
    """Re-read theme and update all color strings. Call before page rebuild."""
    _resolve_colors()


# ---- Helpers --------------------------------------------------------------- #


def to_fa(value) -> str:
    """Render digits in Persian for display."""
    return _analytics.to_fa(value)


def card(content: ft.Control | list[ft.Control],
         padding: int = Layout.card_padding,
         margin: int = 0) -> ft.Card:
    """Standard surface card. Accepts one control or a list (auto-wrapped in Column)."""
    if isinstance(content, list):
        inner: ft.Control = ft.Column(content, spacing=Spacing.sm, expand=True)
    else:
        inner = content
    return ft.Card(
        content=ft.Container(padding=padding, content=inner),
        margin=margin,
        expand=True,
    )


def section_title(text: str) -> ft.Text:
    return ft.Text(value=text, size=Typography.body, weight=ft.FontWeight.W_600,
                   color=ON_SURFACE, rtl=True)


def label(text: str, size: int = Typography.tiny, color: str = ON_SURFACE_VAR) -> ft.Text:
    return ft.Text(value=text, size=size, color=color, rtl=True)


def stat_tile(big: str, caption: str, color: str = ON_SURFACE) -> ft.Column:
    """A compact 'big number + caption' tile used on Home and Analysis."""
    return ft.Column(
        [
            ft.Text(value=big, size=22, weight=ft.FontWeight.W_600, color=color,
                    rtl=True, text_align=ft.TextAlign.CENTER),
            ft.Text(value=caption, size=Typography.tiny, color=ON_SURFACE_VAR, rtl=True,
                    text_align=ft.TextAlign.CENTER),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def divider() -> ft.Divider:
    return ft.Divider(height=1, color=OUTLINE)


def filled_button(text: str, on_click=None, icon: Optional[str] = None,
                  primary: bool = True) -> ft.Control:
    """Standard filled button. Min 48dp tall."""
    btn_cls = ft.FilledButton if primary else ft.FilledTonalButton
    return btn_cls(
        content=text,
        icon=icon,
        on_click=on_click,
        height=Layout.button_height,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Radius.md)),
    )


def outlined_button(text: str, on_click=None, icon: Optional[str] = None) -> ft.Control:
    return ft.OutlinedButton(
        content=text,
        icon=icon,
        on_click=on_click,
        height=Layout.button_height,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Radius.md)),
    )


def text_button(text: str, on_click=None, icon: Optional[str] = None) -> ft.Control:
    return ft.TextButton(
        content=text,
        icon=icon,
        on_click=on_click,
        height=48,
    )


def field_label(text: str) -> ft.Text:
    return ft.Text(value=text, size=12, color=ON_SURFACE_VAR, rtl=True)


def safe_list(controls: Iterable[ft.Control]) -> list[ft.Control]:
    """Filter out None controls (handy when conditionally building UI)."""
    return [c for c in controls if c is not None]


# ---- Layout primitive shortcuts (Flet 1.0 dropped the .all/.symmetric helpers) #


def pad_sym(horizontal: int = 0, vertical: int = 0) -> ft.Padding:
    return ft.Padding(left=horizontal, top=vertical,
                      right=horizontal, bottom=vertical)


def pad_only(left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> ft.Padding:
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def margin_only(left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> ft.Margin:
    return ft.Margin(left=left, top=top, right=right, bottom=bottom)


def border_all(width: float = 1, color: str = OUTLINE) -> ft.Border:
    side = ft.BorderSide(color=color, width=width)
    return ft.Border(top=side, bottom=side, left=side, right=side)


CENTER = ft.Alignment(0, 0)
CENTER_LEFT = ft.Alignment(-1, 0)
CENTER_RIGHT = ft.Alignment(1, 0)
TOP_CENTER = ft.Alignment(0, -1)
BOTTOM_CENTER = ft.Alignment(0, 1)


def responsive_dialog_width(page, max_width: int = 380, min_width: int = 260, side_margin: int = 40) -> int:
    """Keep modal content inside narrow phones while retaining desktop width."""
    try:
        available = int(float(page.width)) - side_margin
    except (TypeError, ValueError, AttributeError):
        available = max_width
    return max(min_width, min(max_width, available))


def responsive_dialog_height(page, max_height: int = 560, min_height: int = 300, vertical_margin: int = 180) -> int:
    """Bound modal height to the current viewport so its contents can scroll."""
    try:
        available = int(float(page.height)) - vertical_margin
    except (TypeError, ValueError, AttributeError):
        available = max_height
    return max(min_height, min(max_height, available))


# ---- Shared chart helpers ------------------------------------------------- #


def bar_chart_7day(last7: list[tuple[str, int]], bar_color: str = ACCENT,
                   height: int = 100) -> ft.Control:
    """A reusable 7-day bar chart.

    Args:
        last7: list of (date_str, value) pairs, oldest → newest.
        bar_color: color for bars with value > 0.
        height: plot height in px.

    Returns:
        A Column with bars + weekday labels.
    """
    from datetime import date as _date
    fa_wd = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
    max_val = max((v for _, v in last7), default=1) or 1

    cols: list[ft.Control] = []
    for date_str, val in last7:
        d = _date.fromisoformat(date_str)
        wd = fa_wd[(d.weekday() + 2) % 7]
        is_today = (date_str == _date.today().isoformat())
        h = max(2, int(height * val / max_val)) if val > 0 else 2
        color = bar_color if val > 0 else OUTLINE
        label_color = bar_color if is_today else ON_SURFACE_MUT
        cols.append(ft.Column([
            ft.Text(to_fa(val), size=9, color=ON_SURFACE_MUT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(width=20, height=h, bgcolor=color, border_radius=4),
            ft.Container(height=4),
            ft.Text(wd, size=11, color=label_color,
                    text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END, expand=True))

    return ft.Row(cols, spacing=8, alignment=ft.MainAxisAlignment.SPACE_AROUND)


def stat_row(items: list[tuple[str, str, str]]) -> ft.Row:
    """A row of stat tiles. Each item = (value, caption, color)."""
    return ft.Row([
        ft.Column([
            ft.Text(value, size=22, weight=ft.FontWeight.W_600, color=color,
                    rtl=True, text_align=ft.TextAlign.CENTER),
            ft.Text(caption, size=11, color=ON_SURFACE_VAR, rtl=True,
                    text_align=ft.TextAlign.CENTER),
        ], alignment=ft.MainAxisAlignment.CENTER,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        for value, caption, color in items
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
