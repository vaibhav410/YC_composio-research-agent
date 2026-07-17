# Composio App Research Agent

An autonomous pipeline that researched 100 apps for AI agent toolkit buildability — auth methods, self-serve access, API surface, MCP availability — with per-field evidence links, a two-pass verification loop, and a human accuracy audit.

**Live report:** https://vaibhav410.github.io/YC_composio-research-agent/
**Repository:** https://github.com/vaibhav410/YC_composio-research-agent

Total cost to run: **$0**. Groq free tier, DuckDuckGo search, Playwright, SQLite, GitHub Pages.

## TL;DR of the findings

Open the live report — the headline patterns sit at the top. In short: which auth dominates, which categories are self-serve vs partner-gated, the most common blockers, and the easy-win list Composio could build this week.

## How it works

```
apps.csv → Planner → Research (search + scrape + LLM extract, every field
must cite a URL + verbatim quote) → Confidence scoring → Verification
(independent second pass + citation re-check against the live page) →
Pattern analysis (Pandas, LLM only narrates) → Static HTML dashboard
```

- Fields the sources don't support come back `UNKNOWN`, never guessed.
- Fields below the confidence threshold get a second research pass that is blind to the first pass's reasoning.
- Cited quotes are re-fetched and matched against the live page to catch hallucinated citations.
- Apps that defeated the agent are marked `UNRESOLVED` and shown on the page.
- All statistics are computed in Pandas; the LLM never produces a number.

## Run it

```bash
git clone https://github.com/vaibhav410/YC_composio-research-agent
cd YC_composio-research-agent
pip install -r requirements.txt
playwright install chromium
cp .env.example .env        # add your free Groq API key
python scripts/run_all.py
```

Output lands in `output/index.html`. The pipeline checkpoints every app to SQLite, so a crash or rate-limit death resumes where it left off — just rerun the same command.

Stages can also run individually:

```bash
python scripts/run_research.py      # pass 1: research all PENDING apps
python scripts/run_verification.py  # pass 2: verify low-confidence fields
python scripts/run_report.py        # stats + dashboard
```

## Public dataset

`output/results_public.csv` and `output/results_public.json` are the shareable dataset — one row per app with only the public fields: App Name, Category, Description, Auth Methods, Gating, API Type, API Breadth, MCP Availability, Buildability, Main Blocker, Status, Confidence, Evidence URLs. Internal pipeline fields (ids, planner hints, pass counters, timestamps, per-field confidence reasoning) are stripped. The dashboard's **Download Dataset** button serves the public CSV.

Regenerate after a pipeline run:

```bash
python scripts/make_public_dataset.py   # also validates: 100 apps, no internal fields
```

## Human audit loop

```bash
python scripts/export_sample.py     # writes data/audit_sample.csv (stratified, seeded)
# check each row against real docs by hand, fill human_value / is_correct / notes
python scripts/import_audit.py      # computes first-pass vs final accuracy
python scripts/run_report.py        # accuracy section appears on the dashboard
```

## Project structure

```
agents/        planner, researcher, verifier, pattern analyzer
prompts/       all LLM instructions, versioned as markdown
models/        field schemas and enums
tools/         search (DuckDuckGo), fetcher (requests → playwright), llm (Groq), browser checks
verification/  confidence formula, audit sampler, accuracy report
storage/       SQLite schema, checkpointing, JSON export
templates/     Jinja2 dashboard (single self-contained HTML)
scripts/       CLI entrypoints per stage
data/          apps.csv input, research.db, page cache
output/        index.html, results.json, results_public.csv, results_public.json
docs/          published copy of the dashboard + public dataset (GitHub Pages / Vercel)
```

## Configuration

`config.yaml`: model name, requests per minute, pages per app, confidence threshold, audit sample size and seed.

The dashboard ships a precompiled, minified Tailwind stylesheet (no CDN at runtime). If you add new utility classes to `templates/index.html.j2`, rebuild it with `npx tailwindcss` against the generated `output/index.html` and swap the `<style>` block.

## Design decisions

- **Pure-Python state machine** over an agent framework: 100 identical research tasks need reliability and resumability, not dynamic planning.
- **SQLite checkpoints per app**: free-tier rate limits mean the run *will* be interrupted; restart cost is one app, not one hundred.
- **Evidence-first extraction**: a claim without a URL and quote is capped at low confidence by construction, so hallucinations can't reach the report quietly.
- **Static single-file dashboard**: the deliverable is one HTML page a reviewer reads in two minutes; the full dataset is embedded as JSON so an agent can consume it too.

## Limitations

- Findings reflect public docs at run time; APIs and pricing change.
- DuckDuckGo occasionally throttles; the pipeline backs off and falls back to direct docs-URL guesses.
- MCP availability is hard to prove negative — `NONE_FOUND` means "not found where searched", with the searched sources cited.
