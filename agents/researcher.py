import json
from pathlib import Path

from agents.planner import build_plan
from models import rules
from models.enums import RESEARCH_FIELDS
from models.schemas import Evidence
from storage import db
from tools import llm
from tools.fetcher import fetch
from tools.search import classify_source, ranked_urls

EVIDENCE_REQUIRED = {"auth_methods", "gating", "api_type", "mcp_available"}

EXTRACTION_PROMPT = Path("prompts/extraction.md").read_text(encoding="utf-8")


def gather_pages(plan, max_pages, char_limit):
    urls = plan.docs_guesses[:2] + ranked_urls(plan.queries, plan.website)
    pages, seen = [], set()
    for url in urls:
        if url in seen or len(pages) >= max_pages:
            continue
        seen.add(url)
        text, method = fetch(url, char_limit=char_limit)
        if text:
            pages.append({"url": url, "text": text, "method": method})
    return pages


RANK_KEYWORDS = (
    "auth", "oauth", "api key", "token", "bearer", "credential", "scope",
    "pricing", "free", "trial", "plan", "partner", "contact sales", "sign up",
    "rest", "graphql", "endpoint", "reference", "developer", "sandbox", "mcp",
)


def rank_chunks(pages, char_budget, chunk_size=700):
    scored = []
    for page in pages:
        text = page["text"]
        for pos in range(0, len(text), chunk_size):
            chunk = text[pos:pos + chunk_size]
            lowered = chunk.lower()
            score = sum(lowered.count(k) for k in RANK_KEYWORDS)
            if pos == 0:
                score += 3
            scored.append((score, page["url"], pos, chunk))
    scored.sort(key=lambda item: -item[0])

    used, selected = 0, []
    for score, url, pos, chunk in scored:
        if used + len(chunk) > char_budget:
            continue
        selected.append((url, pos, chunk))
        used += len(chunk)
    selected.sort(key=lambda item: (item[0], item[1]))
    return selected


def pages_to_context(pages, char_budget=None):
    if not char_budget:
        return "\n\n---\n\n".join(f"[SOURCE: {p['url']}]\n{p['text']}" for p in pages)
    grouped = {}
    for url, _, chunk in rank_chunks(pages, char_budget):
        grouped.setdefault(url, []).append(chunk)
    return "\n\n---\n\n".join(
        f"[SOURCE: {url}]\n" + "\n[...]\n".join(chunks) for url, chunks in grouped.items()
    )


def extract_record(app_name, website, pages, model, char_budget=12000):
    budget = char_budget
    for attempt in range(3):
        context = pages_to_context(pages, budget)
        user = (
            f"App: {app_name}\nOfficial website hint: {website}\n\n"
            f"Scraped pages:\n\n{context}"
        )
        try:
            return llm.complete_json(EXTRACTION_PROMPT, user, model=model)
        except Exception as e:
            if llm.request_too_large(e) and attempt < 2:
                budget //= 2
                continue
            raise


def normalize_value(value):
    if isinstance(value, list):
        return json.dumps(value)
    return str(value) if value is not None else "UNKNOWN"


def research_app(conn, app_row, cfg):
    plan = build_plan(app_row)
    pages = gather_pages(plan, cfg["max_pages_per_app"], cfg["page_char_limit"])
    if not pages:
        db.log_verification(conn, app_row["id"], "pipeline", "", "", "research", "NO_PAGES_FETCHED")
        db.save_record(conn, app_row["id"], {}, "UNRESOLVED", 1)
        return None

    raw = extract_record(
        app_row["name"], app_row["website_hint"], pages, cfg["model"],
        cfg.get("context_char_limit", 12000),
    )
    fields, answers = {}, {}
    for name in RESEARCH_FIELDS:
        ans = raw.get(name) or {}
        url, quote = ans.get("source_url") or "", ans.get("quote") or ""
        if name in EVIDENCE_REQUIRED and (not url or not quote):
            ans = {"value": "UNKNOWN", "source_url": "", "quote": "", "certainty": "guessed"}
            url, quote = "", ""
        value = normalize_value(ans.get("value"))
        fields[name] = value
        answers[name] = ans
        if url:
            method = next((p["method"] for p in pages if p["url"] == url), "requests")
            _, source_type = classify_source(url, app_row["website_hint"])
            db.add_evidence(conn, app_row["id"], Evidence(name, url, quote, method, 1, source_type))

    fields["mcp_available"] = rules.normalize_mcp(
        fields["mcp_available"],
        (answers["mcp_available"].get("source_url") or ""),
        app_row["website_hint"],
    )
    answers["mcp_available"]["value"] = fields["mcp_available"]

    auth = json.loads(fields["auth_methods"]) if fields["auth_methods"].startswith("[") else [fields["auth_methods"]]
    verdict, blocker = rules.decide_buildability(auth, fields["gating"], fields["api_type"])
    fields["buildability"] = verdict
    answers["buildability"]["value"] = verdict
    fields["main_blocker"] = blocker
    answers["main_blocker"]["value"] = blocker

    db.save_record(conn, app_row["id"], fields, "RESEARCHED", 1)
    return answers
