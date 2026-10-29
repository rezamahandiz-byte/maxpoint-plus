"""Screenshot the redesigned assistant modal."""
import os
import sys
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = "/tmp/mp_assistant.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    # Seed data
    sys.path.insert(0, str(PROJECT / "src"))
    os.environ["MAXPOINT_DB_PATH"] = DB_PATH
    from core import db, models
    db.init_db()
    acts = models.list_activities(active_only=True)
    from datetime import date, timedelta
    today = date.today()
    for i in range(7):
        d = (today - timedelta(days=i)).isoformat()
        models.create_session(d, acts[i % len(acts)].id,
                              20 + i * 15, i % 4, f"day {i}")
    models.upsert_goal(acts[0].id, "daily", 120, 0)
    models.create_exam((today - timedelta(days=40)).isoformat(), 1, 5100)
    models.create_exam((today - timedelta(days=20)).isoformat(), 2, 5400)
    print("seeded")

    port = free_port()
    env = os.environ.copy()
    proc = subprocess.Popen(
        ["flet", "run", "-w", "-p", str(port), "--host", "127.0.0.1",
         str(PROJECT / "src" / "main.py")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=str(PROJECT),
    )
    try:
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

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 360, "height": 720},
                device_scale_factor=2,
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
            page.on("console", lambda m: errors.append(
                f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2500)

            # Switch to Analysis (3rd tab from right in RTL = idx 2)
            # x fraction from left = (4 - 1 - 2 + 0.5) / 4 = 0.375
            page.mouse.click(360 * 0.375, 720 - 30)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(PROJECT / "download" / "_redesigned_analysis.png"))

            # Find and click the "دریافت تحلیل هوشمند" button.
            # It's a filled teal button at the bottom of the Analysis tab.
            # We need to scroll down first.
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(800)

            # Click in the middle of the screen where the button should be.
            page.mouse.click(180, 600)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(PROJECT / "download" / "_assistant_step1_preview.png"))

            # Click "ادامه" button — should be at bottom of dialog, on the right.
            page.mouse.click(280, 580)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(PROJECT / "download" / "_assistant_step3_result.png"))

            print("\n--- Browser errors ---")
            for e in errors[:30]:
                print(f"  {e}")

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
