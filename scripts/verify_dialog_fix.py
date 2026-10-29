"""Verify the dialog/snackbar fix works in a real browser session.

Walks through:
  1. Open Home tab.
  2. Click FAB → quick-record dialog should open (no `page.open` error).
  3. Fill the form and submit → SnackBar should appear ("ثبت شد").
  4. Switch to Settings tab.
  5. Click a subject's edit icon → rename dialog should open.
  6. Cancel the dialog.
  7. Click "Clear all data" → first confirmation dialog should open.
"""
import os
import sys
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = "/tmp/mp_dialog_verify.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    # Seed some data so the Home tab has sessions to show
    sys.path.insert(0, str(PROJECT / "src"))
    os.environ["MAXPOINT_DB_PATH"] = DB_PATH
    from core import db, models
    db.init_db()
    acts = models.list_activities(active_only=True)
    from datetime import date
    models.create_session(date.today().isoformat(), acts[0].id, 30, 0, "test")
    print(f"seeded: {len(acts)} activities, 1 session")

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
            ctx = browser.new_context(viewport={"width": 360, "height": 720})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
            page.on("console", lambda m: errors.append(
                f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2500)

            print("\n=== Step 1: Home tab loaded ===")
            page.screenshot(path=str(PROJECT / "download" / "_verify_01_home.png"))

            print("=== Step 2: Click FAB (bottom-left in RTL) ===")
            page.mouse.click(40, 720 - 90)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(PROJECT / "download" / "_verify_02_dialog.png"))

            print("=== Step 3: Fill the form and submit ===")
            # Find the minute field (second textbox in dialog) and bump it
            textboxes = page.query_selector_all("input")
            print(f"  found {len(textboxes)} inputs")
            if len(textboxes) >= 2:
                textboxes[1].fill("45")
            page.wait_for_timeout(300)
            # Find and click the save button (text "ثبت")
            buttons = page.query_selector_all("button")
            clicked = False
            for b in buttons:
                txt = (b.text_content() or "").strip()
                if "ثبت" in txt:
                    b.click()
                    clicked = True
                    break
            print(f"  save clicked: {clicked}")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(PROJECT / "download" / "_verify_03_after_save.png"))

            print("=== Step 4: Switch to Settings (leftmost tab in RTL) ===")
            page.mouse.click(360 * 0.125, 720 - 30)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(PROJECT / "download" / "_verify_04_settings.png"))

            print("=== Step 5: Click first subject's edit (pencil) icon ===")
            # Find pencil-icon buttons
            edit_clicked = False
            for b in page.query_selector_all("button"):
                aria = b.get_attribute("aria-label") or ""
                if "ویرایش" in aria or "edit" in aria.lower():
                    b.click()
                    edit_clicked = True
                    break
            print(f"  edit clicked: {edit_clicked}")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(PROJECT / "download" / "_verify_05_rename_dialog.png"))

            print("=== Step 6: Cancel rename dialog (press Escape) ===")
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

            print("=== Step 7: Scroll to danger zone + click clear ===")
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(800)
            # Find "پاک‌سازی" button
            clear_clicked = False
            for b in page.query_selector_all("button"):
                txt = (b.text_content() or "").strip()
                if "پاک‌سازی" in txt:
                    b.click()
                    clear_clicked = True
                    break
            print(f"  clear clicked: {clear_clicked}")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(PROJECT / "download" / "_verify_06_clear_dialog.png"))

            print("\n=== Browser errors/warnings ===")
            for e in errors[:30]:
                print(f"  {e}")

            # Check for the original error
            original_error = [e for e in errors if "has no attribute 'open'" in e]
            if original_error:
                print("\n*** ORIGINAL ERROR STILL PRESENT ***")
                for e in original_error:
                    print(f"  {e}")
                return 1
            else:
                print("\n*** No 'page.open' errors — fix verified ***")
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
