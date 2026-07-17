import csv
import random

from models.enums import RESEARCH_FIELDS
from storage import db

AUDIT_FIELDS = ["auth_methods", "gating", "api_type", "mcp_available", "buildability"]


def export_sample(conn, out_path, size, seed):
    apps = [dict(r) for r in db.all_apps(conn)]
    rng = random.Random(seed)
    by_category = {}
    for app in apps:
        by_category.setdefault(app["category_hint"], []).append(app)

    picked = [rng.choice(group) for group in by_category.values()]
    remaining = [a for a in apps if a not in picked]
    rng.shuffle(remaining)
    picked += remaining[: max(0, size - len(picked))]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["app_id", "app_name", "field_name", "agent_value", "human_value", "is_correct", "notes"])
        for app in sorted(picked, key=lambda a: a["id"]):
            for field_name in AUDIT_FIELDS:
                writer.writerow([app["id"], app["name"], field_name, app[field_name] or "UNKNOWN", "", "", ""])
    return len(picked)


def import_audit(conn, csv_path):
    conn.execute("DELETE FROM human_audit")
    count = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["is_correct"] == "":
                continue
            conn.execute(
                "INSERT INTO human_audit (app_id, field_name, agent_value, human_value, is_correct, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(row["app_id"]), row["field_name"], row["agent_value"],
                    row["human_value"], int(row["is_correct"]), row.get("notes", ""),
                ),
            )
            count += 1
    conn.commit()
    return count
