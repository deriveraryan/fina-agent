"""One-time migration script to clear template fallback descriptions from listings.

Queries all listings across cities, identifies records where the description
starts with "A verified", and clears the description field via UpdateListingData.
"""

import os
import sys
import json
import argparse
import asyncio

# Add root folder to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability

CITIES = ["SYDNEY", "MELBOURNE", "BRISBANE", "ADELAIDE", "PERTH", "HOBART", "DARWIN", "CANBERRA", "GOLD COAST", "NEWCASTLE"]

TEMPLATE_PREFIX = "A verified"


def is_template_description(description: str | None) -> bool:
    """Returns True if the description is a template fallback that should be cleared."""
    if not description:
        return False
    return description.strip().startswith(TEMPLATE_PREFIX)


async def migrate_city(city: str, dry_run: bool = False, trace_id: str | None = None) -> dict:
    """Clears template descriptions for all listings in a city.

    Returns a summary dict with counts of total, matched, and updated listings.
    """
    summary = {"city": city, "total": 0, "matched": 0, "updated": 0, "errors": 0}

    BackendObservability.info(f"Fetching listings for {city}...", conversation_id=trace_id)
    try:
        res = await execute_graphql_operation(
            "ListAdminListings",
            {"city": city, "limit": 1000, "verificationStatuses": ["VERIFIED", "UNVERIFIED"]},
        )
        listings = res.get("data", {}).get("listings", [])
        summary["total"] = len(listings)
        BackendObservability.info(f"Found {len(listings)} listings in {city}.", conversation_id=trace_id)

        for listing in listings:
            description = listing.get("description")
            if not is_template_description(description):
                continue

            summary["matched"] += 1
            listing_id = listing["id"]
            name = listing.get("name", "Unknown")

            if dry_run:
                BackendObservability.info(
                    f"[DRY RUN] Would clear description for '{name}' (ID: {listing_id}): \"{description}\"",
                    conversation_id=trace_id,
                )
                continue

            try:
                BackendObservability.trace(
                    f"Clearing description for '{name}' (ID: {listing_id})...",
                    conversation_id=trace_id,
                )
                await execute_graphql_operation(
                    "UpdateListingData",
                    {"id": listing_id, "description": ""},
                )
                summary["updated"] += 1
                BackendObservability.info(
                    f"Cleared description for '{name}' (ID: {listing_id}).",
                    conversation_id=trace_id,
                )
                await asyncio.sleep(0.2)
            except Exception as exc:
                summary["errors"] += 1
                BackendObservability.error(
                    f"Failed to update '{name}' (ID: {listing_id}): {exc}",
                    exception=exc,
                    conversation_id=trace_id,
                )

    except Exception as exc:
        BackendObservability.error(
            f"Error fetching listings for {city}: {exc}",
            exception=exc,
            conversation_id=trace_id,
        )

    return summary


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time migration to clear template fallback descriptions."
    )
    parser.add_argument("--city", type=str, help="Specific city to migrate (optional, defaults to all cities).")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to database.")
    parser.add_argument("--trace-id", type=str, help="Trace correlation ID.")
    args = parser.parse_args()

    trace_id = args.trace_id
    dry_run = args.dry_run

    mode_label = "[DRY RUN] " if dry_run else ""
    BackendObservability.info(
        f"{mode_label}Starting template description migration...",
        conversation_id=trace_id,
    )

    cities_to_migrate = [args.city.upper()] if args.city else CITIES
    all_summaries = []

    for city in cities_to_migrate:
        summary = await migrate_city(city, dry_run=dry_run, trace_id=trace_id)
        all_summaries.append(summary)

    total_matched = sum(s["matched"] for s in all_summaries)
    total_updated = sum(s["updated"] for s in all_summaries)
    total_errors = sum(s["errors"] for s in all_summaries)

    BackendObservability.info(
        f"{mode_label}Migration complete! Matched: {total_matched}, Updated: {total_updated}, Errors: {total_errors}",
        conversation_id=trace_id,
    )

    sys.stdout.write(json.dumps({"summaries": all_summaries}, indent=2))


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
