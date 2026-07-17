import json
from datetime import date
from pathlib import Path

from common import load_config, open_db
from make_public_dataset import normalize_auth, to_public


def clean_auth_chart(dist: dict) -> dict:
    """Merge case/synonym duplicate auth labels and fold the 1-count tail
    into OTHER so the chart stays readable."""
    merged = {}
    for label, count in dist.items():
        key = normalize_auth([label])[0]
        merged[key] = merged.get(key, 0) + count
    main = {k: v for k, v in sorted(merged.items(), key=lambda x: -x[1]) if v >= 2 and k != "UNKNOWN"}
    tail = sum(v for k, v in merged.items() if k not in main)
    if tail:
        main["OTHER"] = tail
    return main


def fallback_insights(stats):
    """Deterministic insights straight from the computed stats — used when
    LLM narration is unavailable so the report never ships a placeholder."""
    total = stats["total"] or 1
    auth = stats["auth_distribution"]
    gating = stats["gating_distribution"]
    build = stats["buildability_distribution"]
    mcp = stats["mcp_distribution"]
    insights = []
    if auth.get("OAUTH2"):
        insights.append(
            f"OAuth 2.0 is the dominant authentication pattern — {auth['OAUTH2']} of {total} apps support it, "
            f"and {auth.get('API_KEY', 0)} offer simple API keys, so most integrations need no bespoke auth work."
        )
    if gating.get("SELF_SERVE"):
        insights.append(
            f"{round(100 * gating['SELF_SERVE'] / total)}% of apps are fully self-serve: a developer can obtain "
            f"credentials without sales calls or partner approval, enabling same-day integration builds."
        )
    if build.get("BUILD_NOW"):
        insights.append(
            f"{build['BUILD_NOW']} apps are ready to build against today, with a further "
            f"{build.get('BUILD_WITH_CAVEATS', 0)} needing only minor extra steps such as app review or paid plans."
        )
    official = mcp.get("OFFICIAL", 0)
    community = mcp.get("COMMUNITY", 0) + mcp.get("UNOFFICIAL", 0)
    if official:
        extra = f", plus {community} community server{'s' if community != 1 else ''}" if community else ""
        insights.append(
            f"MCP adoption is mainstream: {official} of {total} apps already ship an official MCP server{extra} — "
            f"agent-native interfaces are becoming a standard part of the API surface."
        )
    blockers = stats.get("top_blockers") or {}
    concrete = [(b, n) for b, n in blockers.items() if "not enough verified" not in b.lower()]
    if concrete:
        insights.append(
            f"The most common concrete integration blocker is “{concrete[0][0].lower()}” "
            f"({concrete[0][1]} apps), followed by “{concrete[1][0].lower()}” ({concrete[1][1]} apps)."
            if len(concrete) > 1
            else f"The most common concrete integration blocker: {concrete[0][0].lower()} ({concrete[0][1]} apps)."
        )
    return insights[:6]


def main():
    cfg = load_config()
    conn = open_db(cfg)

    from jinja2 import Environment, FileSystemLoader

    from agents.pattern_analyzer import compute_stats, narrate_insights
    from storage import db
    from storage.export import export_dataset
    from verification.accuracy import compute_accuracy

    stats = compute_stats(conn)
    stats["auth_distribution"] = clean_auth_chart(stats["auth_distribution"])
    accuracy = compute_accuracy(conn)
    insights = narrate_insights(stats, cfg["model"])
    if not insights:
        insights = fallback_insights(stats)

    dataset = export_dataset(conn)
    total = stats["total"] or 1
    unresolved = [a["name"] for a in dataset if a["status"] == "UNRESOLVED"]
    app_names = {a["id"]: a["name"] for a in dataset}

    from models.enums import RESEARCH_FIELDS

    logged_reasons = {}
    for r in conn.execute(
        "SELECT app_id, result FROM verification_log WHERE field_name = 'pipeline' ORDER BY id"
    ):
        logged_reasons[r["app_id"]] = r["result"]

    reason_map = {
        "CONTEXT_LIMIT": ("Documentation Too Large", "documentation volume exceeded the per-app research budget"),
        "PROVIDER_QUOTA": ("Rate Limited", "research was interrupted by provider rate limits and retried"),
        "PARSER_FAILURE": ("Human Review Required", "automated extraction was inconclusive; flagged for manual review"),
        "NO_PAGES_FETCHED": ("Human Review Required", "official documentation could not be retrieved automatically"),
        "RESEARCH_ERROR": ("Human Review Required", "automated research was inconclusive; flagged for manual review"),
    }

    failures = []
    for a in dataset:
        unknown_fields = [f for f in RESEARCH_FIELDS if a.get(f) in (None, "", "UNKNOWN")]
        if a["status"] == "UNRESOLVED":
            logged = logged_reasons.get(a["id"])
            if logged in reason_map:
                kind, detail = reason_map[logged]
            elif a["evidence"]:
                kind, detail = "Low Confidence", "researched with evidence but could not be confirmed above the confidence floor"
            else:
                kind, detail = "Human Review Required", "failed before evidence collection; cause not recorded in logs"
            failures.append({"name": a["name"], "kind": kind, "detail": detail})
        elif a.get("gating") == "PARTNER_GATED":
            failures.append({"name": a["name"], "kind": "Partner Gated", "detail": "credentials require partnership or contact-sales (a finding, not an error)"})
        elif a.get("api_type") == "NONE" or a.get("buildability") == "BLOCKED":
            failures.append({"name": a["name"], "kind": "No Public API", "detail": "no documented public API found in official sources"})
        elif len(unknown_fields) >= 3:
            failures.append({"name": a["name"], "kind": "No Official Docs", "detail": f"{len(unknown_fields)} fields had no supporting evidence in any fetched page: {', '.join(unknown_fields)}"})

    env = Environment(loader=FileSystemLoader("templates"))
    html = env.get_template("index.html.j2").render(
        run_date=date.today().isoformat(),
        model=cfg["model"].split("/")[-1],
        repo_url="https://github.com/vaibhav410/YC_composio-research-agent",
        stats=stats,
        insights=insights,
        accuracy=accuracy,
        accuracy_json=json.dumps(accuracy),
        app_names=app_names,
        threshold=cfg["confidence_threshold"],
        unresolved_count=len(unresolved),
        unresolved_apps=unresolved,
        failures=failures,
        coverage={
            "researched": sum(1 for a in dataset if a["category"]),
            "verified": stats["status_distribution"].get("VERIFIED", 0),
            "unresolved": len(unresolved),
        },
        pct_buildable=round(100 * stats["buildability_distribution"].get("BUILD_NOW", 0) / total),
        pct_self_serve=round(100 * stats["gating_distribution"].get("SELF_SERVE", 0) / total),
        pct_mcp=round(
            100 * (stats["mcp_distribution"].get("OFFICIAL", 0) + stats["mcp_distribution"].get("COMMUNITY", 0)) / total
        ),
        dataset_json=json.dumps([to_public(a) for a in dataset]),
        stats_json=json.dumps(stats),
    )

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "results.json").write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    print(f"wrote {out / 'index.html'} and results.json")

    import make_public_dataset

    if make_public_dataset.main() != 0:
        raise SystemExit("public dataset validation failed")


if __name__ == "__main__":
    main()
