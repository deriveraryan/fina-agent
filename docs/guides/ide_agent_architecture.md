# Fina Native IDE Agent Architecture & Runbook

This reference document provides a comprehensive overview of the design, logic, and operational execution flow of the Fina Native IDE Agent pipeline. It details how the `fina_listing_map_search`, `fina_listing_web_search`, `fina_enrich_listing_socials_finder`, `fina_listing_embedder`, `fina_events_finder`, and `fina_docs_reviewer` subagents interact with the Google Places API and the Firebase SQL Connect database (hosted in the core `fina` repository) to automate discovery tasks without paid Gemini API keys.

---

## 📌 Orchestration Flow

Below is the high-level execution sequence of the native IDE agent workflow. The architecture leverages the Antigravity IDE's native subagents for data discovery, verification, enrichment, and pagination across 6 distinct, isolated pipelines.

```mermaid
flowchart TD
    %% ─── SCHEDULE OR MANUAL INVOCATION ───
    Start(["Trigger: Manual /schedule or Direct Prompt"]) --> SelectSubagent{"Which Agent Flow?"}
    
    SelectSubagent -->|Listing Map Search| InvokeListingMapSearch["IDE Invokes fina_listing_map_search Subagent"]
    SelectSubagent -->|Listing Web Search| InvokeListingWebSearch["IDE Invokes fina_listing_web_search Subagent"]
    SelectSubagent -->|Enrich Listing Socials Finder| InvokeEnrichListingSocialsFinder["IDE Invokes fina_enrich_listing_socials_finder Subagent"]
    SelectSubagent -->|Listing Embedder| InvokeListingEmbedder["IDE Invokes fina_listing_embedder Subagent"]
    SelectSubagent -->|Events Finder| InvokeEventsFinder["IDE Invokes fina_events_finder Subagent"]
    SelectSubagent -->|Docs Reviewer| InvokeDocsReviewer["IDE Invokes fina_docs_reviewer Subagent"]

    %% ════════ 1. MAPS SEARCH FLOW (TASK-BASED) ════════
    InvokeListingMapSearch --> GenerateMapTasks["Execute: python3 scripts/agent_maps_search_tasks.py<br>--action generate --city C (idempotent)"]
    GenerateMapTasks --> GetNextMapTask["Execute: python3 scripts/agent_maps_search_tasks.py<br>--action next --city C"]
    GetNextMapTask --> FetchCityListingsMaps["Execute: python3 scripts/agent_fetch_targets.py --type city-listings<br>--city C > tmp/existing_city_listings.json"]
    FetchCityListingsMaps --> ExecMapsFetch["Execute: python3 scripts/agent_maps_fetch.py<br>--query QUERY --city C --category CAT"]
    ExecMapsFetch --> CheckDuplicateMaps["Check duplicate via agent_check_duplicate.py"]
    CheckDuplicateMaps --> VerifyHeuristic["Subagent evaluates candidate internally<br>(using name & description details)"]

    VerifyHeuristic -->|Filipino Affiliated| ExecPushDataMaps["Execute: python3 scripts/agent_graphql_push.py<br>--operation CreateListing"]
    subgraph agent_graphql_push_maps["Inside scripts/agent_graphql_push.py"]
        SyncGeocodeDedupMaps["Sync Geocode & Deduplicate"]
        GQLMutationMaps["GraphQL Mutation<br>(CreateListing or UpdateListing)"]
    end
    ExecPushDataMaps --> SyncGeocodeDedupMaps
    SyncGeocodeDedupMaps --> GQLMutationMaps
    GQLMutationMaps --> DBTransactionMaps[("PostgreSQL Database")]

    DBTransactionMaps --> CheckHasMore
    VerifyHeuristic -->|Not Affiliated| CheckHasMore

    CheckHasMore{"More Candidates from API?"}
    CheckHasMore -->|Yes| CheckDuplicateMaps
    CheckHasMore -->|No| CompleteMapTask["Execute: python3 scripts/agent_maps_search_tasks.py<br>--action complete --task-id ID"]
    CompleteMapTask --> FinishMaps(["Task Completed — Next run picks up next task"])

    %% ════════ 2. LISTING WEB SEARCH FLOW (TASK-BASED) ════════
    InvokeListingWebSearch --> GenerateTasks["Execute: python3 scripts/agent_web_search_tasks.py<br>--action generate --city C (idempotent)"]
    GenerateTasks --> GetNextTask["Execute: python3 scripts/agent_web_search_tasks.py<br>--action next --city C"]
    GetNextTask --> FetchCityListings["Execute: python3 scripts/agent_fetch_targets.py --type city-listings<br>--city C > tmp/existing_city_listings.json"]
    FetchCityListings --> NativeWebSearch["Subagent uses Native Web Search<br>(4 rounds: Facebook, Instagram, General Web, Google Maps)<br>using task's formatted_query"]
    NativeWebSearch --> FilterKnown["Filters out existing URLs/Names by<br>inspecting tmp/existing_city_listings.json on disk"]
    
    FilterKnown --> BrowserVerify["For each NEW candidate URL:<br>Subagent uses chrome-devtools to inspect page<br>(visible text/selectors only)"]
    BrowserVerify -->|Verified Filipino| ExecPushListing["Execute: python3 scripts/agent_graphql_push.py<br>--operation CreateListing"]
    subgraph agent_graphql_push_listing["Inside scripts/agent_graphql_push.py"]
        SyncGeocodeDedupListing["Sync Geocode & Deduplicate"]
        GQLMutationListing["GraphQL Mutation<br>(CreateListing or UpdateListing)"]
    end
    ExecPushListing --> SyncGeocodeDedupListing
    SyncGeocodeDedupListing --> GQLMutationListing
    GQLMutationListing --> DBTransactionListing[("PostgreSQL Database")]
    
    DBTransactionListing --> CheckHasMoreSocial
    BrowserVerify -->|Not Affiliated| CheckHasMoreSocial
    
    CheckHasMoreSocial{"Found 30 new listings<br>OR finished all rounds?"}
    CheckHasMoreSocial -->|Yes| NativeWebSearch
    CheckHasMoreSocial -->|Yes| CompleteTask["Execute: python3 scripts/agent_web_search_tasks.py<br>--action complete --task-id ID"]
    CompleteTask --> FinishSocial(["Task Completed — Next run picks up next task"])

    %% ════════ 3. ENRICH LISTING SOCIALS FINDER FLOW (BACKFILL) ════════
    InvokeEnrichListingSocialsFinder --> ExecGetMissingSocial["Execute: python3 scripts/agent_fetch_targets.py --type missing-social<br>--city C > tmp/missing_socials_targets.json"]
    
    subgraph agent_fetch_missing_social["Inside scripts/agent_fetch_targets.py"]
        DBQueryMissingSocial[("PostgreSQL Database<br>(ListListingsMissingSocial)")]
        ReturnMissingSocial["Writes JSON list of Listings missing URLs<br>to tmp/missing_socials_targets.json"]
    end
    
    ExecGetMissingSocial --> DBQueryMissingSocial
    DBQueryMissingSocial -.-> ReturnMissingSocial
    
    ReturnMissingSocial --> ReadTargets["Read target list from tmp/missing_socials_targets.json"]
    ReadTargets --> EnrichLoop{"For each Listing"}
    EnrichLoop --> SearchWeb["Subagent uses web search<br>Finds official Facebook/Instagram"]
    SearchWeb --> VerifySocial["Verifies pages match business<br>(inspects visible text/selectors only)"]
    
    VerifySocial --> ExecUpdateSocial["Execute: python3 scripts/agent_graphql_push.py<br>--operation UpdateListingSocialUrls"]
    subgraph agent_graphql_push_update["Inside scripts/agent_graphql_push.py"]
        GQLMutationUpdate["GraphQL Mutation<br>(UpdateListingSocialUrls)"]
    end
    
    ExecUpdateSocial --> GQLMutationUpdate
    GQLMutationUpdate --> DBTransactionUpdate[("PostgreSQL Database")]
    DBTransactionUpdate --> EnrichLoop
    
    EnrichLoop -.->|No more listings| FinishEnrich(["Socials Enrichment Completed"])

    %% ════════ 4. LISTING EMBEDDER FLOW (VECTOR BACKFILL) ════════
    InvokeListingEmbedder --> ExecEmbeddings["Execute: python3 scripts/agent_generate_embeddings.py<br>--city C --trace-id TID --limit L > tmp/fina_listing_embedder_run.json"]

    subgraph agent_generate_embeddings["Inside scripts/agent_generate_embeddings.py"]
        QueryMissing[("PostgreSQL Database<br>(ListListingsMissingEmbedding)")]
        GenVector["Generate 768-dim vector<br>via Google GenAI"]
        PushVector["GraphQL Mutation<br>(UpdateListingData)"]
    end

    ExecEmbeddings --> QueryMissing
    QueryMissing -.-> GenVector
    GenVector --> PushVector
    PushVector --> DBTransactionEmbed[("PostgreSQL Database")]
    DBTransactionEmbed --> FinishEmbed(["Embedding Backfill Completed"])

    %% ════════ 5. EVENTS FINDER FLOW (BUSINESS PAGES) ════════
    InvokeEventsFinder --> ExecGetBusinessSocial["Execute: python3 scripts/agent_fetch_targets.py<br>--type business-socials --city C"]
    
    subgraph agent_fetch_business_social["Inside scripts/agent_fetch_targets.py"]
        DBQueryBusinessSocial[("PostgreSQL Database<br>(ListAdminListings)")]
        ReturnBusinessSocial["Returns JSON list of Business Social URLs"]
    end
    
    ExecGetBusinessSocial --> DBQueryBusinessSocial
    DBQueryBusinessSocial -.-> ReturnBusinessSocial
    
    ReturnBusinessSocial --> HarvestLoop{"For each URL"}
    HarvestLoop --> IdentifyPlatform["Identify Platform & Query Tracker:<br>python3 scripts/agent_fetch_targets.py --type social-post-tracker"]
    IdentifyPlatform --> GetTrackerGQL["GraphQL Query:<br>GetSocialPostTracker"]
    GetTrackerGQL --> DBQueryTracker[("PostgreSQL Database")]
    DBQueryTracker -.-> ReturnTracker["Return lastPostDate"]
    
    ReturnTracker --> ReadBrowserHarvest["Subagent uses IDE Native Browser Tools<br>(visit, scroll)"]
    ReadBrowserHarvest --> ScanLoop{"Scan posts (max 10)<br>Stop if post date <= lastPostDate"}
    ScanLoop --> ExtractEventData["Extract events & follower count"]
    
    ExtractEventData --> ExecPushEvent["Execute: python3 scripts/agent_graphql_push.py<br>--operation CreateEvent"]
    ExtractEventData --> ExecPushFollowers["Execute: python3 scripts/agent_graphql_push.py<br>--operation UpdateListingSocialUrls"]
    ExtractEventData --> ExecPushTracker["Execute: python3 scripts/agent_graphql_push.py<br>--operation UpsertSocialPostTracker"]
    
    subgraph agent_graphql_push_event["Inside scripts/agent_graphql_push.py"]
        GQLMutationEvent["GraphQL Mutation<br>(CreateEvent)"]
        GQLMutationFollowers["GraphQL Mutation<br>(UpdateListingSocialUrls)"]
        GQLMutationTracker["GraphQL Mutation<br>(UpsertSocialPostTracker)"]
    end
    
    ExecPushEvent --> GQLMutationEvent
    ExecPushFollowers --> GQLMutationFollowers
    ExecPushTracker --> GQLMutationTracker
    
    GQLMutationEvent & GQLMutationFollowers & GQLMutationTracker --> DBTransactionEvent[("PostgreSQL Database")]
    DBTransactionEvent --> HarvestLoop
    
    HarvestLoop -.->|No more URLs| FinishHarvest(["Events Discovery Completed"])

    %% ════════ 6. DOCUMENTATION REVIEWER FLOW (DOCS AUDIT) ════════
    InvokeDocsReviewer --> VerifyDocs["Subagent audits documentation against codebase"]
    VerifyDocs -->|Discrepancies Found| UpdateDocs["Update Markdown Files"]
    VerifyDocs -->|Report Generation| WriteDocReport["Write report to logs/"]
    UpdateDocs & WriteDocReport --> FinishDocs(["Docs Audit Completed"])
```

