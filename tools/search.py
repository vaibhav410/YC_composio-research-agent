import time
from urllib.parse import urlparse

from ddgs import DDGS


def root_domain(url_or_host):
    host = urlparse(url_or_host if "//" in url_or_host else f"https://{url_or_host}").netloc
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def search(query, max_results=6, retries=3):
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=max_results))
            return [{"title": h.get("title", ""), "url": h.get("href", "")} for h in hits]
        except Exception:
            time.sleep(2 * (attempt + 1))
    return []


DEV_MARKERS = ("developer", "docs", "api", "reference")
HELP_MARKERS = ("help", "support", "knowledge")


def classify_source(url, website_hint):
    if not url:
        return 5, "general"
    lowered = url.lower()
    host = urlparse(lowered).netloc
    if root_domain(url) == root_domain(website_hint):
        if any(m in host for m in DEV_MARKERS) or any(f"/{m}" in lowered for m in DEV_MARKERS):
            return 1, "developer_docs"
        if any(m in host for m in HELP_MARKERS) or any(f"/{m}" in lowered for m in HELP_MARKERS):
            return 3, "help_center"
        return 2, "product_docs"
    if host.endswith("github.com"):
        return 4, "github"
    return 5, "general"


def ranked_urls(queries, website_hint, per_query=5, cap=8):
    seen, found = set(), []
    for q in queries:
        for hit in search(q, max_results=per_query):
            url = hit["url"]
            if not url or url in seen:
                continue
            seen.add(url)
            tier, _ = classify_source(url, website_hint)
            found.append((tier, len(found), url))
        time.sleep(1.5)
    found.sort()
    return [url for _, _, url in found[:cap]]
