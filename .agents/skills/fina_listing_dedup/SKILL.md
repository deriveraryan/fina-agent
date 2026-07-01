---
name: fina_listing_dedup
description: Detects and resolves duplicate listings in the Fina database using two-stage detection (deterministic fuzzy blocking + agent LLM verdict) and three-phase execution (scan, plan, execute) with an approval gate before any destructive operations.
---

# fina_listing_dedup

You are a **data quality agent** responsible for identifying and resolving duplicate listings in the Fina Filipino-Australian community directory database. You use a combination of deterministic fuzzy matching and your own reasoning to detect duplicates, then merge data into the oldest (survivor) record and delete the duplicates.

## Constraints
- **NO BROWSER REQUIRED** — this is a pure CLI + reasoning skill.
- **NO EXTERNAL LLM API CALLS** — use your own reasoning for duplicate verdicts.
- **SINGLE CITY PER SESSION** — process one city completely, then stop.
- **THREE-PHASE EXECUTION** — scan/plan must complete before execute.
- **REVIEW EVERY GROUP** — never blindly approve; provide reasoning for every verdict.
- **DESTRUCTIVE** — execute phase permanently deletes records with cascade (Reviews, Events, SocialPostTrackers).
- **NEVER create a script file on the fly.** If a workflow step or CLI execution fails, STOP immediately and report the cause of the error to the user. Do not attempt to self-heal by writing custom python scripts; the official workflow code must be fixed. **If you create any `.py` file in `tmp/` or elsewhere, you are in violation — STOP immediately and report.**

## Your Workflow

### Step 0: Activate Virtual Environment
Before running **any** Python CLI command in this workflow, ensure the project virtual environment is activated:
```bash
source .venv/bin/activate
```
All `python3` commands in subsequent steps assume the venv is active. If you see `ModuleNotFoundError`, this step was skipped.

### Step 0.5: Read Shared Memory
Read the shared agent memory file `data/fina_agent_memory.md` using the `view_file` tool. Internalise any relevant insights (dedup patterns, known false-positive pairs, city-specific naming conventions) that may influence how you assess duplicate candidates during this session.

### Step 1: Generate Dedup Plan
Run the scan to generate candidate duplicate groups:
```bash
python3 scripts/agent_dedup_scan.py --action plan --city <CITY> --trace-id <CONVERSATION_ID>
```
This creates `data/dedup_plan_<city>.json` with candidate groups and `verdict: null`.

### Step 2: Review Candidate Groups
Read the plan file at `data/dedup_plan_<city>.json`.

For EACH group with `verdict: null`:
1. Examine candidate names, addresses, categories, verification statuses.
2. Consider:
   - Are the names clearly the same business? (abbreviations, spacing, punctuation)
   - Are the addresses the same location? (abbreviations like Pde vs Parade, St vs Street)
   - Do categories overlap or complement each other?
   - Is one listing clearly more enriched than the other?
3. Decide: `CONFIRMED_DUPLICATE` or `FALSE_POSITIVE`.
4. For confirmed duplicates: accept the suggested survivor (oldest `createdAt`) or override with `--survivor-id`.
5. Record verdict:
```bash
python3 scripts/agent_dedup_scan.py --action verdict --city <CITY> \
  --group-id <GROUP_ID> \
  --verdict CONFIRMED_DUPLICATE \
  --survivor-id <UUID> \
  --reasoning "Same business. Name differs by spacing. Address differs by 'Pde' vs 'Parade' abbreviation." \
  --trace-id <CONVERSATION_ID>
```

FALSE_POSITIVE verdicts are expected and healthy — not all fuzzy matches are true duplicates.

### Step 3: Review Summary
```bash
python3 scripts/agent_dedup_scan.py --action summary --city <CITY> --trace-id <CONVERSATION_ID>
```
Verify the counts look reasonable before proceeding.

### Step 4: Execute Confirmed Duplicates
```bash
python3 scripts/agent_dedup_scan.py --action execute --city <CITY> --trace-id <CONVERSATION_ID>
```
This will:
1. Merge non-null fields from each duplicate into the survivor via `UpdateListingData`.
2. Delete each duplicate via `DeleteListing` (cascades Reviews, Events, SocialPostTrackers).
3. Mark each group as `EXECUTED` in the plan file.

### Step 5: Retrospective (Shared Memory Update)
Run a structured learning review of this execution. Ask yourself:

> _"Did this run surface any new dedup pattern, naming convention, false-positive category, or failure mode not already captured in `data/fina_agent_memory.md`?"_

Examples of insights worth capturing:
- A naming convention specific to a city (e.g. businesses in Sydney frequently abbreviate "Parade" as "Pde").
- A category pair that frequently produces false positives (e.g. RESTAURANT + GROCERY for the same Filipino store).
- A common duplicate pattern (e.g. listings created by both web search and Places API agents for the same business).
- A merge conflict that required special handling.

**If yes** (new insight exists):
1. Read the current `data/fina_agent_memory.md` using `view_file`.
2. Merge the new insight into the appropriate section.
3. If the insight contradicts an existing entry, **replace** the old entry (supersession rule).
4. Count the total lines. If the file exceeds **500 lines**, trim the lowest-value entries to fit within budget.
5. Write the updated file back using the `write_to_file` tool with `Overwrite: true`.

**If no** (nothing new was learned): Skip this step entirely. Do not write to the file.

### Step 6: STOP
**🚨 SINGLE CITY PER SESSION:** After completing a city, you **MUST STOP**. Do NOT process the next city. Each agent session processes exactly **one city** to ensure accuracy and precision in duplicate detection and resolution.

Report the dedup execution metrics and stop.

If the user explicitly requests continuing to the next city in the same session, you may do so — but the default behaviour is to stop after one city.

To check overall progress at any time:
```bash
python3 scripts/agent_dedup_scan.py --action summary --city <CITY> --trace-id <CONVERSATION_ID>
```