---

## 🛠️ Essential Components & Mechanics

### 1. The `fina_listing_map_search` Subagent (Places Discovery)
This subagent automates business research on Google Maps using a task-based state machine:
*   **Task-Based Execution**: Each run is scoped to a single task (1 city × 1 category × 1 search template). Tasks are managed via `scripts/agent_maps_search_tasks.py`, which generates all (category × template) permutations at city-level only by default (`data/listing_map_search_tasks_{city}.json`). Pass `--include-suburbs` to add suburb-level tasks.
*   **Category Validation**: To ensure alignment with [categories.json](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/data/categories.json), the subagent reads the canonical category rules at startup.
*   **Single Google Places API Call**: Each task triggers a single call to `scripts/agent_maps_fetch.py --query "<formatted_query>" --city C --category CAT --trace-id <CONVERSATION_ID>`, which executes one Google Places (New) Text Search request and returns formatted candidates to stdout.
*   **Deduplication**: Before evaluating candidates, the agent fetches existing city listings to `tmp/existing_city_listings.json` and checks each candidate via `agent_check_duplicate.py`.
*   **Omission of Embeddings Flag**: Does NOT use the `--generate-embeddings` flag when pushing listings via the GraphQL client. Listing description vector embeddings are backfilled asynchronously by the dedicated `fina_listing_embedder` agent.

