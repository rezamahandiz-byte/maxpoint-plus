"""MAXPOINT design tokens — single source of truth for the visual language.

Supports both Dark and Light themes. The active theme is stored in the
SQLite `settings` table and applied dynamically by `main.py`.
"""
from __future__ import annotations


class DarkColors:
    bg             = "#0D1117"
    surface_1      = "#161B22"
    surface_2      = "#21262D"
    surface_3      = "#30363D"
    text_primary   = "#E6EDF3"
    text_secondary = "#8B949E"
    text_muted     = "#6E7681"
    accent         = "#4EA1A1"
    accent_muted   = "#2E6B6B"
    accent_text    = "#E6EDF3"
    warning        = "#D29922"
    success        = "#3FB950"
    info           = "#58A6FF"


class LightColors:
    bg             = "#F6F8FA"
    surface_1      = "#FFFFFF"
    surface_2      = "#F0F2F5"
    surface_3      = "#D8DEE4"
    text_primary   = "#1F2328"
    text_secondary = "#59636E"
    text_muted     = "#818B98"
    accent         = "#1A7F7F"
    accent_muted   = "#B8E0E0"
    accent_text    = "#FFFFFF"
    warning        = "#9A6700"
    success        = "#1A7F37"
    info           = "#0969DA"


class Typography:
    h1               = 28
    h2               = 20
    body             = 16
    small            = 14
    tiny             = 12
    weight_regular   = 400
    weight_semibold  = 600


class Spacing:
    xs  = 4
    sm  = 8
    md  = 12
    lg  = 16
    xl  = 24
    xxl = 32


class Radius:
    sm   = 8
    md   = 12
    lg   = 16
    full = 999


class Motion:
    fast       = 150
    standard   = 250
    emphasized = 400


class Layout:
    screen_edge       = 16
    card_padding      = 16
    between_cards     = 12
    between_sections  = 24
    min_touch         = 48
    button_height     = 52
    tab_bar_height    = 64
    fab_size          = 56


# ── Theme switching ────────────────────────────────────────────────────── #

THEME_KEY = "ui_theme"  # "dark" or "light"

def get_theme_mode() -> str:
    """Read the saved theme from SQLite. Returns 'dark' or 'light'."""
    try:
        from core import models
        val = models.get_setting(THEME_KEY, "dark") or "dark"
        return "light" if val == "light" else "dark"
    except Exception:
        return "dark"


def set_theme_mode(mode: str) -> None:
    """Persist the theme choice."""
    from core import models
    models.set_setting(THEME_KEY, "light" if mode == "light" else "dark")


def active_colors():
    """Return the color class for the current theme."""
    return LightColors if get_theme_mode() == "light" else DarkColors
