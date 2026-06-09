#!/usr/bin/env python3
"""CLI script to audit, verify, and correct category classifications for Fina listings.

Compares listing details against a canonical category specification in data/categories.json
using the Gemini LLM.
"""

import os
import sys
import json
import argparse
import asyncio
import re
from datetime import datetime

# Enable FINA_AGENT_CLI_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add parent directory to path to allow importing modules
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability, audit_token_budget

async def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Fina listing categories.")
    parser.add_argument("--city", type=str, required=True, help="Target city to audit listings for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of listings to check.")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination.")
    parser.add_argument("--dry-run", action="store_true", help="Audit categories without updating the database.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(
        f"Starting agent_audit_listings.py with city={args.city}, limit={args.limit}, offset={args.offset}, dry_run={args.dry_run}",
        conversation_id=args.trace_id
    )

    # 1. Load data/categories.json rules
    categories_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "categories.json"
    )
    try:
        with open(categories_path, "r", encoding="utf-8") as f:
            categories_data = json.load(f)
    except Exception as e:
        BackendObservability.fatal(
            f"Failed to load categories.json: {e}",
            exception=e,
            conversation_id=args.trace_id
        )
        sys.exit(1)

    # 2. Query listings by city
    BackendObservability.trace(
        f"Executing GraphQL operation ListCityListings with variables: {{'city': '{args.city}'}}",
        conversation_id=args.trace_id
    )
    try:
        result = await execute_graphql_operation(operation_name="ListCityListings", variables={"city": args.city})
    except Exception as e:
        BackendObservability.fatal(
            f"GraphQL query ListCityListings failed: {e}",
            exception=e,
            conversation_id=args.trace_id
        )
        sys.exit(1)

    listings = result.get("data", {}).get("listings", [])
    total_listings = len(listings)
    listings_slice = listings[args.offset : args.offset + args.limit]

    BackendObservability.info(
        f"Retrieved {total_listings} listings for {args.city}. Auditing slice of {len(listings_slice)} (offset {args.offset}).",
        conversation_id=args.trace_id
    )

    # Import google-genai package
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field

    class CategoryAuditResult(BaseModel):
        recategorize: bool = Field(description="True if the category needs to be updated, False otherwise")
        categories: list[str] = Field(description="The updated category or categories for the listing, from the allowed list: RESTAURANT, CAFE, SHOP, CHURCH, GOVERNMENT, COMMUNITY, SERVICES")
        reason: str = Field(description="The reason/rationalization for this category assignment")

    # Initialize Gemini client if API key is present
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key or gemini_key == "mock-key":
        BackendObservability.warning(
            "GEMINI_API_KEY is not set or is 'mock-key'. Using mock/dry-run predictions.",
            conversation_id=args.trace_id
        )
        client = None
    else:
        client = genai.Client()

    new_corrections = []
    errors = []
    scanned_count = 0
    correct_count = 0
    recat_count = 0

    categories_spec = json.dumps(categories_data, indent=2)

    for listing in listings_slice:
        scanned_count += 1
        listing_id = listing.get("id")
        listing_name = listing.get("name")
        curr_categories = listing.get("categories", [])
        desc = listing.get("description", "")
        tags = listing.get("tags", "")

        BackendObservability.trace(
            f"Auditing listing: name='{listing_name}' (ID={listing_id}), current categories={curr_categories}",
            conversation_id=args.trace_id
        )

        # Skip if listing is missing core identification details
        if not listing_id or not listing_name:
            BackendObservability.warning(
                f"Skipping listing with missing ID or name: {listing}",
                conversation_id=args.trace_id
            )
            continue

        result_json = None
        if client is None:
            # Mock behavior / fallback when no real API key is available
            # If name or description contains 'cargo' or 'freight' or 'migration' or 'accountant' and current category is 'COMMUNITY', recategorize to 'SERVICES'
            desc_lower = desc.lower() if desc else ""
            name_lower = listing_name.lower()
            if ("cargo" in name_lower or "freight" in name_lower or "cargo" in desc_lower or "freight" in desc_lower) and "COMMUNITY" in curr_categories:
                result_json = {
                    "recategorize": True,
                    "categories": ["SERVICES"],
                    "reason": "Balikbayan cargo is a commercial logistics service, not a non-profit community group."
                }
            else:
                result_json = {
                    "recategorize": False,
                    "categories": curr_categories,
                    "reason": "Current categories match listing description and rules."
                }
        else:
            prompt = f"""You are a Fina listing auditor. Your task is to review the category classification for the following business listing and determine if it should be re-categorized based on the canonical category definitions.

Canonical Category Definitions:
{categories_spec}

Listing to Audit:
ID: {listing_id}
Name: {listing_name}
Current Categories: {curr_categories}
Description: {desc}
Tags: {tags}
City: {args.city}

Allowed categories to choose from: RESTAURANT, CAFE, SHOP, CHURCH, GOVERNMENT, COMMUNITY, SERVICES.

Perform a thorough evaluation:
1. Review the current category or categories.
2. Compare the listing details against the description, rules, and examples of each category.
3. Pay close attention to professional services, cargo forwarders, logistics, migration agents, accountants, etc., which belong in 'SERVICES', not 'COMMUNITY'.
4. Return a structured JSON response. Set 'recategorize' to true if the category needs to be updated, and false if the current category is correct. If 'recategorize' is true, set 'categories' to the list of correct category/categories (e.g. ["SERVICES"]). Always provide a detailed 'reason' for your decision.
"""
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CategoryAuditResult,
                        temperature=0.0,
                    )
                )
                
                # Audit token utilization
                prompt_tokens = (len(prompt or "") + 3) // 4
                candidate_tokens = (len(response.text or "") + 3) // 4
                audit_token_budget(
                    conversation_id=args.trace_id or "unknown",
                    prompt_tokens=prompt_tokens,
                    candidate_tokens=candidate_tokens
                )
                
                try:
                    result_json = json.loads(response.text)
                except json.JSONDecodeError as jde:
                    BackendObservability.error(
                        f"Gemini returned invalid JSON for listing '{listing_name}': {response.text}",
                        exception=jde,
                        conversation_id=args.trace_id
                    )
                    errors.append(f"JSON decode failed for ID {listing_id}: {jde}")
                    continue
            except Exception as e:
                BackendObservability.error(
                    f"Gemini API call failed for listing '{listing_name}': {e}",
                    exception=e,
                    conversation_id=args.trace_id
                )
                errors.append(f"Gemini call failed for ID {listing_id}: {e}")
                continue

        if result_json:
            recategorize = result_json.get("recategorize", False)
            new_cats = result_json.get("categories", [])
            reason = result_json.get("reason", "")

            if recategorize and new_cats:
                recat_count += 1
                new_corrections.append({
                    "name": listing_name,
                    "old_categories": ", ".join(curr_categories),
                    "new_categories": ", ".join(new_cats),
                    "reason": reason,
                    "db_id": listing_id
                })

                if not args.dry_run:
                    BackendObservability.info(
                        f"Recategorizing listing '{listing_name}' (ID={listing_id}) from {curr_categories} to {new_cats}. Reason: {reason}",
                        conversation_id=args.trace_id
                    )
                    try:
                        await execute_graphql_operation(
                            operation_name="UpdateListingData",
                            variables={
                                "id": listing_id,
                                "categories": new_cats
                            }
                        )
                    except Exception as e:
                        BackendObservability.error(
                            f"Failed to update listing ID={listing_id} categories: {e}",
                            exception=e,
                            conversation_id=args.trace_id
                        )
                        errors.append(f"DB update failed for ID {listing_id}: {e}")
                else:
                    BackendObservability.info(
                        f"[DRY-RUN] Would recategorize listing '{listing_name}' (ID={listing_id}) from {curr_categories} to {new_cats}. Reason: {reason}",
                        conversation_id=args.trace_id
                    )
            else:
                correct_count += 1

    # 3. Write/Consolidate Report
    now = datetime.now()
    yyyymmdd = now.strftime("%Y%m%d")
    hhmm = now.strftime("%H%M")
    
    logs_dir = os.path.join("logs", yyyymmdd)
    os.makedirs(logs_dir, exist_ok=True)
    report_path = os.path.join(logs_dir, f"fina_listing_auditor_report_{args.city}_{yyyymmdd}_{hhmm}.md")

    existing_eval = 0
    existing_corr = 0
    existing_unchanged = 0
    existing_errors_count = 0
    existing_applied_updates = []
    existing_errors_list = []

    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse metadata/counts from existing report
            m_eval = re.search(r"\*\*Listings Evaluated\*\*\s*\|\s*(\d+)", content)
            if m_eval:
                existing_eval = int(m_eval.group(1))

            m_corr = re.search(r"\*\*Corrections Applied\*\*\s*\|\s*(\d+)", content)
            if m_corr:
                existing_corr = int(m_corr.group(1))

            m_unchanged = re.search(r"\*\*Listings Correct / Unchanged\*\*\s*\|\s*(\d+)", content)
            if m_unchanged:
                existing_unchanged = int(m_unchanged.group(1))

            m_err = re.search(r"\*\*Errors Encountered\*\*\s*\|\s*(\d+)", content)
            if m_err:
                existing_errors_count = int(m_err.group(1))

            # Parse Applied Updates log
            update_blocks = re.findall(
                r"\d+\.\s+\*\*(.*?)\*\*\s*\n\s*-\s*\*\*Old Categories\*\*:\s*(.*?)\s*\n\s*-\s*\*\*New Categories\*\*:\s*(.*?)\s*\n\s*-\s*\*\*Reason\*\*:\s*(.*?)\s*\n\s*-\s*\*\*DB ID\*\*:\s*`(.*?)`",
                content
            )
            for name, old_cat, new_cat, reason, db_id in update_blocks:
                existing_applied_updates.append({
                    "name": name,
                    "old_categories": old_cat,
                    "new_categories": new_cat,
                    "reason": reason,
                    "db_id": db_id
                })

            # Parse Errors & Warnings list
            err_section = content.split("## Errors & Warnings")
            if len(err_section) > 1:
                err_lines = err_section[1].strip().split("\n")
                for line in err_lines:
                    line = line.strip()
                    if line.startswith("- ") and "None encountered" not in line:
                        existing_errors_list.append(line[2:])
        except Exception as e:
            BackendObservability.warning(
                f"Failed to parse existing report for merging: {e}",
                conversation_id=args.trace_id
            )

    total_eval = existing_eval + scanned_count
    total_corr = existing_corr + recat_count
    total_unchanged = total_eval - total_corr
    total_errors = existing_errors_count + len(errors)

    # Merge updates list without duplicate entries by DB ID
    all_updates = list(existing_applied_updates)
    for corr in new_corrections:
        if not any(x["db_id"] == corr["db_id"] for x in all_updates):
            all_updates.append(corr)

    # Merge errors list
    all_errors = list(existing_errors_list)
    for err in errors:
        if err not in all_errors:
            all_errors.append(err)

    exec_date = now.strftime("%Y-%m-%d %I:%M %p AEST")

    report_content = f"""# Fina Listing Auditor Report — {args.city}

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_listing_auditor |
| **Target City** | {args.city} |
| **Listings Evaluated** | {total_eval} |
| **Corrections Applied** | {total_corr} |
| **Dry-Run Mode** | {args.dry_run} |
| **Execution Date** | {exec_date} |
| **Trace ID** | `{args.trace_id or ""}` |

## Summary

| Metric | Count |
| :--- | :---: |
| **Total Listings Scanned** | {total_eval} |
| **Listings Correct / Unchanged** | {total_unchanged} |
| **Listings Re-categorized** | {total_corr} |
| **Errors Encountered** | {total_errors} |

## Corrections Log

### Applied Updates
"""
    for idx, update in enumerate(all_updates, 1):
        report_content += f"""
{idx}. **{update['name']}**
   - **Old Categories**: {update['old_categories']}
   - **New Categories**: {update['new_categories']}
   - **Reason**: {update['reason']}
   - **DB ID**: `{update['db_id']}`
"""

    report_content += "\n## Errors & Warnings\n\n"
    if all_errors:
        for err in all_errors:
            report_content += f"- {err}\n"
    else:
        report_content += "- None encountered.\n"

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        BackendObservability.info(
            f"Consolidated audit report written to: {report_path}",
            conversation_id=args.trace_id
        )
    except Exception as e:
        BackendObservability.error(
            f"Failed to write audit report: {e}",
            exception=e,
            conversation_id=args.trace_id
        )

    # 4. Output pagination info to stdout
    has_more = total_listings > args.offset + args.limit
    sys.stdout.write(json.dumps({
        "listings": [
            {
                "id": l.get("id"),
                "name": l.get("name"),
                "categories": l.get("categories", [])
            }
            for l in listings_slice
        ],
        "total": total_listings,
        "has_more": has_more
    }))

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
