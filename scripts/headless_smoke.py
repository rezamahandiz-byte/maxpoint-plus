"""Headless smoke test — exercise every tab's build() without a real Flet page.

This catches construction-time errors (wrong kwargs, missing helpers, etc.)
that imports alone won't surface.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ["MAXPOINT_DB_PATH"] = "/tmp/mp_headless_test.db"

import flet as ft

from core import db, models
from services import secure as secure_service


class FakePage:
    """Just enough of ft.Page for our code to construct UIs."""
    def __init__(self):
        self.controls = []
        self.overlay = []
        self.services = []
        self.navigation_bar = None
        self.floating_action_button = None
        self.title = ""
        self.theme = None
        self.dark_theme = None
        self.theme_mode = None
        self.rtl = False
        self.bgcolor = None
        self.padding = 0
        self.horizontal_alignment = None
        self.vertical_alignment = None
        self.scroll = None
        self.fonts = {}
        self.session = type("S", (), {})()
        self.run_task = lambda *a, **kw: None
        self.run_thread = lambda *a, **kw: None
        self.update = lambda: None

    def add(self, *controls):
        self.controls.extend(controls)

    def open(self, dlg):
        pass

    def close(self, dlg):
        pass


def make_ctx():
    page = FakePage()
    sec = secure_service.SecureKeyStore(page)  # safe; degrades if no keystore
    import main as _main
    ctx = _main.AppContext(page=page, secure=sec)
    return ctx


def main():
    db.init_db()
    acts = models.list_activities(active_only=True)
    from datetime import date, timedelta
    today = date.today()
    for i in range(7):
        d = (today - timedelta(days=i)).isoformat()
        models.create_session(d, acts[i % len(acts)].id,
                              20 + i * 10, i % 3, f"day {i}")
    models.upsert_goal(acts[0].id, "daily", 120, 0)
    models.upsert_goal(acts[1].id, "daily", 60, 0)
    models.create_exam((today - timedelta(days=30)).isoformat(), 1, 5000)
    models.create_exam((today - timedelta(days=20)).isoformat(), 2, 5200)
    models.create_exam((today - timedelta(days=10)).isoformat(), 3, 5400)

    ctx = make_ctx()

    from ui import home as ui_home, record as ui_record, analysis as ui_analysis, settings as ui_settings, notifications as ui_notifications

    tabs = [("home", ui_home), ("record", ui_record),
            ("analysis", ui_analysis), ("notifications", ui_notifications),
            ("settings", ui_settings)]

    failures = []
    for name, mod in tabs:
        try:
            view = mod.build(ctx)
            print(f"OK: {name}.build() -> {type(view).__name__}")
        except Exception as e:
            import traceback
            failures.append((name, e, traceback.format_exc()))
            print(f"FAIL: {name}.build(): {type(e).__name__}: {e}")

    from ui import record as ui_record
    try:
        ui_record.open_quick_record(ctx)
        print("OK: record.open_quick_record()")
    except Exception as e:
        print(f"FAIL: record.open_quick_record(): {type(e).__name__}: {e}")

    from ui import assistant
    try:
        assistant.open_assistant(ctx)
        print("OK: assistant.open_assistant()")
    except Exception as e:
        print(f"FAIL: assistant.open_assistant(): {type(e).__name__}: {e}")

    if failures:
        print("\n=== TRACEBACKS ===")
        for name, e, tb in failures:
            print(f"\n--- {name} ---")
            print(tb)
        sys.exit(1)
    else:
        print("\nALL TABS OK")


if __name__ == "__main__":
    main()
