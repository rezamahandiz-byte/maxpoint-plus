"""Capture full-page screenshots of every tab including scrolled content."""
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8765/"
OUT = "/home/z/my-project/download"

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 360, "height": 720}, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)

    # 5 tabs in RTL: home(0)=rightmost, more(4)=leftmost
    tabs = ["home", "record", "analysis", "notifications", "more"]
    num = 5
    for idx, name in enumerate(tabs):
        x_frac = (num - 1 - idx + 0.5) / num
        page.mouse.click(360 * x_frac, 720 - 30)
        page.wait_for_timeout(2500)
        # Full-page screenshot (captures everything including scrolled content)
        page.screenshot(path=f"{OUT}/full_{name}.png", full_page=True)
        print(f"saved full_{name}.png")

    print("\n=== page errors ===")
    for e in errors[:20]:
        print(f"  {e}")

    browser.close()
