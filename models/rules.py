from tools.search import root_domain

USABLE_APIS = {"REST", "GRAPHQL", "BOTH"}
KNOWN_AUTH = {"OAUTH2", "API_KEY", "BASIC", "TOKEN", "JWT"}
MCP_REGISTRY_HOSTS = {"github.com", "modelcontextprotocol.io", "mcp.so", "glama.ai", "smithery.ai"}


def decide_buildability(auth_methods, gating, api_type):
    auth = set(auth_methods) & KNOWN_AUTH
    if api_type == "NONE":
        return "BLOCKED", "no public API"
    if gating == "PARTNER_GATED":
        return "OUTREACH_REQUIRED", "API access requires a partnership or contact-sales gate"
    if api_type in USABLE_APIS and gating == "SELF_SERVE" and auth:
        return "BUILD_NOW", "NONE"
    if api_type in USABLE_APIS and gating == "PAID_ONLY":
        return "BUILD_WITH_CAVEATS", "credentials require a paid plan"
    if api_type in USABLE_APIS and gating == "FREE_WITH_APPROVAL":
        return "BUILD_WITH_CAVEATS", "credentials require an approval or app review step"
    if api_type == "SDK_ONLY":
        return "BUILD_WITH_CAVEATS", "no documented HTTP API, SDK only"
    if api_type in USABLE_APIS and auth:
        return "BUILD_WITH_CAVEATS", "usable API but access path unclear"
    return "UNKNOWN", "not enough verified facts to decide"


def normalize_mcp(claimed, evidence_url, website_hint):
    if claimed not in ("OFFICIAL", "COMMUNITY"):
        return claimed if claimed in ("NONE_FOUND", "UNKNOWN") else "UNKNOWN"
    if not evidence_url:
        return "UNKNOWN"
    host = root_domain(evidence_url)
    if host == root_domain(website_hint):
        return claimed
    if host in MCP_REGISTRY_HOSTS:
        return "COMMUNITY" if claimed == "COMMUNITY" else claimed
    return "UNKNOWN"
