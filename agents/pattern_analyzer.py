import json

import pandas as pd

from storage import db


def load_frame(conn):
    rows = [dict(r) for r in db.all_apps(conn)]
    frame = pd.DataFrame(rows)

    def parse_auth(value):
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            return [value]

    frame["auth_list"] = frame["auth_methods"].apply(parse_auth)
    return frame


def compute_stats(conn):
    frame = load_frame(conn)
    total = len(frame)

    auth_counts = {}
    for methods in frame["auth_list"]:
        for m in methods:
            auth_counts[m] = auth_counts.get(m, 0) + 1

    def dist(col):
        return frame[col].fillna("UNKNOWN").value_counts().to_dict()

    def crosstab(col):
        ct = pd.crosstab(frame["category_hint"], frame[col].fillna("UNKNOWN"))
        return {cat: row.to_dict() for cat, row in ct.iterrows()}

    blockers = (
        frame[~frame["main_blocker"].isin([None, "", "NONE", "UNKNOWN"])]["main_blocker"]
        .str.lower().str.strip().value_counts().head(10).to_dict()
    )

    easy = frame[
        (frame["buildability"] == "BUILD_NOW")
        & (frame["gating"] == "SELF_SERVE")
        & (frame["api_type"].isin(["REST", "GRAPHQL", "BOTH"]))
    ]["name"].tolist()

    hard = frame[
        frame["buildability"].isin(["OUTREACH_REQUIRED", "BLOCKED"])
        | (frame["gating"] == "PARTNER_GATED")
    ][["name", "main_blocker"]].to_dict("records")

    conf = pd.read_sql("SELECT app_id, field_name, score, pass_number FROM confidence", conn)
    evidence = pd.read_sql("SELECT source_type FROM evidence", conn)
    official_types = {"developer_docs", "product_docs", "help_center"}
    official_pct = (
        round(100 * evidence["source_type"].isin(official_types).mean()) if len(evidence) else 0
    )
    corrections = pd.read_sql(
        "SELECT app_id, field_name, old_value, new_value, method FROM verification_log "
        "WHERE result IN ('CORRECTED', 'RECOMPUTED') AND old_value != new_value",
        conn,
    ).to_dict("records")
    durations = db.all_stats(conn).get("stage_durations", {})

    stats = {
        "total": total,
        "auth_distribution": auth_counts,
        "gating_distribution": dist("gating"),
        "api_type_distribution": dist("api_type"),
        "mcp_distribution": dist("mcp_available"),
        "buildability_distribution": dist("buildability"),
        "status_distribution": dist("status"),
        "gating_by_category": crosstab("gating"),
        "api_type_by_category": crosstab("api_type"),
        "mcp_by_category": crosstab("mcp_available"),
        "auth_by_category": auth_by_category(frame),
        "top_blockers": blockers,
        "easy_wins": easy,
        "hard_integrations": hard,
        "confidence_histogram": confidence_histogram(conf),
        "avg_confidence": round(float(conf["score"].mean()), 2) if len(conf) else None,
        "evidence_count": int(len(evidence)),
        "official_source_pct": official_pct,
        "corrections": corrections,
        "stage_durations": durations,
    }
    for name, value in stats.items():
        db.save_stat(conn, name, value)
    return stats


def auth_by_category(frame):
    result = {}
    for cat, group in frame.groupby("category_hint"):
        counts = {}
        for methods in group["auth_list"]:
            for m in methods:
                counts[m] = counts.get(m, 0) + 1
        result[cat] = counts
    return result


def confidence_histogram(conf):
    bins = [0, 0.2, 0.4, 0.6, 0.75, 0.9, 1.01]
    labels = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.75", "0.75-0.9", "0.9-1.0"]
    out = {}
    for pass_number, group in conf.groupby("pass_number"):
        cut = pd.cut(group["score"], bins=bins, labels=labels, right=False)
        out[f"pass_{pass_number}"] = cut.value_counts().reindex(labels).fillna(0).astype(int).to_dict()
    return out


def narrate_insights(stats, model):
    from tools import llm

    system = (
        "You are an analyst. You are given pre-computed statistics about 100 apps researched "
        "for AI agent toolkit buildability. Write the 5 strongest insights as plain punchy "
        "sentences a reviewer can skim. Use only the numbers given, never invent numbers. "
        'Reply as JSON: {"insights": ["...", "..."]}'
    )
    try:
        result = llm.complete_json(system, json.dumps(stats, default=str), model=model)
        return result.get("insights", [])
    except Exception:
        return []
