# Fina Agent — Data Extraction Scraper Pipeline

This repository houses the data discovery, verification, enrichment, and scraping agents for the Fina platform (the Filipino-Australian community directory). It consists of specialized Antigravity IDE subagents that scrape data from Google Maps (New) and social media (Facebook/Instagram), verify authenticity, and push results securely via a GraphQL client directly into the live Fina Postgres database.

---

## 🏛️ Repository Overview

This project is decoupled from the main Fina application backend. It runs lightweight Python scripts locally inside the Antigravity IDE:
* **Google Maps Scraper**: Scrapes candidate businesses matching category & city.
* **Social Web Searcher**: Discovers missing social media handles for listings.
* **Browser Event Crawler**: Crawls business pages to harvest upcoming temporal events.
* **Community Discoverer**: Crawls Facebook and Instagram for online groups and communities.

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

* **`fina_places_finder`**: Queries Google Places Text Search.
* **`fina_socials_finder`**: Enriches existing listings with missing Facebook/Instagram URLs.
* **`fina_events_finder`**: Crawls business social media pages to harvest upcoming events.
* **`fina_community_finder`**: Searches social platforms for Filipino community pages.

For a detailed flow diagram of how these agents operate, see the [Native IDE Agent Architecture Guide](docs/guides/ide_agent_architecture.md).

### 2. Running Scans via Chat Prompts
You can trigger a manual scan by asking the Antigravity agent directly in the chat:
*   *Places Discovery*:
    > "Use the `fina_places_finder` skill to scan Google Places in <CITY> for <CATEGORY>." (e.g., replacement: `DARWIN`, `RESTAURANT`).
    >
    > **To scan all categories and cities at once:**
    > "Use the `fina_places_finder` skill to scan Google Places for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`) across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Missing Socials Finder*:
    > "Use the `fina_socials_finder` skill to back-fill missing social URLs in SYDNEY."
    >
    > **To scan all categories and cities at once:**
    > "Use the `fina_socials_finder` skill to back-fill missing social URLs for all listing categories across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Events Finder*:
    > "Use the `fina_events_finder` skill to discover events in MELBOURNE."
    >
    > **To scan all categories and cities at once:**
    > "Use the `fina_events_finder` skill to discover events for all listing categories across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."
*   *Community Scanning*:
    > "Use the `fina_community_finder` skill to search Facebook and Instagram for community listings in SYDNEY."
    >
    > **To scan all categories and cities at once:**
    > "Use the `fina_community_finder` skill to search Facebook and Instagram for all categories (`RESTAURANT`, `CAFE`, `SHOP`, `CHURCH`, `COMMUNITY`, `GOVERNMENT`) across all major Australian cities (`SYDNEY`, `MELBOURNE`, `BRISBANE`, `PERTH`, `ADELAIDE`, `DARWIN`, `HOBART`, `CANBERRA`, `GOLD COAST`)."

### 3. Scheduling Automatic Scans
You can schedule the agents to run periodic background scans using the `/schedule` slash command:
*   *Places Scan Schedule*:
    ```bash
    /schedule CronExpression="0 12 * * *" Prompt="Use the fina_places_finder skill to scan Google Places for restaurants in all cities."
    ```
*   *Community Scan Schedule*:
    ```bash
    /schedule CronExpression="0 0 * * *" Prompt="Use the fina_community_finder skill to scan for events and listings across all cities."
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
