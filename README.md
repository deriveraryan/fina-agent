# Fina Agent — Data Discovery & Enrichment Pipeline

This repository houses the data discovery, verification, and enrichment agents for **Fina** (the Filipino-Australian community directory). Specialized [Antigravity IDE](https://blog.google/technology/google-labs/project-mariner-antigravity/) subagents execute lightweight Python scripts locally, parse data, verify authenticity, and push results securely through a GraphQL layer into the live Fina PostgreSQL database.

---

## 🏛️ Repository Overview

This project is decoupled from the main Fina application backend. It runs lightweight Python scripts locally inside the Antigravity IDE, with three production-ready agents:

| Agent | Purpose |
|---|---|
| **`fina_listing_web_search`** | Discovers new Filipino listing candidates on Facebook, Instagram, TikTok, general web platforms, and Google Maps (via browser) using a task-based state machine |
| **`fina_listing_enrichment`** | Enriches existing listings by extracting reviews, synthesising descriptions, updating operating hours, and filling missing social URLs |
| **`fina_events_listing`** | Crawls social media pages of verified businesses to discover and push temporal upcoming events |

All three agents participate in a [shared memory protocol](#-shared-agent-memory) that enables cross-session learning.

> [!NOTE]
> Additional agents (`fina_listing_map_search`, `fina_listing_embedder`, `fina_docs_reviewer`) exist as skills/scripts but are **not yet production-ready**. Their supporting CLI scripts are available in `scripts/` for future activation. See the [Architecture Guide](docs/guides/ide_agent_architecture.md) for details.

---

## ⚙️ Required Setup & Configuration

### 1. Local Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables (`.env`)
Create a `.env` file in the repository root:
```bash
# Required for the agents to perform listing extraction
GEMINI_API_KEY="YOUR_ACTUAL_GEMINI_API_KEY"

# Used by the push script to geocode scraped addresses (falls back to city centers if omitted)
GOOGLE_MAPS_API_KEY="YOUR_GOOGLE_MAPS_API_KEY"

# Firebase Cloud Config (points to your Fina Backend instance)
GCP_PROJECT="fina-au"
```

### 3. Chrome DevTools MCP Configuration
Both production agents require a running Chrome DevTools MCP server (`chrome_devtools`). Add it to the `"mcpServers"` object in either:
- **Global Config**: `~/.gemini/config/mcp_config.json`
- **Workspace Config**: `.gemini/antigravity/mcp_config.json`

#### Option A: Auto-Launch Mode (Recommended)
The MCP server automatically launches and manages its own headless Chrome instance:
```json
"chrome_devtools": {
  "command": "npx",
  "args": [
    "-y",
    "chrome-devtools-mcp@latest"
  ]
}
```

#### Option B: Active Browser Mode (Connect to Local Session)
To let the agent interact with your active, logged-in Chrome window:
1. Launch Chrome with remote debugging:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   ```
2. Configure the MCP server to connect to port 9222:
   ```json
   "chrome_devtools": {
     "command": "npx",
     "args": [
       "-y",
       "chrome-devtools-mcp@latest",
       "--browserUrl",
       "http://127.0.0.1:9222"
     ]
   }
   ```

---

## 🚀 Run & Use Guide

### 1. Running via Chat Prompts

Trigger agents directly in the Antigravity Chat UI. For long-running scans, prefix with the `/goal` slash command so the agent runs continuously.

**Web Search Discovery:**
> **Task-Based Queue System**: The `fina_listing_web_search` skill targets a **single city** and executes the next pending search task (location × category × search template) from the generated task queue.
>
> "Use the `fina_listing_web_search` skill to search the web for new listings in SYDNEY."

**Listing Enrichment:**
> **Task-Based Queue System**: The `fina_listing_enrichment` skill targets a **single city** and processes the next pending listing for enrichment.
>
> "Use the `fina_listing_enrichment` skill to enrich listings in SYDNEY."

**Events Discovery:**
> **Task-Based Queue System**: The `fina_events_listing` skill targets a **single city** and scans the social media pages of the next pending listing for upcoming events.
>
> "Use the `fina_events_listing` skill to discover events in SYDNEY."

### 2. Running Scripts via CLI

#### Web Search Task Manager
```bash
# Generate all search task permutations for a city (idempotent — skips if file exists, pass --force to regenerate)
python3 scripts/agent_web_search_tasks.py --action generate --city SYDNEY --trace-id <CONVERSATION_ID>

# Get the next pending task (atomically transitions to IN_PROGRESS)
python3 scripts/agent_web_search_tasks.py --action next --city SYDNEY --trace-id <CONVERSATION_ID>

# Mark a task as completed with metrics
python3 scripts/agent_web_search_tasks.py --action complete --city SYDNEY --task-id sydney__RESTAURANT__0__sydney \
  --listings-created 5 --pages-searched 3 --candidates-evaluated 8 --candidates-rejected 1 \
  --candidates-duplicate 2 --candidates-merged 1 --maps-results-scraped 15 --trace-id <CONVERSATION_ID>

# View aggregate progress
python3 scripts/agent_web_search_tasks.py --action summary --city SYDNEY --trace-id <CONVERSATION_ID>
```

#### Enrichment Task Manager
```bash
# Generate per-listing enrichment tasks for a city (idempotent, pass --force to regenerate)
python3 scripts/agent_enrichment_tasks.py --action generate --city SYDNEY --trace-id <CONVERSATION_ID>

# Get the next pending enrichment task (atomically transitions to IN_PROGRESS)
python3 scripts/agent_enrichment_tasks.py --action next --city SYDNEY --trace-id <CONVERSATION_ID>

# Mark enrichment task as completed with metrics
python3 scripts/agent_enrichment_tasks.py --action complete --city SYDNEY --task-id <ID> \
  --listings-enriched 1 --reviews-extracted 8 --reviews-pushed 8 --socials-enriched 2 \
  --descriptions-rewritten 1 --maps-visits 1 --trace-id <CONVERSATION_ID>

# View aggregate enrichment progress
python3 scripts/agent_enrichment_tasks.py --action summary --city SYDNEY --trace-id <CONVERSATION_ID>
```

#### Events Task Manager
```bash
# Generate per-listing events tasks for a city (only listings with social URLs, idempotent)
python3 scripts/agent_events_tasks.py --action generate --city SYDNEY --trace-id <CONVERSATION_ID>

# Get the next pending events task (atomically transitions to IN_PROGRESS)
python3 scripts/agent_events_tasks.py --action next --city SYDNEY --trace-id <CONVERSATION_ID>

# Mark events task as completed with metrics
python3 scripts/agent_events_tasks.py --action complete --city SYDNEY --task-id <ID> \
  --events-discovered 3 --events-pushed 3 --social-urls-scanned 2 \
  --follower-counts-updated 2 --bookmarks-updated 2 --trace-id <CONVERSATION_ID>

# View aggregate events progress
python3 scripts/agent_events_tasks.py --action summary --city SYDNEY --trace-id <CONVERSATION_ID>
```

#### Shared Utilities
```bash
# Fetch existing city listings for deduplication context
python3 scripts/agent_fetch_targets.py --type city-listings --city SYDNEY --trace-id <CONVERSATION_ID> > tmp/existing_city_listings.json

# Check for duplicate listings
python3 scripts/agent_check_duplicate.py --file tmp/existing_city_listings.json --name "<NAME>" --url "<URL>" --trace-id <CONVERSATION_ID>

# Push data via GraphQL (single payload)
python3 scripts/agent_graphql_push.py --operation <CreateListing|UpdateListingData|CreateReview|CreateEvent|UpdateListingSocialUrls|UpsertSocialPostTracker> --variables @tmp/payload.json --trace-id <CONVERSATION_ID>
```

> [!IMPORTANT]
> **Category Validation & Normalization**: The push script validates `category` and `categories` values against [categories.json](data/categories.json). Case-insensitive normalization (to uppercase) is applied automatically. Invalid categories trigger a fatal error (exit code 1).

### 3. Scheduling Automatic Scans

Schedule agents to run periodic background scans using the `/schedule` slash command:
```bash
# Web search discovery — daily at midnight
/schedule CronExpression="0 0 * * *" Prompt="Use the fina_listing_web_search skill to search the web for new listings in SYDNEY."

# Listing enrichment — daily at 6am
/schedule CronExpression="0 6 * * *" Prompt="Use the fina_listing_enrichment skill to enrich listings in SYDNEY."

# Events discovery — daily at noon
/schedule CronExpression="0 12 * * *" Prompt="Use the fina_events_listing skill to discover events in SYDNEY."
```
*(Note: The Antigravity IDE window must remain active for scheduled agents to execute.)*

---

## 🧠 Shared Agent Memory

All three production agents participate in a shared, self-evolving memory protocol via [`data/fina_agent_memory.md`](data/fina_agent_memory.md). This enables agents to learn from their executions and share operational knowledge across sessions.

**How it works:**
1. **Read Phase** — At session start, the agent reads the memory file and internalises relevant insights.
2. **Retrospective Phase** — After task completion, the agent evaluates whether the execution surfaced new operational knowledge. If yes, it merges the insight into the memory file within a **500-line budget**. If no, it skips the update entirely.

The memory file is not a changelog — it contains only distilled, reusable operational knowledge (platform behaviours, search patterns, city intelligence, known pitfalls). See the [Architecture Guide](docs/guides/ide_agent_architecture.md#-shared-agent-memory) for the full design rationale.

---

## 🧪 Run Unit Tests

This project practices Test-Driven Development (TDD). The test suite runs entirely offline with mocked APIs:
```bash
source .venv/bin/activate
python3 -m unittest discover tests
```

---

## 📖 Further Reading

* **Architecture Guide**: [docs/guides/ide_agent_architecture.md](docs/guides/ide_agent_architecture.md) — Detailed agent flows, mermaid diagrams, database integration, and memory framework design.
* **Agent Rules**: [AGENTS.md](AGENTS.md) — Architectural constraints, coding standards, and invariants for all agents.
* **Categories**: [data/categories.json](data/categories.json) — Canonical business category definitions and search templates.
