"""Take screenshots of the MAXPOINT app for visual verification.

Starts a Flet web app on a random port, opens it with Playwright, walks
through each tab, and saves a PNG per tab to /home/z/my-project/download/.

Usage: python3 scripts/screenshot_tabs.py
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = "/tmp/mp_screenshots.db"
OUT_DIR = PROJECT / "download"
OUT_DIR.mkdir(exist_ok=True)


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def seed_data():
    """Reset DB and seed varied data so charts render meaningfully."""
    import sys as _sys
    _sys.path.insert(0, str(PROJECT / "src"))
    os.environ["MAXPOINT_DB_PATH"] = DB_PATH
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    from core import db, models
    from services import clock_sync
    db.init_db()
    acts = models.list_activities(active_only=True)
    from datetime import date, timedelta
    # Use clock_sync.now_local().date() — the same date the app uses
    today = clock_sync.now_local().date()
    # Seed sessions for today (multiple)
    for i in range(4):
        models.create_session(today.isoformat(), acts[i].id,
                              30 + i * 15, i % 3, f"session {i+1}")
    # Spread sessions across the last 7 days
    for i in range(1, 7):
        d = (today - timedelta(days=i)).isoformat()
        models.create_session(d, acts[i % len(acts)].id,
                              20 + i * 15, i % 4, f"day {i}")
    # Goals
    models.upsert_goal(acts[0].id, "daily", 120, 0)
    models.upsert_goal(acts[1].id, "daily", 60, 0)
    models.upsert_goal(acts[2].id, "daily", 90, 1)
    # Exams for the line chart
    models.create_exam((today - timedelta(days=40)).isoformat(), 1, 5100)
    models.create_exam((today - timedelta(days=30)).isoformat(), 2, 5300)
    models.create_exam((today - timedelta(days=20)).isoformat(), 3, 5250)
    models.create_exam((today - timedelta(days=10)).isoformat(), 4, 5600)


def main():
    seed_data()
    port = free_port()
    env = os.environ.copy()
    env["MAXPOINT_DB_PATH"] = DB_PATH

    proc = subprocess.Popen(
        ["flet", "run", "-w", "-p", str(port), "--host", "127.0.0.1",
         str(PROJECT / "src" / "main.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(PROJECT),
    )
    try:
        # Wait for the server to come up
        url = f"http://127.0.0.1:{port}/"
        for _ in range(30):
            time.sleep(1)
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                continue
        else:
            print("server didn't come up", file=sys.stderr)
            proc.terminate()
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 360, "height": 720},
                device_scale_factor=2,
            )
            page = ctx.new_page()
            # Capture console + page errors
            errors = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.on("console", lambda m: errors.append(
                f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2500)  # let Flet warm up

            # Click through each tab once to trigger any lazy errors
            num_tabs = 6
            for idx in range(num_tabs):
                x_frac = (num_tabs - 1 - idx + 0.5) / num_tabs
                page.mouse.click(360 * x_frac, 720 - 30)
                page.wait_for_timeout(1200)

            tabs = [
                ("home",     "tab_home.png"),
                ("study",    "tab_study.png"),
                ("charts",   "tab_charts.png"),
                ("exam",     "tab_exam.png"),
                ("test",     "tab_test.png"),
                ("settings", "tab_settings.png"),
            ]

            # In RTL, NavigationBar destinations are laid out right-to-left,
            # so destination[0] (Home) is at the RIGHT, destination[3]
            # (Settings) is at the LEFT. We click by x-coordinate using
            # reversed ordering.
            for idx, (name, fname) in enumerate(tabs):
                # In RTL: visual position from left = (num_tabs - 1 - idx)
                # x fraction from LEFT = (num_tabs - 1 - idx + 0.5) / num_tabs
                num_tabs = len(tabs)
                x_frac_from_left = (num_tabs - 1 - idx + 0.5) / num_tabs
                w = page.viewport_size["width"]
                h = page.viewport_size["height"]
                page.mouse.click(w * x_frac_from_left, h - 30)
                page.wait_for_timeout(1800)
                out = OUT_DIR / fname
                page.screenshot(path=str(out), full_page=False)
                print(f"saved {out} (clicked x={w*x_frac_from_left:.0f})")

            # Also screenshot a dialog (quick record) — go back to Home (rightmost tab in RTL) first
            try:
                # In RTL with 4 tabs: Home is rightmost, x_frac = (3 + 0.5) / 4 = 0.875
                page.mouse.click(w * 0.875, h - 30)
                page.wait_for_timeout(2000)
                # FAB in RTL is at bottom-LEFT (FloatingActionButtonLocation.END_FLOAT,
                # and "end" in RTL is the left). The FAB is 56dp above the nav bar.
                # Try multiple positions to hit the FAB.
                fab_positions = [(40, h - 100), (40, h - 120), (56, h - 110), (50, h - 130)]
                for px, py in fab_positions:
                    page.mouse.click(px, py)
                    page.wait_for_timeout(1800)
                    page.screenshot(path=str(OUT_DIR / "dialog_quick_record.png"))
                    # Don't try to verify here — just take the screenshot and move on.
                    break
                # Close dialog if open
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            except Exception as e:
                print(f"dialog screenshot skipped: {e}", file=sys.stderr)

            if errors:
                print("\n--- BROWSER ERRORS / WARNINGS ---", file=sys.stderr)
                for e in errors[:60]:
                    print(e, file=sys.stderr)

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    return 0


if __name__ == "__main__":
    sys.exit(main())
