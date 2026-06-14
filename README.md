# Fina Agent — Data Extraction Scraper Pipeline

This repository houses the data discovery, verification, enrichment, and scraping agents for the Fina platform (the Filipino-Australian community directory). It consists of specialized Antigravity IDE subagents that scrape data from Google Maps (New) and social media (Facebook/Instagram), verify authenticity, and push results securely via a GraphQL client directly into the live Fina Postgres database.

---

## 🏛️ Repository Overview

This project is decoupled from the main Fina application backend. It runs lightweight Python scripts locally inside the Antigravity IDE:
* **Google Maps Scraper**: Scrapes candidate businesses matching category & city.
* **Web & Social Searcher**: Discovers new Filipino listing candidates on Facebook, Instagram, TikTok, and general web platforms using a task-based state machine.
* **Social Enricher**: Enriches existing listings with missing Facebook, Instagram, and TikTok URLs.
* **Browser Event Crawler**: Crawls business pages to harvest upcoming temporal events.
* **Listing Embedder**: Generates and backfills vector description embeddings for semantic search.
* **Documentation Reviewer**: Audits repository documentation for alignment with the codebase.

---

## ⚙️ Required Setup & Configuration

To run the agents, you must set up a local virtual environment and configure the environment variables.

### 1. Local Python Environment
Create a virtual environment and install the required dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables (`.env`)
Create a `.env` file in the root of the `fina-agent` repository:
```bash
# Required by the local agents and Cloud Functions to run browser-use/crawl4ai and perform listing extraction.
GEMINI_API_KEY="YOUR_ACTUAL_GEMINI_API_KEY"

# Optional. Used by the push script to geocode scraped addresses. 
# Falls back to city centers if omitted.
GOOGLE_MAPS_API_KEY="YOUR_GOOGLE_MAPS_API_KEY"

# Firebase Cloud Configs (points to your Fina Backend instance)
GCP_PROJECT="fina-au"
```

---

## 🚀 Run & Use Guide

You can trigger these discovery scans manually through the Antigravity Chat UI or run the underlying scripts directly in your shell.

### 1. The Scraper Agents

* **`fina_listing_map_search`**: Queries Google Places Text Search using a task-based state machine (1 city × 1 category × 1 template per run).
* **`fina_listing_web_search`**: Discovers new Filipino listings on social platforms using a task-based state machine (1 location × 1 category × 1 template per run).
* **`fina_enrich_listing_socials_finder`**: Enriches existing listings with missing Facebook/Instagram URLs.
* **`fina_listing_embedder`**: Audits and generates vector description embeddings for listings missing them.
* **`fina_events_finder`**: Crawls business social media pages to harvest upcoming events.
* **`fina_docs_reviewer`**: Audits repository documentation files for any gaps or discrepancies against the current codebase.

For a detailed flow diagram of how these agents operate, see the [Native IDE Agent Architecture Guide](docs/guides/ide_agent_architecture.md).

### 2. Running Scans via Chat Prompts
You can trigger a manual scan by asking the Antigravity agent directly in the chat. For large, multi-city scans, we highly recommend prefixing your prompt with the `/goal` slash command so the agent runs continuously in the background without stopping.

*   *Places Discovery*:
> [!IMPORTANT]
    > **Task-Based Queue System**: The `fina_listing_map_search` skill targets a **single city** and automatically executes the next pending Google Places search task (category × search template) from the generated task queue. By default, only city-level tasks are generated.
    >
    > "Use the `fina_listing_map_search` skill to search Google Places for new listings in SYDNEY."
*   *Web/Social Discovery*:
    > **Task-Based Queue System**: The `fina_listing_web_search` skill targets a **single city** and automatically executes the next pending search task (location × category × search template) from the generated task queue.
    >
    > "Use the `fina_listing_web_search` skill to search the web for new listings in SYDNEY."
*   *Missing Socials Finder*:
    > "Use the `fina_enrich_listing_socials_finder` skill to back-fill missing social URLs in SYDNEY."
*   *Listing Embedder*:
    > "Use the `fina_listing_embedder` skill to generate missing description vector embeddings in SYDNEY."
    >
    > **To process only a limited number of listings:**
    > "Use the `fina_listing_embedder` skill to generate vector embeddings in SYDNEY with a limit of 10."
*   *Events Finder*:
    > **Single City Target Restriction**: To prevent prompt context window bloat and ensure high reliability, the `fina_events_finder` skill strictly targets a **single city** per execution run. Multi-city sweeps must be run in separate, independent agent sessions.
    >
    > "Use the `fina_events_finder` skill to discover events in MELBOURNE."
*   *Documentation Reviewer*:
    > "Use the `fina_docs_reviewer` skill to review the repository documentation for any gaps."

### 3. Running Scripts via CLI
You can execute the underlying discovery and database push scripts directly in your shell.

*   **Web Search Task Manager**:
    ```bash
    # Generate all search task permutations for a city (idempotent — skips if file exists)
    python3 scripts/agent_web_search_tasks.py --action generate --city SYDNEY --trace-id <CONVERSATION_ID>

    # Get the next pending task (atomically transitions to IN_PROGRESS)
    python3 scripts/agent_web_search_tasks.py --action next --city SYDNEY --trace-id <CONVERSATION_ID>

    # Mark a task as completed with metrics
    python3 scripts/agent_web_search_tasks.py --action complete --city SYDNEY --task-id sydney__RESTAURANT__0__sydney --listings-created 5 --pages-searched 3 --candidates-evaluated 8 --candidates-rejected 1 --candidates-duplicate 2 --trace-id <CONVERSATION_ID>

    # View aggregate progress
    python3 scripts/agent_web_search_tasks.py --action summary --city SYDNEY --trace-id <CONVERSATION_ID>
    ```
