import pandas as pd

from storage import db


def compute_accuracy(conn):
    audit = pd.read_sql("SELECT * FROM human_audit", conn)
    if audit.empty:
        db.save_stat(conn, "accuracy", {"available": False})
        return {"available": False}

    log = pd.read_sql("SELECT app_id, field_name, old_value, result FROM verification_log", conn)
    corrected = log[log["result"] == "CORRECTED"][["app_id", "field_name", "old_value"]]

    merged = audit.merge(corrected, on=["app_id", "field_name"], how="left")

    def first_pass_correct(row):
        if pd.isna(row["old_value"]):
            return row["is_correct"]
        return 1 if str(row["old_value"]) == str(row["human_value"]) else 0

    merged["pass1_correct"] = merged.apply(first_pass_correct, axis=1)

    per_field = (
        merged.groupby("field_name")
        .agg(pass1=("pass1_correct", "mean"), final=("is_correct", "mean"), checks=("is_correct", "size"))
        .round(3)
    )

    misses = merged[merged["is_correct"] == 0][
        ["app_id", "field_name", "agent_value", "human_value", "notes"]
    ].to_dict("records")

    result = {
        "available": True,
        "checks": int(len(merged)),
        "apps_sampled": int(merged["app_id"].nunique()),
        "pass1_accuracy": round(float(merged["pass1_correct"].mean()), 3),
        "final_accuracy": round(float(merged["is_correct"].mean()), 3),
        "per_field": {i: r.to_dict() for i, r in per_field.iterrows()},
        "misses": misses,
    }
    db.save_stat(conn, "accuracy", result)
    return result