### 2. The `fina_listing_web_search` Subagent (Community Scanner)
This subagent actively searches Facebook, Instagram, TikTok, general web platforms, and Google Maps for Filipino listings using a deterministic task-based state machine:
*   **Task-Based Execution**: Each run is scoped to a single task (1 location × 1 category × 1 search template) with a limit of 30 new listings. Tasks are managed via `scripts/agent_web_search_tasks.py`, which generates all permutations for a city (`data/listing_web_search_tasks_{city}.json`) and provides `next`/`complete` actions for state transitions (PENDING → IN_PROGRESS → COMPLETED). Categories with `"cityOnly": true` in `data/categories.json` (e.g. `GOVERNMENT`) produce only city-level tasks, skipping suburb permutations. By default, generation skips if the file already exists; pass `--force` to regenerate while merging existing task state (status, metrics) into the new file via atomic replacement. Stale `IN_PROGRESS` tasks (exceeding `--stale-timeout-minutes`, default 60) are automatically reclaimed to `PENDING` during `--action next`.
*   **Context Setup (No-Bloat)**: Executes `scripts/agent_fetch_targets.py --type city-listings --city C > tmp/existing_city_listings.json` to write the deduplication context directly to disk. The agent checks if a candidate exists by searching the file directly on disk, avoiding terminal stdout dumps.
*   **Web Discovery**: Uses the task's pre-formatted search query to run four sequential search rounds (Facebook, Instagram, General Web, and Google Maps browser). Each task's query is pre-generated from the `searchTemplates` in `data/categories.json` combined with the location (city or suburb from `data/top_suburbs_per_city.json`).
*   **Browser Verification (No-Bloat)**: The subagent uses the `chrome-devtools` skill to inspect candidate pages, extracting only visible text or target DOM selectors (such as the follower count element or the bio description), rather than loading full raw page HTML into prompt history.
*   **Category Standardization**: The subagent is instructed to view [categories.json](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/data/categories.json) to ensure extracted categories map precisely to canonical definitions before pushing.
*   **Google Maps Enrichment**: Navigates to Google Maps via Chrome DevTools to enrich verified candidates with latitude/longitude (parsed from URL bar), address, opening hours, phone, Place ID, and website — filling only empty fields. Adds a `google-maps` tag when enrichment succeeds. Proceeds to push regardless of Maps enrichment outcome.
*   **Listing Persistence**: Verified organizations are pushed directly to the `Listing` table using `CreateListing`. For online-only communities (no physical street address), the address is set to the city name with city center coordinates and tagged with `online-org`.
*   **Omission of Embeddings Flag**: Does NOT use the `--generate-embeddings` flag when pushing listings via the GraphQL client. Listing description vector embeddings are backfilled asynchronously by the dedicated `fina_listing_embedder` agent.