*   **Maps Search Task Manager**:
    ```bash
    # Generate city-level task permutations (idempotent, pass --include-suburbs for suburb tasks)
    python3 scripts/agent_maps_search_tasks.py --action generate --city SYDNEY --trace-id <CONVERSATION_ID>

    # Get the next pending task (atomically transitions to IN_PROGRESS)
    python3 scripts/agent_maps_search_tasks.py --action next --city SYDNEY --trace-id <CONVERSATION_ID>

    # Mark a task as completed with metrics
    python3 scripts/agent_maps_search_tasks.py --action complete --city SYDNEY --task-id sydney__RESTAURANT__0__sydney --listings-created 3 --places-fetched 15 --candidates-evaluated 15 --candidates-rejected 10 --candidates-duplicate 2 --trace-id <CONVERSATION_ID>

    # View aggregate progress
    python3 scripts/agent_maps_search_tasks.py --action summary --city SYDNEY --trace-id <CONVERSATION_ID>
    ```
*   **Listing Vector Embedding Generator**:
    ```bash
    # Generate and back-fill description embeddings for listings missing them
    python3 scripts/agent_generate_embeddings.py --city SYDNEY --limit 10 --trace-id <CONVERSATION_ID>
    ```
*   **Google Places Fetch (single query)**:
    ```bash
    python3 scripts/agent_maps_fetch.py --query "Filipino restaurant in Sydney" --city SYDNEY --category RESTAURANT --trace-id <CONVERSATION_ID>
    ```
*   **Fetch Targets**:
    ```bash
    # Retrieve listings missing social URLs for a city
    python3 scripts/agent_fetch_targets.py --type missing-social --city SYDNEY --trace-id <CONVERSATION_ID> > tmp/missing_socials_targets.json

    # Retrieve business social URLs for a city (used by events finder)
    python3 scripts/agent_fetch_targets.py --type business-socials --city SYDNEY --trace-id <CONVERSATION_ID> > tmp/business_socials_targets.json

    # Retrieve all city listings for deduplication context (used by web finder)
    python3 scripts/agent_fetch_targets.py --type city-listings --city SYDNEY --trace-id <CONVERSATION_ID> > tmp/existing_city_listings.json

    # Retrieve scan bookmark for a listing on a platform (used by events finder)
    python3 scripts/agent_fetch_targets.py --type social-post-tracker --listing-id <LISTING_UUID> --platform facebook --trace-id <CONVERSATION_ID>
    ```
*   **Check Duplicate**:
    ```bash
    python3 scripts/agent_check_duplicate.py --file tmp/existing_city_listings.json --name "<NAME>" --url "<URL>" --trace-id <CONVERSATION_ID>
    ```
*   **GraphQL Database Push**:
    ```bash
    # Push/Upsert a social post tracker entry
    python3 scripts/agent_graphql_push.py --operation UpsertSocialPostTracker --variables '{"listingId": "listing-uuid", "platform": "FACEBOOK", "lastPostDate": "2026-06-09T00:00:00Z"}' --trace-id <CONVERSATION_ID>

    # Create listing or event (e.g. from variables file)
    python3 scripts/agent_graphql_push.py --operation CreateListing --variables @tmp/payload.json --trace-id <CONVERSATION_ID>
    ```
    
    > [!IMPORTANT]
    > **Category Validation & Normalization**: The database push script strictly validates `category` and `categories` values against the canonical definitions in [categories.json](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/data/categories.json) (e.g., `RESTAURANT`, `CAFE`, etc.). Case-insensitive normalization (to uppercase) is automatically applied. Invalid categories will trigger a validation error and terminate script execution (exiting with code 1).

### 4. Scheduling Automatic Scans
You can schedule the agents to run periodic background scans using the `/schedule` slash command:
*   *Places Scan Schedule*:
    ```bash
    /schedule CronExpression="0 12 * * *" Prompt="Use the fina_listing_map_search skill to search Google Places for new listings in SYDNEY."
    ```
*   *Community Scan Schedule*:
    ```bash
    /schedule CronExpression="0 0 * * *" Prompt="Use the fina_listing_web_search skill to scan for events and listings across all cities."
    ```
*   *Listing Embedding Generator Schedule*:
    ```bash
    /schedule CronExpression="0 18 * * *" Prompt="Use the fina_listing_embedder skill to generate missing description vector embeddings in SYDNEY."
    ```
*   *Documentation Review Schedule*:
    ```bash
    /schedule CronExpression="0 0 * * 0" Prompt="Use the fina_docs_reviewer skill to audit documentation for gaps."
    ```
*(Note: The Antigravity IDE window must remain active for scheduled subagents to execute).*

---

## 🧪 Run Unit Tests

This project practices Test-Driven Development (TDD). The test suite runs entirely offline with mocked APIs to ensure fast, deterministic feedback.

Execute the test runner from the root directory:
```bash
source .venv/bin/activate
python3 -m unittest discover tests
```
