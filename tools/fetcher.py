import hashlib
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CACHE_DIR = Path("data/page_cache")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}


def _cache_path(url):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".txt")


def _clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s{2,}", " ", text)


def _fetch_requests(url, retries=2):
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return _clean_html(resp.text)
        except requests.RequestException as e:
            last_error = e
            time.sleep(1 + attempt)
    raise last_error


def _fetch_playwright(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        html = page.content()
        browser.close()
    return _clean_html(html)


def fetch(url, char_limit=9000, use_cache=True):
    cache = _cache_path(url)
    if use_cache and cache.exists():
        return cache.read_text(encoding="utf-8")[:char_limit], "cache"

    text, method = "", "requests"
    try:
        text = _fetch_requests(url)
    except Exception:
        text = ""
    if len(text) < 400:
        try:
            rendered = _fetch_playwright(url)
            if len(rendered) > len(text):
                text, method = rendered, "playwright"
        except Exception:
            pass
    if len(text) >= 300:
        cache.write_text(text, encoding="utf-8")
        time.sleep(1)
        return text[:char_limit], method
    return "", "failed"
