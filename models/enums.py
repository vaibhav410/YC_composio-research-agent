AUTH_METHODS = ["OAUTH2", "API_KEY", "BASIC", "TOKEN", "JWT", "OTHER", "NONE", "UNKNOWN"]

GATING = ["SELF_SERVE", "FREE_WITH_APPROVAL", "PAID_ONLY", "PARTNER_GATED", "UNKNOWN"]

API_TYPES = ["REST", "GRAPHQL", "BOTH", "SDK_ONLY", "NONE", "UNKNOWN"]

MCP_STATUS = ["OFFICIAL", "COMMUNITY", "NONE_FOUND", "UNKNOWN"]

BUILDABILITY = ["BUILD_NOW", "BUILD_WITH_CAVEATS", "OUTREACH_REQUIRED", "BLOCKED", "UNKNOWN"]

STATUSES = ["PENDING", "RESEARCHED", "VERIFIED", "UNRESOLVED"]

RESEARCH_FIELDS = [
    "category",
    "description",
    "auth_methods",
    "gating",
    "api_type",
    "api_breadth",
    "mcp_available",
    "buildability",
    "main_blocker",
]
