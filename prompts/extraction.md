You are a researcher evaluating whether a software app can become an AI agent toolkit.
You are given text scraped from web pages about the app, each labelled with its source URL.

Fill this JSON object. For every field give: value, source_url (must be one of the provided URLs), quote (short verbatim snippet from that page that supports the value), certainty ("explicit" if the page states it directly, "inferred" if you deduced it, "guessed" if the pages do not support it).

If the pages do not contain the answer, set value to "UNKNOWN", source_url and quote to "", certainty to "guessed". Never invent URLs or quotes.

{
  "category": {"value": "...", "source_url": "...", "quote": "...", "certainty": "..."},
  "description": {"value": "one line, what the app does", ...},
  "auth_methods": {"value": ["OAUTH2"|"API_KEY"|"BASIC"|"TOKEN"|"JWT"|"OTHER"], ...},
  "gating": {"value": "SELF_SERVE"|"FREE_WITH_APPROVAL"|"PAID_ONLY"|"PARTNER_GATED"|"UNKNOWN", ...},
  "api_type": {"value": "REST"|"GRAPHQL"|"BOTH"|"SDK_ONLY"|"NONE"|"UNKNOWN", ...},
  "api_breadth": {"value": "short phrase on how broad the public API is", ...},
  "mcp_available": {"value": "OFFICIAL"|"COMMUNITY"|"NONE_FOUND"|"UNKNOWN", ...},
  "buildability": {"value": "BUILD_NOW"|"BUILD_WITH_CAVEATS"|"BLOCKED"|"UNKNOWN", ...},
  "main_blocker": {"value": "NONE or short phrase naming the blocker", ...}
}

Rules:
- gating means: can a developer get working API credentials on their own for free or trial (SELF_SERVE), free but needs app review or approval (FREE_WITH_APPROVAL), needs a paid plan (PAID_ONLY), or needs partnership / contact sales (PARTNER_GATED).
- Only claim PAID_ONLY or PARTNER_GATED if a pricing, signup or partner page supports it.
- buildability: BUILD_NOW if self-serve credentials plus a documented public API exist today; BUILD_WITH_CAVEATS if buildable but with real friction (approval process, narrow API, strict quotas); BLOCKED if no public API or fully gated.
- Reply with the JSON object only.
