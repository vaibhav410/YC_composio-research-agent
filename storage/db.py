import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_hint TEXT,
    website_hint TEXT,
    category TEXT,
    description TEXT,
    auth_methods TEXT,
    gating TEXT,
    api_type TEXT,
    api_breadth TEXT,
    mcp_available TEXT,
    buildability TEXT,
    main_blocker TEXT,
    status TEXT DEFAULT 'PENDING',
    research_pass INTEGER DEFAULT 0,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    field_name TEXT,
    source_url TEXT,
    quote TEXT,
    fetch_method TEXT,
    source_type TEXT,
    pass_number INTEGER,
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS confidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    field_name TEXT,
    score REAL,
    reasons TEXT,
    pass_number INTEGER
);
CREATE TABLE IF NOT EXISTS verification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    method TEXT,
    result TEXT,
    verified_at TEXT
);
CREATE TABLE IF NOT EXISTS human_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    field_name TEXT,
    agent_value TEXT,
    human_value TEXT,
    is_correct INTEGER,
    pass_number INTEGER,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT,
    value_json TEXT,
    computed_at TEXT
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    evidence_cols = {r["name"] for r in conn.execute("PRAGMA table_info(evidence)")}
    if "source_type" not in evidence_cols:
        conn.execute("ALTER TABLE evidence ADD COLUMN source_type TEXT DEFAULT 'general'")
        conn.commit()


def load_apps_csv(conn, csv_path):
    import csv

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            conn.execute(
                "INSERT OR IGNORE INTO apps (id, name, category_hint, website_hint) VALUES (?, ?, ?, ?)",
                (int(row["id"]), row["name"], row["category"], row["website"]),
            )
    conn.commit()


def apps_with_status(conn, status):
    return conn.execute("SELECT * FROM apps WHERE status = ? ORDER BY id", (status,)).fetchall()


def apps_needing_research(conn):
    return conn.execute(
        "SELECT * FROM apps WHERE status = 'PENDING' "
        "OR (status = 'UNRESOLVED' AND category IS NULL) ORDER BY id"
    ).fetchall()


def all_apps(conn):
    return conn.execute("SELECT * FROM apps ORDER BY id").fetchall()


def save_record(conn, app_id, fields, status, pass_number):
    assignments = [f"{k} = ?" for k in fields] + ["status = ?", "research_pass = ?", "updated_at = ?"]
    values = list(fields.values()) + [status, pass_number, now(), app_id]
    conn.execute(f"UPDATE apps SET {', '.join(assignments)} WHERE id = ?", values)
    conn.commit()


def add_evidence(conn, app_id, ev):
    exists = conn.execute(
        "SELECT 1 FROM evidence WHERE app_id = ? AND field_name = ? AND source_url = ? AND quote = ?",
        (app_id, ev.field_name, ev.source_url, ev.quote),
    ).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO evidence (app_id, field_name, source_url, quote, fetch_method, source_type, pass_number, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (app_id, ev.field_name, ev.source_url, ev.quote, ev.fetch_method, ev.source_type, ev.pass_number, now()),
    )
    conn.commit()


def set_confidence(conn, app_id, field_name, score, reasons, pass_number):
    conn.execute(
        "DELETE FROM confidence WHERE app_id = ? AND field_name = ?", (app_id, field_name)
    )
    conn.execute(
        "INSERT INTO confidence (app_id, field_name, score, reasons, pass_number) VALUES (?, ?, ?, ?, ?)",
        (app_id, field_name, score, reasons, pass_number),
    )
    conn.commit()


def confidences_for(conn, app_id):
    rows = conn.execute("SELECT * FROM confidence WHERE app_id = ?", (app_id,)).fetchall()
    return {r["field_name"]: r["score"] for r in rows}


def confidence_details(conn, app_id):
    rows = conn.execute("SELECT * FROM confidence WHERE app_id = ?", (app_id,)).fetchall()
    return {r["field_name"]: {"score": r["score"], "reasons": r["reasons"]} for r in rows}


def evidence_for(conn, app_id, field_name=None):
    if field_name:
        return conn.execute(
            "SELECT * FROM evidence WHERE app_id = ? AND field_name = ? ORDER BY pass_number DESC",
            (app_id, field_name),
        ).fetchall()
    return conn.execute("SELECT * FROM evidence WHERE app_id = ?", (app_id,)).fetchall()


def log_verification(conn, app_id, field_name, old, new, method, result):
    conn.execute(
        "INSERT INTO verification_log (app_id, field_name, old_value, new_value, method, result, verified_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (app_id, field_name, old, new, method, result, now()),
    )
    conn.commit()


def save_stat(conn, name, value):
    conn.execute("DELETE FROM statistics WHERE metric_name = ?", (name,))
    conn.execute(
        "INSERT INTO statistics (metric_name, value_json, computed_at) VALUES (?, ?, ?)",
        (name, json.dumps(value), now()),
    )
    conn.commit()


def all_stats(conn):
    rows = conn.execute("SELECT metric_name, value_json FROM statistics").fetchall()
    return {r["metric_name"]: json.loads(r["value_json"]) for r in rows}
