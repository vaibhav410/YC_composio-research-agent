from models.schemas import ResearchPlan
from tools.search import root_domain

QUERY_TEMPLATES = [
    "{name} API documentation authentication",
    "{name} developer docs OAuth or API key",
    "{name} REST API or GraphQL reference",
    "{name} API pricing free developer plan",
    "{name} MCP server",
]

VERIFY_TEMPLATES = {
    "auth_methods": ["{name} API authentication OAuth or API key", "how to authenticate {name} API"],
    "gating": ["{name} developer account free signup", "{name} API access contact sales partner"],
    "api_type": ["{name} REST or GraphQL API", "{name} API endpoints reference"],
    "mcp_available": ["{name} model context protocol server github", "{name} MCP integration"],
    "buildability": ["{name} API limitations restrictions", "{name} public API availability"],
    "gating_default": ["{name} API access requirements"],
}


def build_plan(app_row):
    name = app_row["name"]
    site = app_row["website_hint"]
    domain = root_domain(site)
    queries = [t.format(name=name) + f" site:{domain}" for t in QUERY_TEMPLATES[:1]]
    queries += [t.format(name=name) for t in QUERY_TEMPLATES]
    guesses = [f"https://{site}" if not site.startswith("http") else site]
    for prefix in ("developers", "docs", "developer", "api"):
        if not site.startswith(prefix):
            guesses.append(f"https://{prefix}.{domain}")
    return ResearchPlan(
        app_id=app_row["id"], name=name, website=site, queries=queries, docs_guesses=guesses
    )


def verify_queries(name, field_name):
    templates = VERIFY_TEMPLATES.get(field_name, VERIFY_TEMPLATES["gating_default"])
    return [t.format(name=name) for t in templates]