### 3. The `fina_enrich_listing_socials_finder` Subagent (Missing Socials Finder)
This subagent focuses purely on completing existing directory entries:
*   **Single City Target Restriction**: Mandates the `--city <CITY>` parameter during target collection to enforce a single-city focus and prevent context bloat.
*   **Targeting (No-Bloat)**: Executes `agent_fetch_targets.py --type missing-social --city C > tmp/missing_socials_targets.json` to write targets to disk. The agent reads and inspects the JSON file on disk, avoiding terminal stdout dumps.
*   **Web Search**: Uses LLM-driven web search tools (with site-specific filtering) to find the business's official social media pages.
*   **Browser Verification (No-Bloat)**: Uses Chrome DevTools to verify pages, extracting only visible text or target selectors (follower count containers or bio description), rather than loading full raw page HTML into context. Updates are pushed via the `UpdateListingSocialUrls` mutation.

### 4. The `fina_listing_embedder` Subagent (Listing Vector Embedder)
This subagent audits listing records and fills in missing vector embeddings to support semantic search functionality:
*   **Targeting (No-Bloat)**: Executes `python3 scripts/agent_generate_embeddings.py --city C --trace-id <CONVERSATION_ID> > tmp/fina_listing_embedder_run.json` to process listings missing description embeddings.
*   **Vector Generation**: Constructs a composite text string from listing fields and generates a 768-dimension vector using the local Google GenAI client.
*   **Rate-Limit Controls**: Sleeps for 0.2s between updates to stay within API thresholds.
*   **Persistence**: Overwrites/saves vectors in the database using the `UpdateListingData` mutation.
*   **Run Report Consolidation**: Outputs a summary report as JSON to stdout, typically redirected to `tmp/fina_listing_embedder_run.json`.

