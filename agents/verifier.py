import time
from pathlib import Path

import json

from agents.planner import verify_queries
from agents.researcher import pages_to_context
from models import rules
from models.schemas import Evidence
from storage import db
from tools import llm
from tools.browser import quote_on_page
from tools.fetcher import fetch
from tools.search import classify_source, ranked_urls

VERIFY_PROMPT = Path("prompts/verification.md").read_text(encoding="utf-8")


def check_citation(conn, app_id, field_name, value):
    rows = db.evidence_for(conn, app_id, field_name)
    for row in rows:
        if not row["source_url"] or not row["quote"]:
            continue
        found, method = quote_on_page(row["source_url"], row["quote"])
        db.log_verification(
            conn, app_id, field_name, value, value,
            f"citation_check:{method}", "PASS" if found else "FAIL",
        )
        return found
    return False


def second_pass(conn, app_row, field_name, current_value, cfg):
    queries = verify_queries(app_row["name"], field_name)
    urls = ranked_urls(queries, app_row["website_hint"], per_query=4, cap=3)
    pages = []
    for url in urls:
        text, method = fetch(url, char_limit=cfg["page_char_limit"])
        if text:
            pages.append({"url": url, "text": text, "method": method})
    if not pages:
        return None

    budget = cfg.get("context_char_limit", 12000)
    result = None
    for attempt in range(3):
        user = (
            f"App: {app_row['name']}\n"
            f"Claim: the field '{field_name}' has value: {current_value}\n\n"
            f"Fresh pages:\n\n{pages_to_context(pages, budget)}"
        )
        try:
            result = llm.complete_json(VERIFY_PROMPT, user, model=cfg["model"])
            break
        except ValueError:
            return None
        except Exception as e:
            if llm.request_too_large(e) and attempt < 2:
                budget //= 2
                continue
            raise
    if result is None:
        return None

    verdict = result.get("verdict", "NO_EVIDENCE")
    url, quote = result.get("source_url") or "", result.get("quote") or ""
    source_type = classify_source(url, app_row["website_hint"])[1] if url else "general"
    if verdict == "SUPPORTED":
        if url:
            db.add_evidence(conn, app_row["id"], Evidence(field_name, url, quote, "verify", 2, source_type))
        db.log_verification(conn, app_row["id"], field_name, current_value, current_value, "second_pass", "SUPPORTED")
        return {"value": current_value, "source_url": url, "quote": quote, "certainty": "explicit"}
    if verdict == "CONTRADICTED" and result.get("corrected_value"):
        new_value = result["corrected_value"]
        if url:
            db.add_evidence(conn, app_row["id"], Evidence(field_name, url, quote, "verify", 2, source_type))
        db.log_verification(conn, app_row["id"], field_name, current_value, str(new_value), "second_pass", "CORRECTED")
        return {"value": new_value, "source_url": url, "quote": quote, "certainty": "explicit"}
    db.log_verification(conn, app_row["id"], field_name, current_value, current_value, "second_pass", "NO_EVIDENCE")
    return None


def answers_from_db(conn, app_row):
    from models.enums import RESEARCH_FIELDS

    answers = {}
    for field_name in RESEARCH_FIELDS:
        value = app_row[field_name]
        rows = db.evidence_for(conn, app_row["id"], field_name)
        url = rows[0]["source_url"] if rows else ""
        quote = rows[0]["quote"] if rows else ""
        certainty = "explicit" if quote else "guessed"
        answers[field_name] = {
            "value": value if value is not None else "UNKNOWN",
            "source_url": url,
            "quote": quote,
            "certainty": certainty,
        }
    return answers


def verify_app(conn, app_row, answers, cfg):
    from agents.researcher import normalize_value
    from verification.confidence import score_field

    threshold = cfg["confidence_threshold"]
    floor = cfg["unresolved_floor"]
    derived_fields = {"buildability", "main_blocker"}
    updates, final_scores = {}, {}

    for field_name, answer in answers.items():
        if field_name in derived_fields:
            continue
        evidence = db.evidence_for(conn, app_row["id"], field_name)
        score, reasons = score_field(answer, evidence, app_row["website_hint"])

        if score >= threshold and answer.get("quote"):
            if not check_citation(conn, app_row["id"], field_name, answer.get("value")):
                score = min(score, floor)
                reasons += "; quote not found on the cited page, treated as unreliable"

        if score < threshold:
            fixed = second_pass(conn, app_row, field_name, answer.get("value"), cfg)
            if fixed:
                answer = fixed
                updates[field_name] = normalize_value(fixed["value"])
                evidence = db.evidence_for(conn, app_row["id"], field_name)
                score, reasons = score_field(answer, evidence, app_row["website_hint"])
                reasons += "; confirmed by independent second research pass"
            time.sleep(1)

        db.set_confidence(conn, app_row["id"], field_name, score, reasons, 2)
        final_scores[field_name] = score

    final = {f: updates.get(f, app_row[f] or "UNKNOWN") for f in answers}
    auth_raw = final["auth_methods"]
    auth = json.loads(auth_raw) if str(auth_raw).startswith("[") else [auth_raw]
    verdict, blocker = rules.decide_buildability(auth, final["gating"], final["api_type"])
    if verdict != app_row["buildability"]:
        db.log_verification(
            conn, app_row["id"], "buildability", app_row["buildability"], verdict, "rule_engine", "RECOMPUTED"
        )
    updates["buildability"] = verdict
    updates["main_blocker"] = blocker

    input_scores = [final_scores[f] for f in ("auth_methods", "gating", "api_type") if f in final_scores]
    derived_score = round(min(input_scores), 3) if input_scores else 0.0
    derived_reason = "derived by rule engine from auth, gating and api type; inherits their weakest confidence"
    for field_name in derived_fields:
        db.set_confidence(conn, app_row["id"], field_name, derived_score, derived_reason, 2)
        final_scores[field_name] = derived_score

    status = "VERIFIED" if all(s >= floor for s in final_scores.values()) else "UNRESOLVED"
    db.save_record(conn, app_row["id"], updates, status, 2)
    return final_scores
