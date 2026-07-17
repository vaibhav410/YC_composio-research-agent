import json
from datetime import date
from pathlib import Path

from common import load_config, open_db


def main():
    cfg = load_config()
    conn = open_db(cfg)

    from jinja2 import Environment, FileSystemLoader

    from agents.pattern_analyzer import compute_stats, narrate_insights
    from storage import db
    from storage.export import export_dataset
    from verification.accuracy import compute_accuracy

    stats = compute_stats(conn)
    accuracy = compute_accuracy(conn)
    insights = narrate_insights(stats, cfg["model"])
    if not insights:
        insights = ["Insight generation unavailable — see charts below."]

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
        "CONTEXT_LIMIT": ("Context Limit", "context exceeded processing budget before extraction"),
        "PROVIDER_QUOTA": ("Provider Quota", "free-tier daily token quota exhausted mid-run; retried on quota recovery"),
        "PARSER_FAILURE": ("Human Review Required", "model output could not be parsed into the schema"),
        "NO_PAGES_FETCHED": ("Human Review Required", "automated fetching returned no usable pages; HTTP-level cause not logged"),
        "RESEARCH_ERROR": ("Human Review Required", "research pass raised an error before extraction completed"),
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
        dataset_json=json.dumps(dataset),
        stats_json=json.dumps(stats),
    )

    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "results.json").write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    print(f"wrote {out / 'index.html'} and results.json")


if __name__ == "__main__":
    main()
