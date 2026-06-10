# Fina Agent — Data Extraction Scraper Pipeline

This repository houses the data discovery, verification, enrichment, and scraping agents for the Fina platform (the Filipino-Australian community directory). It consists of specialized Antigravity IDE subagents that scrape data from Google Maps (New) and social media (Facebook/Instagram), verify authenticity, and push results securely via a GraphQL client directly into the live Fina Postgres database.

---

## 🏛️ Repository Overview

This project is decoupled from the main Fina application backend. It runs lightweight Python scripts locally inside the Antigravity IDE:
* **Google Maps Scraper**: Scrapes candidate businesses matching category & city.
* **Social Web Searcher**: Discovers missing social media handles for listings.
* **Browser Event Crawler**: Crawls business pages to harvest upcoming temporal events.
* **Community Discoverer**: Crawls Facebook and Instagram for online groups and communities.
* **Category Auditor**: Audits and recategorizes listing categories using canonical definitions and LLM validation.

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
ANTIGRAVITY_AGENT_ID="antigravity-preview-05-2026"
ANTIGRAVITY_ENVIRONMENT="remote"
```

---

## 🚀 Run & Use Guide

You can trigger these discovery scans manually through the Antigravity Chat UI or run the underlying scripts directly in your shell.

### 1. The Scraper Agents

* **`fina_refresh_listing_maps_finder`**: Queries Google Places Text Search.
* **`fina_new_listing_web_finder`**: Searches social platforms for Filipino community pages.
* **`fina_enrich_listing_socials_finder`**: Enriches existing listings with missing Facebook/Instagram URLs.
* **`fina_listing_auditor`**: Audits and corrects category classifications using canonical definitions and LLM validation.
* **`fina_events_finder`**: Crawls business social media pages to harvest upcoming events.
* **`fina_docs_reviewer`**: Audits repository documentation files for any gaps or discrepancies against the current codebase.

For a detailed flow diagram of how these agents operate, see the [Native IDE Agent Architecture Guide](docs/guides/ide_agent_architecture.md).

### 2. Running Scans via Chat Prompts
You can trigger a manual scan by asking the Antigravity agent directly in the chat. For large, multi-city scans, we highly recommend prefixing your prompt with the `/goal` slash command so the agent runs continuously in the background without stopping.

#### 💾 Caching & Bypassing Cache (`--refresh`)
By default, the `fina_refresh_listing_maps_finder` caches Google Places search results under `.antigravity_saves/` to minimize API costs and prevent prompt bloat. To force a live scan that bypasses the local cache, include terms like **"refresh"**, **"bypassing cache"**, or **"live scan"** in your prompt (which instructs the agent to run the underlying fetch script with the `--refresh` flag).

*   *Places Discovery*:
    > "Use the `fina_refresh_listing_maps_finder` skill to scan Google Places in <CITY> for <CATEGORY>." (e.g., replacement: `DARWIN`, `RESTAURANT`).
    >
    > **To scan a single city for all categories (using cache):**
    > "/goal Use the `fina_refresh_listing_maps_finder` skill to scan Google Places for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`, `SERVICES`) in SYDNEY."
    >
    > **To force a fresh live scan bypassing the local cache:**
    > "/goal Use the `fina_refresh_listing_maps_finder` skill to scan Google Places with **refresh** for RESTAURANT in SYDNEY."
    >
    > **To scan a single category across all cities:**
    > "/goal Use the `fina_refresh_listing_maps_finder` skill to scan Google Places for RESTAURANT across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
    >
    > **To scan all categories and cities at once:**
    > "/goal Use the `fina_refresh_listing_maps_finder` skill to scan Google Places for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`, `SERVICES`) across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Community Scanning*:
    > "Use the `fina_new_listing_web_finder` skill to search the web for community listings in SYDNEY."
    >
    > **To scan a single city for all categories:**
    > "/goal Use the `fina_new_listing_web_finder` skill to search the web for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`, `SERVICES`) in SYDNEY."
    >
    > **To scan a single category across all cities:**
    > "/goal Use the `fina_new_listing_web_finder` skill to search the web for RESTAURANT across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
    >
    > **To scan all categories and cities at once:**
    > "/goal Use the `fina_new_listing_web_finder` skill to search the web for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`, `SERVICES`) across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Missing Socials Finder*:
    > "Use the `fina_enrich_listing_socials_finder` skill to back-fill missing social URLs in SYDNEY."
    >
    > **To scan all cities at once:**
    > "/goal Use the `fina_enrich_listing_socials_finder` skill to back-fill missing social URLs across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Category Auditor*:
    > "Use the `fina_listing_auditor` skill to audit and correct categories in SYDNEY."
    >
    > **To run a dry-run audit without database writes:**
    > "Use the `fina_listing_auditor` skill in dry-run mode to audit categories in SYDNEY."
*   *Events Finder*:
    > "Use the `fina_events_finder` skill to discover events in MELBOURNE."
    >
    > **To scan all cities at once:**
    > "/goal Use the `fina_events_finder` skill to discover events across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Documentation Reviewer*:
    > "Use the `fina_docs_reviewer` skill to review the repository documentation for any gaps."

### 3. Running Scripts via CLI
You can execute the underlying discovery and database push scripts directly in your shell.

*   **Listing Category Auditor**:
    Note: The underlying Python CLI script only retrieves listing data. Category validation and dry-run/push choices are made at the agent workflow level.
    ```bash
    # Fetch listings for audit review
    python3 scripts/agent_audit_listings.py --city SYDNEY --limit 10 --offset 0 --trace-id <CONVERSATION_ID>
    ```
*   **Google Places Fetch (with `--refresh` to bypass local cache and query live API)**:
    ```bash
    python3 scripts/agent_maps_fetch.py --city SYDNEY --category RESTAURANT --limit 10 --offset 0 --refresh --trace-id <CONVERSATION_ID>
    ```
*   **Fetch Targets (e.g. retrieve social post tracker)**:
    ```bash
    # Retrieve scan bookmark for a listing on Facebook
    python3 scripts/agent_fetch_targets.py --type social-post-tracker --listing-id <LISTING_UUID> --platform facebook --trace-id <CONVERSATION_ID>
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
    /schedule CronExpression="0 12 * * *" Prompt="Use the fina_refresh_listing_maps_finder skill to scan Google Places for restaurants in all cities."
    ```
*   *Community Scan Schedule*:
    ```bash
    /schedule CronExpression="0 0 * * *" Prompt="Use the fina_new_listing_web_finder skill to scan for events and listings across all cities."
    ```
*   *Category Audit Schedule*:
    ```bash
    /schedule CronExpression="0 18 * * *" Prompt="Use the fina_listing_auditor skill to audit and correct categories in SYDNEY."
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
