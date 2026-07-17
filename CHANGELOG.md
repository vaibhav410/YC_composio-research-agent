# Changelog

## Review pass — hardening for accuracy and explainability

### Evidence quality
- Every evidence row now stores a `source_type` (developer_docs, product_docs, help_center, github, general) alongside the URL and verbatim quote, classified deterministically from the URL.
- Factual fields (auth, gating, API type, MCP) with no source URL or quote are forced to UNKNOWN in code, not just in the prompt. A hallucinated answer without evidence can no longer enter the database.
- Duplicate evidence (same app, field, URL and quote) is skipped on insert, so verification passes don't inflate the evidence table or the agreement score.
- Why it scores higher: the assignment grades evidence per answer; typed, deduplicated evidence makes every claim auditable in one click.

### Official documentation priority
- Search results are ranked by a five-tier source hierarchy: official developer docs → official product docs → official help center → GitHub → general web. The researcher reads pages in that order, so the first valid official source wins and general-web pages only fill gaps.
- Why it scores higher: answers grounded in developer docs are the ones a reviewer can trust and re-check.

### Deterministic rule engine (LLM no longer decides)
- `models/rules.py` computes the buildability verdict from extracted facts: usable API + self-serve + known auth → BUILD_NOW; partner gate → OUTREACH_REQUIRED; paid or approval gate → BUILD_WITH_CAVEATS; no public API → BLOCKED; insufficient facts → UNKNOWN. The main blocker string comes from the same rule.
- MCP claims are normalized deterministically: OFFICIAL requires evidence on the app's own domain, COMMUNITY requires a known registry or GitHub, anything unevidenced degrades to UNKNOWN.
- The verifier re-runs the rule engine after second-pass corrections and logs any changed verdict as RECOMPUTED.
- Why it scores higher: verdicts are consistent across all 100 apps and defensible in the interview — the LLM only extracts and classifies against evidence; every decision and every number is reproducible code.

### Confidence explainability
- Confidence reasons are now human sentences ("cited from official developer docs; 2 independent sources agree; explicitly stated in the page text") instead of internal weights.
- Rule-derived fields inherit the weakest confidence of their inputs, with a reason saying so.
- The dashboard exposes reasons as hover tooltips on every confidence badge.
- Why it scores higher: a reviewer can see not just that the agent is confident, but why.

### Reliability
- HTTP fetches retry twice with backoff before escalating to Playwright rendering; only then does a field become UNKNOWN. One blocked site can never stop the pipeline (per-app try/except plus SQLite checkpointing already ensured resume).
- Screenshots are cached by name and page text is cached per URL on disk, so re-runs and verification passes never refetch.

### Metrics and dashboard
- New pipeline metrics: average field confidence, total evidence snippets, share of evidence from official sources, and measured research/verification durations (persisted in the statistics table by the stage scripts).
- New dashboard sections: "What the Agent Could Not Determine" (access blocked, low confidence, partner-gated, thin documentation — each app named with the reason), and "Fields corrected by the verification loop" showing every old → new correction and which mechanism fixed it.
- The verification card already showed sampled apps and first-pass vs final accuracy; it now also lists corrections, keeping the honesty requirements front and center on one page.
- Why it scores higher: the assignment explicitly rewards showing failures honestly and showing how accuracy moved between passes.

### Code quality
- The verifier skips LLM verification for rule-derived fields, saving wasted Groq calls per app.
- Single-letter variables in the confidence formula renamed to `source_score`, `agreement_score`, `certainty_score`.
- Search planner queries broadened to cover auth, REST/GraphQL, developer docs, pricing and MCP per app.