### 5. The `fina_events_finder` Subagent (Listing's Events Discoverer)
This subagent directly crawls the social pages of verified businesses to discover upcoming temporal events, checking for new posts since the last scan date.
*   **Targeting (No-Bloat)**: Executes `agent_fetch_targets.py --type business-socials --city C --trace-id <CONVERSATION_ID> > tmp/business_socials_targets.json` to write target listing social URLs to disk, avoiding stdout dumps.
*   **Bookmark Tracking**: Queries the database via `agent_fetch_targets.py --type social-post-tracker --listing-id L --platform P --trace-id <CONVERSATION_ID>` to retrieve the `lastPostDate` bookmark.
*   **Web Browsing & Scanning Limit (No-Bloat)**: Uses Chrome DevTools to visit the social account page, extracting only visible text or selectors rather than outerHTML. It scans posts starting from the most recent, stopping when:
    1. A post's publish date is older than or equal to the retrieved `lastPostDate` bookmark.
    2. OR it has evaluated exactly 10 posts on the page.
*   **Relative Date Parsing**: Resolves relative post timestamps (e.g. "3 hours ago", "Yesterday at 4 PM", "2 days ago") into absolute UTC ISO 8601 strings based on current local system metadata, and resolves event dates relative to the post publication date.
*   **Follower count parsing**: Capture page follower counts and parse them strictly to integers, resolving suffix modifiers like "K" (thousands) and "M" (millions) and mapping missing values to `null`.
*   **Heuristic Event Classification**: Filters out daily menu items, past events, product ads, and generic promotions, extracting only distinct future community happenings.
*   **GraphQL Updates & Self-Correction**: Pushes discovered events (`CreateEvent`), follower counts (`UpdateListingSocialUrls`), and updated bookmarks (`UpsertSocialPostTracker`) using mutations with validation self-correction on exit code 1.


