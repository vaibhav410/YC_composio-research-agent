import re
from pathlib import Path

from tools.fetcher import fetch

SCREENSHOT_DIR = Path("output/screenshots")


def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def quote_on_page(url, quote):
    text, method = fetch(url, char_limit=60000, use_cache=False)
    if not text:
        return False, method
    probe = normalize(quote)[:120]
    if not probe.strip():
        return False, method
    found = probe in normalize(text)
    if not found:
        words = [w for w in probe.split() if len(w) > 3]
        page = normalize(text)
        hits = sum(1 for w in words if w in page)
        found = words and hits / len(words) >= 0.7
    return found, method


def screenshot(url, name):
    try:
        from playwright.sync_api import sync_playwright

        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f"{name}.png"
        if path.exists():
            return str(path)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(path))
            browser.close()
        return str(path)
    except Exception:
        return ""
