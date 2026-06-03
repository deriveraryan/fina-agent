"""Three-tier memory structure and agent state persistence loop.

Implements standard state management following google.antigravity 2.0 specs.
Decouples native conversational history from schema-safe JSON and human-auditable markdown.
"""

from datetime import datetime
import json
import os
import re
from typing import Any
from google.antigravity import Agent
from features.shared.observability import BackendObservability

STATE_FILE = os.path.abspath("./brain_state.json")
HUMAN_MEM_FILE = os.path.abspath("./brain.md")


def load_structured_state() -> dict[str, Any]:
    """Loads the programmatic memory state safely."""
    if not os.path.exists(STATE_FILE):
        return {
            "last_run_status": "init",
            "last_run_timestamp": None,
            "total_listings_created_to_date": 0,
            "total_events_created_to_date": 0,
            "consecutive_failures": 0,
            "cities_tracked": [],
        }
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        BackendObservability.warning(
            "Failed to parse structured memory state. Resetting state.",
            exception=exc,
        )
        return {
            "last_run_status": "corrupt_reset",
            "last_run_timestamp": None,
            "total_listings_created_to_date": 0,
            "total_events_created_to_date": 0,
            "consecutive_failures": 0,
            "cities_tracked": [],
        }


def save_structured_state(state: dict[str, Any]) -> None:
    """Saves the programmatic memory state cleanly."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        BackendObservability.error(
            "Failed to save structured state to brain_state.json.", exception=exc
        )


async def execute_agent_memory_loop(
    agent: Agent, run_start_time: datetime, scan_logs: list[dict[str, Any]]
) -> str:
    """Runs the scheduled scraper agent memory synthesis loop.

    Reads previous memory programmatically, feeds telemetry into the Antigravity Agent,
    parses updated JSON state boundaries, compiles brain.md, and returns insights.
    """
    BackendObservability.info("Executing Antigravity Agent Memory loop...")

    # 1. Ingest structured memory state programmatically
    state = load_structured_state()

    # Calculate statistics from current run
    run_created_listings = 0
    run_created_events = 0
    run_failed_scans = 0
    run_cities: set[str] = set()

    for log in scan_logs:
        run_cities.add(log.get("city", "UNKNOWN"))
        if log.get("status") == "FAILED":
            run_failed_scans += 1

        # Compile counts based on scan type
        scan_type = log.get("scanType", "LISTING")
        created = log.get("listingsCreated", 0)

        if scan_type == "EVENT":
            run_created_events += created
        else:
            run_created_listings += created

    # 2. Formulate dynamic contextual instructions for the Agent
    custom_context = (
        f"You are analyzing the latest Fina directories scraper execution.\n"
        f"--- CURRENT RUN SUMMARY ---\n"
        f"- Start Time: {run_start_time.isoformat()}\n"
        f"- Scanned Cities: {list(run_cities)}\n"
        f"- Newly Created Listings: {run_created_listings}\n"
        f"- Newly Created Events: {run_created_events}\n"
        f"- Failed Scans: {run_failed_scans}\n\n"
        f"--- PAST PERSISTENT MEMORY ---\n"
        f"- Last Run Timestamp: {state.get('last_run_timestamp')}\n"
        f"- Last Run Status: {state.get('last_run_status')}\n"
        f"- Total Listings Created to Date: {state.get('total_listings_created_to_date')}\n"
        f"- Total Events Created to Date: {state.get('total_events_created_to_date')}\n"
        f"- Consecutive Failures: {state.get('consecutive_failures')}\n\n"
        f"--- INSTRUCTIONS ---\n"
        f"1. Generate an EXTREMELY BRIEF, high-level narrative summary (maximum 2-3 short bullet points, under 15 words per bullet) highlighting ONLY the most essential operational updates. Keep it under a 1-minute read limit (maximum 45 words total). DO NOT include introductory chatter, greetings, generic strategic headers, or conversational fluff.\n"
        f"2. You MUST include a ```json code block containing the updated variables:\n"
        f"```json\n"
        f"{{\n"
        f"  \"total_listings_created_to_date\": {state.get('total_listings_created_to_date', 0) + run_created_listings},\n"
        f"  \"total_events_created_to_date\": {state.get('total_events_created_to_date', 0) + run_created_events},\n"
        f"  \"consecutive_failures\": {state.get('consecutive_failures', 0) + 1 if run_failed_scans > 0 else 0}\n"
        f"}}\n"
        f"```\n"
    )

    # 3. Invoke the Antigravity Agent
    try:
        response = await agent.chat(custom_context)
        reply_text = await response.text()
    except Exception as exc:
        BackendObservability.error(
            "Failed to communicate with Antigravity Agent for memory loop.",
            exception=exc,
        )
        reply_text = "Memory loop error: Agent chat failed."
        state["last_run_status"] = "failed"
        save_structured_state(state)
        return reply_text

    # 4. Extract and save structured programmatic updates
    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", reply_text, re.DOTALL)
        if json_match:
            updates = json.loads(json_match.group(1).strip())
            state.update(updates)

            # Update meta variables
            state["last_run_status"] = (
                "success" if run_failed_scans == 0 else "partial_failure"
            )
            state["last_run_timestamp"] = datetime.utcnow().isoformat() + "Z"

            # Incorporate cities
            cities_set = set(state.get("cities_tracked", []))
            cities_set.update(run_cities)
            state["cities_tracked"] = sorted(list(cities_set))

            save_structured_state(state)
            BackendObservability.info("Successfully updated brain_state.json memory.")
    except Exception as parse_exc:
        BackendObservability.error(
            "Failed to parse agent structured memory updates.", exception=parse_exc
        )
        state["last_run_status"] = "failed"
        save_structured_state(state)

    # 5. Output beautiful human presentation view to brain.md
    await compile_human_brain_markdown(state, reply_text)

    return reply_text


async def compile_human_brain_markdown(
    state: dict[str, Any], agent_reply: str
) -> None:
    """Compiles a beautifully formatted human-readable presentation of the agent memory."""
    markdown_content = f"""# 🧠 Fina Agent Memory & Scraper Diagnostics

* **Last Scrape Run:** `{state.get('last_run_timestamp')}`
* **Last Execution Status:** `{state.get('last_run_status')}`
* **Total Active Cities Tracked:** `{len(state.get('cities_tracked', []))}` (`{", ".join(state.get('cities_tracked', []))}`)
* **Total Database Listings Created to Date:** `{state.get('total_listings_created_to_date')}`
* **Total Database Events Created to Date:** `{state.get('total_events_created_to_date')}`
* **Consecutive Failures Count:** `{state.get('consecutive_failures')}`

---

## 📝 Latest Agent Insight & Analysis Summary
{agent_reply}

---
*Note: This file is compiled dynamically by the Google Antigravity Agent on each cron execution.
Do not edit directly; to customize agent rules, modify system_instructions configurations.*
"""
    try:
        with open(HUMAN_MEM_FILE, "w", encoding="utf-8") as f:
            f.write(markdown_content)
    except Exception as exc:
        BackendObservability.error("Failed to write brain.md file.", exception=exc)