### 6. The `fina_docs_reviewer` Subagent (Documentation Reviewer)
This subagent audits repository documentation against actual Python script definitions:
*   **CLI Verification**: Reviews CLI usages, options, and parameters in documentation against source arguments (e.g. confirming no outdated parameters like `--dry-run` are passed directly to script commands).
*   **Agent Flow Auditing**: Verifies that new agent skills, registries, and architecture diagrams match active implementations.
*   **Audit Report Generation**: Saves documentation reviews and gap logs in markdown report files under the `logs/` directory.

### 7. Database Integration Scripts
To maintain security and ensure all data mutations pass through the authorized GraphQL layer, the subagents rely on local Python helper CLI scripts that connect to the core `fina` Firebase project:
*   `scripts/agent_fetch_targets.py`: Fetches target source URLs, missing-social listings, business-socials, city-listings (for deduplication context), or social-post-trackers (for checking previous event scraper bookmarks) from the database.
*   `scripts/agent_graphql_push.py`: Pushes verified JSON objects or updates to the backend using GraphQL operations (including `CreateListing`, `UpdateListingSocialUrls`, `CreateEvent`, and `UpsertSocialPostTracker`). It normalizes platform names, dynamically validates and normalizes categories against [categories.json](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/data/categories.json) (enforcing case-insensitive uppercase normalization and throwing a fatal exit code 1 if invalid), caches loaded categories in module scope to prevent redundant disk reads, and synchronously handles geocoding and deduplication before creating new listings.
*   `scripts/agent_maps_fetch.py`: Executes a single Google Places (New) Text Search API call for a pre-formatted query and returns formatted candidate places as JSON.
*   `scripts/agent_generate_embeddings.py`: Queries listings missing vector embeddings, generates 768-dimension vectors, and updates them via the GraphQL push client.
*   `scripts/agent_check_duplicate.py`: Checks a local JSON file of existing listings for duplicate candidates by name and/or social URL match. Used by `fina_listing_map_search` and `fina_listing_web_search` before pushing new listings.
*   `scripts/agent_web_search_tasks.py`: Manages the deterministic task-based state machine for `fina_listing_web_search`, supporting `generate`, `next`, `complete`, and `summary` actions for web search task lifecycle management.
*   `scripts/agent_maps_search_tasks.py`: Manages the deterministic task-based state machine for `fina_listing_map_search`, supporting `generate`, `next`, `complete`, and `summary` actions for maps search task lifecycle management. Generates city-level tasks by default; pass `--include-suburbs` for suburb-level permutations.
*   `scripts/migrate_embeddings.py`: One-time migration utility for backfilling vector embeddings across all or a specific city.
*   `scripts/migrate_template_descriptions.py`: One-time migration utility to clear legacy template fallback descriptions from existing listings.
*   `scripts/agent_backup_and_reset.py`: Backs up Listing, Review, and Event data to local JSON files, then clears the database tables for a clean reset.

### 8. Synchronous Geocoding & Deduplication
To simplify the architecture and reduce cloud function dependencies, heavy transactional logic is handled synchronously by `agent_graphql_push.py` before inserting data into the database:
*   **Geocoding**: Uses the Google Maps Geocoding API to resolve coordinates if missing prior to insertion.
*   **Deduplication**: Resolves matches using name normalization, `pgvector` semantic embedding similarity, and Jaccard word-overlap coefficient (>0.7). If a duplicate is found, it merges missing fields via `UpdateListingData` and `UpdateListingStatus` mutations instead of creating a new duplicate record.

---

## 🧠 Shared Agent Memory

### Overview

The Fina agent pipeline uses a shared, self-evolving memory system that enables agents to learn from their executions and share operational knowledge across sessions. This addresses the fundamental limitation of stateless agent invocations: without persistent memory, agents repeat the same mistakes, rediscover the same patterns, and waste tokens re-learning platform behaviours.

