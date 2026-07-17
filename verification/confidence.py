from tools.search import classify_source

CERTAINTY_SCORE = {"explicit": 1.0, "inferred": 0.5, "guessed": 0.0}

SOURCE_SCORE = {
    "developer_docs": 1.0,
    "product_docs": 0.9,
    "help_center": 0.8,
    "github": 0.6,
    "general": 0.3,
}

SOURCE_LABEL = {
    "developer_docs": "official developer docs",
    "product_docs": "official product site",
    "help_center": "official help center",
    "github": "GitHub",
    "general": "third-party page",
}


def agreement(evidence_rows):
    urls = {r["source_url"] for r in evidence_rows if r["source_url"]}
    if len(urls) >= 2:
        return 1.0, f"{len(urls)} independent sources agree"
    if len(urls) == 1:
        return 0.6, "single source only"
    return 0.0, "no sources collected"


def score_field(answer, evidence_rows, website_hint):
    url = answer.get("source_url") or ""
    quote = answer.get("quote") or ""
    certainty = answer.get("certainty", "guessed")
    value = answer.get("value")

    source_type = classify_source(url, website_hint)[1] if url else "general"
    source_score = SOURCE_SCORE[source_type] if url else 0.0
    agreement_score, agreement_reason = agreement(evidence_rows)
    certainty_score = CERTAINTY_SCORE.get(certainty, 0.0)
    score = 0.4 * source_score + 0.35 * agreement_score + 0.25 * certainty_score

    reasons = []
    reasons.append(f"cited from {SOURCE_LABEL[source_type]}" if url else "no source URL")
    reasons.append(agreement_reason)
    if certainty == "explicit":
        reasons.append("explicitly stated in the page text")
    elif certainty == "inferred":
        reasons.append("inferred, not stated verbatim")
    else:
        reasons.append("model could not ground the answer")

    if not url or not quote:
        score = min(score, 0.4)
        reasons.append("capped: missing supporting quote")
    if value in (None, "", "UNKNOWN"):
        score = min(score, 0.2)
        reasons.append("value is UNKNOWN")

    return round(score, 3), "; ".join(reasons)
