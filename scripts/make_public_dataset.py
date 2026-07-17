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


# --- value normalization ----------------------------------------------------
# The extractor occasionally returns free-text or case-variant values. The
# public dataset presents canonical enums; anything that cannot be mapped
# without guessing becomes UNKNOWN (the evidence URLs remain for the reader).

AUTH_TOKEN_SYNONYMS = {"BEARER", "ACCESS_TOKEN", "PERSONAL_ACCESS_TOKEN", "AUTHORIZATION_HEADER"}
AUTH_JUNK = {"AUTH_METHODS", "MCP", "CLI"}
MCP_CANON = {"OFFICIAL", "COMMUNITY", "NONE_FOUND", "UNKNOWN"}
API_CANON = {"REST", "GRAPHQL", "BOTH", "SDK_ONLY", "NONE", "UNKNOWN"}


def normalize_auth(methods) -> list:
    out = []
    for m in methods or []:
        if not isinstance(m, str):  # None / pandas NaN
            m = ""
        m = m.strip().upper().replace(" ", "_")
        if not m or m in AUTH_JUNK:
            continue
        if m in AUTH_TOKEN_SYNONYMS:
            m = "TOKEN"
        if m not in out:
            out.append(m)
    return out or ["UNKNOWN"]


def normalize_api_type(v) -> str:
    u = (v or "").strip().upper().replace(" ", "_")
    if u in API_CANON:
        return u
    if "REST" in u and "GRAPHQL" in u:
        return "BOTH"
    if "REST" in u:
        return "REST"
    if "GRAPHQL" in u:
        return "GRAPHQL"
    return "UNKNOWN"


def normalize_breadth(v) -> str:
    s = (v or "").strip().lower()
    if s in ("comprehensive", "broad", "limited", "unknown"):
        return s.upper() if s == "unknown" else s
    if any(w in s for w in ("comprehensive", "full", "complete", "extensive", "everything")):
        return "comprehensive"
    if any(w in s for w in ("broad", "wide")):
        return "broad"
    if any(w in s for w in ("limited", "selected", "narrow")):
        return "limited"
    return "UNKNOWN"


def normalize_mcp(v) -> str:
    u = (v or "").strip().upper()
    if u in MCP_CANON:
        return u
    if u == "UNOFFICIAL":
        return "COMMUNITY"
    return "UNKNOWN"


def to_public(app: dict) -> dict:
    urls = []
    for url in (app.get("evidence") or {}).values():
        if url and url not in urls:
            urls.append(url)
    return {
        "app_name": app.get("name", ""),
        # curated research-set taxonomy (10 categories), matching the
        # Category Distribution chart; falls back to the extracted value
        "category": app.get("category_hint") or app.get("category") or "UNKNOWN",
        "description": app.get("description", ""),
        "auth_methods": normalize_auth(app.get("auth_methods")),
        "gating": app.get("gating") or "UNKNOWN",
        "api_type": normalize_api_type(app.get("api_type")),
        "api_breadth": normalize_breadth(app.get("api_breadth")),
        "mcp_availability": normalize_mcp(app.get("mcp_available")),
        "buildability": app.get("buildability") or "UNKNOWN",
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