The memory is stored in a single markdown file — [`data/fina_agent_memory.md`](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/data/fina_agent_memory.md) — that agents read at session start and conditionally update at session end.

### Design Philosophy

The framework is built on five core principles, each drawn from research into leading agent memory architectures:

| Principle | Origin | Implementation |
|---|---|---|
| **Bounded curation** | [Hermes](https://arxiv.org/abs/2310.00710) (~800 token active memory) | 200-line hard budget forces agents to prioritise quality over quantity |
| **Post-execution reflection** | [OpenClaw](https://arxiv.org/abs/2401.13178) (dreaming pipeline) | Structured retrospective step after every task completion |
| **Self-managing memory** | [MemGPT/Letta](https://arxiv.org/abs/2310.08560) (agents edit their own memory) | Agents read, merge, prune, and write back the memory file autonomously |
| **Quality-gated learning** | [Reflexion](https://arxiv.org/abs/2303.11366) (execute → reflect → crystallise) | Explicit "did I learn anything new?" gate prevents noise accumulation |
| **Semantic taxonomy** | [CoALA](https://arxiv.org/abs/2309.02427) (memory type classification) | Five named sections map to distinct knowledge domains |

**What was deliberately not adopted:**
- **OpenClaw's daily log rotation** — Fina agents run as single-task sessions, not daemons
- **MemGPT's multi-tier storage** — Overkill for a single markdown file with 200-line budget
- **Hermes' skill crystallisation** — Agent skills are manually curated SKILL.md files, not auto-generated
- **Vector-indexed episodic memory** — The 200-line cap makes full-text reading cheaper than semantic retrieval

### Architecture

```mermaid
flowchart LR
    subgraph SessionStart["Session Start"]
        ReadMem["Step 0.7: Read Memory<br>view_file data/fina_agent_memory.md"]
    end

    subgraph TaskExecution["Task Execution"]
        Execute["Steps 1-7: Core Workflow<br>(discovery, enrichment, etc.)"]
    end

    subgraph SessionEnd["Session End"]
        Retro{"Step 7.5: Retrospective<br>Did I learn anything new?"}
        Retro -->|Yes| Merge["Read → Merge → Prune → Write"]
        Retro -->|No| Skip["Skip update entirely"]
    end

    ReadMem --> Execute --> Retro
    Merge --> MemFile["data/fina_agent_memory.md"]
    MemFile -.->|Next session| ReadMem
```

The memory protocol integrates into the agent lifecycle as two lightweight steps that bookend the core workflow:

1. **Read Phase (Step 0.7)** — After environment setup but before task execution, the agent reads the memory file and internalises relevant insights for the upcoming task.
2. **Retrospective Phase (Step 7.5)** — After task completion but before stopping, the agent evaluates whether the execution surfaced genuinely new operational knowledge.

### File Schema

The memory file has a fixed five-section structure, each serving a distinct knowledge domain:

```markdown
# Fina Agent Memory

> Self-evolving shared memory for Fina discovery and enrichment agents.
> Maximum budget: **200 lines**.
> Supersession rule: new insights replace contradictory old entries.
> Format: concise bullet points (one line per insight). No prose paragraphs.

## Platform & Browser Insights
<!-- Anti-bot patterns, UI changes, rate limits, login walls -->

## Discovery Patterns
<!-- Search techniques, template effectiveness, duplicate trends -->

## Enrichment Patterns
<!-- Review extraction, hours parsing, social media quirks -->

## City Intelligence
<!-- Suburb saturation, high-yield categories, city-specific observations -->

## Known Pitfalls
<!-- Validation errors, payload patterns, failure recovery -->
```

**Section responsibilities:**

| Section | Written by | Example entries |
|---|---|---|
| Platform & Browser Insights | Both agents | "Facebook requires login to view follower counts as of 2026-06" |
| Discovery Patterns | `fina_listing_web_search` | "RESTAURANT category in Sydney CBD yields >80% duplicates — consider skipping" |
| Enrichment Patterns | `fina_listing_enrichment` | "Google Maps reviews section now uses `div[data-review-id]` selector" |
| City Intelligence | Both agents | "Melbourne: Dandenong and Footscray are highest-density Filipino suburbs" |
| Known Pitfalls | Both agents | "`CreateListing` rejects `openingHours` with trailing whitespace in day names" |

### Budget Management

The memory file enforces a **200-line hard cap** (including headers, section headings, and blockquote rules). This constraint is deliberate:

- **Forces curation**: Agents must evaluate what's truly worth retaining versus what's transient noise.
- **Prevents context bloat**: At ~200 lines, the entire file fits comfortably within a single `view_file` call, keeping the read phase cheap.
- **Drives supersession**: When new insights contradict existing entries, agents replace the old entry rather than appending both.

**Pruning heuristics** (applied by agents when the file approaches the budget):

1. **Staleness**: Remove entries about platform behaviours that have since changed (superseded).
2. **Redundancy**: Merge entries that describe the same insight from different angles.
3. **Specificity**: Prefer specific, actionable entries over vague observations.
4. **Frequency**: Entries that apply to every execution are more valuable than edge cases.

### Entry Format

All entries must follow these formatting rules:

- **One bullet point per insight** — keeps entries atomic and individually pruneable.
- **No prose paragraphs** — agents write concise, scannable entries.
- **Include dates when relevant** — for time-sensitive platform behaviours (e.g., "as of 2026-06").
- **Include scope when relevant** — for city/category-specific patterns (e.g., "Sydney RESTAURANT").

### Concurrency Model

The current implementation uses a **last-writer-wins** strategy:

- Multiple concurrent agents may read the memory file simultaneously (no conflict).
- If two agents both decide to write at the same time, the last write overwrites the first.
- This is acceptable because:
  1. The quality gate means most executions skip the write entirely.
  2. When writes do occur, they're typically to different sections.
  3. Git history preserves any overwritten content for manual recovery.
  4. The cost of `fcntl` locking for a rarely-written markdown file exceeds the benefit.

**Known limitation**: In a theoretical worst case, two concurrent agents could both surface valuable insights, and the second writer could overwrite the first's contribution. The mitigation is that agents run as single-task sessions and the retrospective happens at session end, making true write contention rare.

### Participating Agents

The memory protocol is currently implemented for the 2 production-ready agents:

| Agent | Read Step | Retro Step | Typical insights |
|---|---|---|---|
| `fina_listing_web_search` | Step 0.7 | Step 7.5 | Search template effectiveness, platform rate limits, suburb saturation |
| `fina_listing_enrichment` | Step 0.7 | Step 7.5 | Maps UI selectors, review extraction techniques, hours parsing edge cases |

Planned agents (`fina_listing_map_search`, `fina_events_finder`, `fina_listing_embedder`) are not yet released but can be onboarded by adding the same Step 0.7/7.5 pattern to their SKILL.md files.

### Governing Rule

The memory protocol is enforced by **Rule 1.15: Shared Agent Memory Protocol** in [AGENTS.md](file:///Users/ryan/.gemini/antigravity/scratch/fina-agent/AGENTS.md), which establishes the read/retro lifecycle, budget invariant, supersession rule, and content invariant as architectural constraints.

### Version History & Recovery

The memory file is Git-tracked (it lives in `data/`), providing automatic version history. If an agent's write is destructive or incorrect:

```bash
# View memory file evolution
git log --oneline data/fina_agent_memory.md

# Recover a previous version
git show HEAD~1:data/fina_agent_memory.md
```

This makes Git the de-facto "episodic memory" layer — the live file is working memory, and Git history is long-term recall.

---

## 💻 Operational Runbook

For instructions on how to trigger or schedule the `fina_listing_map_search`, `fina_listing_web_search`, `fina_listing_enrichment`, `fina_listing_embedder`, `fina_events_finder`, and `fina_docs_reviewer` subagents, refer to the Operational Guide in the main repository `README.md`.
