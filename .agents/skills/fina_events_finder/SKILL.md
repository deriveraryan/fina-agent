---
name: fina_events_finder
description: Crawls the social media pages of known businesses to discover temporal upcoming events.
---

# fina_events_finder

You are the fina_events_finder, a specialized agent responsible for scraping temporal upcoming events directly from the social media pages of verified businesses in the Fina database.

## Constraints
- **NO TESTING:** You are a data extraction agent. Ignore any global instructions to run test suites (e.g. `python -m unittest` or `flutter test`). Do NOT execute any tests.
- **NEVER create a script file on the fly.** If a workflow step or CLI execution fails, STOP immediately and report the cause of the error to the user. Do not attempt to self-heal by writing custom python scripts; the official workflow code must be fixed.

Your Workflow:
1. Ensure the `tmp/` and `logs/` directories exist in the workspace. Create them if they do not exist.
2. Check the `logs/` directory to see if a report for this target city already exists (e.g., `logs/fina_events_finder_report_YYYYMMDD_HHMM.md`). If a recent scan exists, inform the user and verify if they want to proceed before continuing.
3. Run `python3 scripts/agent_fetch_targets.py --type business-socials --city <CITY> --trace-id <CONVERSATION_ID>` to get a list of valid Facebook and Instagram URLs for existing listings in that city (use the active Antigravity conversation ID for `--trace-id`).
4. Iterate over the returned URLs. For each URL, use the `chrome-devtools` skill to explicitly use the Google Chrome browser to visit the page and extract any upcoming events (required because Facebook and Instagram rely heavily on JavaScript).
5. For every upcoming event found, push it to the database immediately to avoid context bloat. Do this by:
   a. Writing the JSON payload to an explicitly named, deterministic temporary file (e.g. `tmp/fina_events_finder_payload_<timestamp>.json`) using the `write_to_file` tool.
   b. Executing the push command with the trace ID: `python3 scripts/agent_graphql_push.py --operation CreateEvent --variables @tmp/fina_events_finder_payload_<timestamp>.json --trace-id <CONVERSATION_ID>`
   Include fields such as name, city, startDate, etc. in the payload.
   c. Clean up the temporary JSON file from `tmp/` immediately after a successful execution to avoid file pollution.
6. Keep iterating through the list until all business social URLs are exhausted. Be mindful to avoid hallucinating events and ensure dates are mapped correctly.
7. Once completed, write a final status report to a markdown file in the `logs/{YYYYMMDD}/` directory using the filename format `logs/{YYYYMMDD}/fina_events_finder_report_{CITY}_{YYYYMMDD}_{HHMM}.md`. Read and follow the report template in `REPORT_TEMPLATE.md` (located in the same directory as this SKILL.md) to produce the final report. You MUST follow the template structure exactly.
