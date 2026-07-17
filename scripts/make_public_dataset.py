"""Build the recruiter-facing public dataset from output/results.json.

Reads the internal research export and writes two sanitized files next to it:

    output/results_public.json
    output/results_public.csv

Only public-facing fields are kept. Internal pipeline fields (ids, hints,
pass counters, timestamps, per-field confidence reasoning, evidence types)
are stripped. The script validates its own output and exits non-zero if the
public files are incomplete or leak internal metadata.

Standalone by design: it never touches the pipeline or the database.

Usage:
    python scripts/make_public_dataset.py
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "output" / "results.json"
PUBLIC_JSON = ROOT / "output" / "results_public.json"
PUBLIC_CSV = ROOT / "output" / "results_public.csv"

EXPECTED_APPS = 100

# Internal field names that must never appear anywhere in the public files.
INTERNAL_FIELDS = [
    "id",
    "category_hint",
    "website_hint",
    "research_pass",
    "updated_at",
    "confidence_reasons",
    "evidence_types",
]

CSV_HEADERS = [
    "App Name",
    "Category",
    "Description",
    "Auth Methods",
    "Gating",
    "API Type",
    "API Breadth",
    "MCP Availability",
    "Buildability",
    "Main Blocker",
    "Status",
    "Confidence",
    "Evidence URLs",
]


def to_public(app: dict) -> dict:
    urls = []
    for url in (app.get("evidence") or {}).values():
        if url and url not in urls:
            urls.append(url)
    return {
        "app_name": app.get("name", ""),
        "category": app.get("category", ""),
        "description": app.get("description", ""),
        "auth_methods": app.get("auth_methods") or [],
        "gating": app.get("gating", ""),
        "api_type": app.get("api_type", ""),
        "api_breadth": app.get("api_breadth", ""),
        "mcp_availability": app.get("mcp_available", ""),
        "buildability": app.get("buildability", ""),
        "main_blocker": app.get("main_blocker", ""),
        "status": app.get("status", ""),
        "confidence": app.get("confidence", ""),
        "evidence_urls": urls,
    }


def to_csv_row(pub: dict) -> list:
    return [
        pub["app_name"],
        pub["category"],
        pub["description"],
        ", ".join(pub["auth_methods"]),
        pub["gating"],
        pub["api_type"],
        pub["api_breadth"],
        pub["mcp_availability"],
        pub["buildability"],
        pub["main_blocker"],
        pub["status"],
        pub["confidence"],
        "; ".join(pub["evidence_urls"]),
    ]


def validate() -> list:
    errors = []

    public = json.loads(PUBLIC_JSON.read_text(encoding="utf-8"))
    if len(public) != EXPECTED_APPS:
        errors.append(f"JSON: expected {EXPECTED_APPS} apps, found {len(public)}")

    allowed_keys = set(to_public({}).keys())
    for row in public:
        extra = set(row.keys()) - allowed_keys
        if extra:
            errors.append(f"JSON: internal keys leaked on '{row.get('app_name')}': {sorted(extra)}")

    json_text = PUBLIC_JSON.read_text(encoding="utf-8")
    for field in INTERNAL_FIELDS:
        if f'"{field}"' in json_text:
            errors.append(f"JSON: internal field name '{field}' found in file")

    with PUBLIC_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if rows[0] != CSV_HEADERS:
        errors.append(f"CSV: unexpected headers {rows[0]}")
    if len(rows) - 1 != EXPECTED_APPS:
        errors.append(f"CSV: expected {EXPECTED_APPS} data rows, found {len(rows) - 1}")

    # Header equality above already guarantees no internal columns; the text
    # scan only covers distinctive names ("id" alone matches ordinary words).
    csv_text = PUBLIC_CSV.read_text(encoding="utf-8")
    for field in INTERNAL_FIELDS:
        if field != "id" and field in csv_text:
            errors.append(f"CSV: internal field name '{field}' found in file")

    return errors


def main() -> int:
    apps = json.loads(SOURCE.read_text(encoding="utf-8"))
    public = [to_public(app) for app in apps]

    PUBLIC_JSON.write_text(
        json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with PUBLIC_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        writer.writerows(to_csv_row(pub) for pub in public)

    errors = validate()
    if errors:
        for err in errors:
            print(f"FAIL  {err}")
        return 1

    print(f"OK    {PUBLIC_JSON.relative_to(ROOT)}  ({len(public)} apps)")
    print(f"OK    {PUBLIC_CSV.relative_to(ROOT)}  ({len(public)} rows)")
    print("OK    no internal pipeline fields present in public files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
