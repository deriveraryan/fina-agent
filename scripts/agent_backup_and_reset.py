#!/usr/bin/env python3
"""Backs up Listing, Review, and Event data to local JSON files, then deletes
all rows from Listing (cascading Review, Event, SocialPostTracker) and
AgentScanLog to reset the database to a clean state.

Usage:
    cd fina-agent
    source .venv/bin/activate
    python3 scripts/agent_backup_and_reset.py --trace-id <CONVERSATION_ID>
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path for feature imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability


# Resolve backup output directory (../../fina/backup/ relative to this script)
SCRIPT_DIR = Path(__file__).resolve().parent
BACKUP_DIR = SCRIPT_DIR.parent.parent / "fina" / "backup"


async def fetch_all_data() -> dict[str, list[dict]]:
    """Fetches all listings, reviews, events, and agent scan log IDs."""
    BackendObservability.info("Fetching all listings...")
    listings_res = await execute_graphql_operation("ListAllListings", {})
    listings = listings_res.get("data", {}).get("listings", [])
    BackendObservability.info(f"  → {len(listings)} listings fetched")

    BackendObservability.info("Fetching all reviews...")
    reviews_res = await execute_graphql_operation("ListAllReviews", {})
    reviews = reviews_res.get("data", {}).get("reviews", [])
    BackendObservability.info(f"  → {len(reviews)} reviews fetched")

    BackendObservability.info("Fetching all events...")
    events_res = await execute_graphql_operation("ListAllEvents", {})
    events = events_res.get("data", {}).get("events", [])
    BackendObservability.info(f"  → {len(events)} events fetched")

    BackendObservability.info("Fetching all agent scan log IDs...")
    scan_logs_res = await execute_graphql_operation("ListAllAgentScanLogs", {})
    scan_logs = scan_logs_res.get("data", {}).get("agentScanLogs", [])
    BackendObservability.info(f"  → {len(scan_logs)} agent scan logs fetched")

    return {
        "listings": listings,
        "reviews": reviews,
        "events": events,
        "scan_logs": scan_logs,
    }


def write_backup_files(
    data: dict[str, list[dict]], timestamp: str
) -> dict[str, Path]:
    """Writes backup JSON files to the backup directory."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    files: dict[str, Path] = {}
    for key in ("listings", "reviews", "events"):
        filename = f"{key}_backup_{timestamp}.json"
        filepath = BACKUP_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data[key], f, indent=2, ensure_ascii=False, default=str)
        files[key] = filepath
        BackendObservability.info(
            f"  ✓ Wrote {len(data[key])} {key} → {filepath}"
        )

    return files


async def delete_all_listings(listings: list[dict]) -> int:
    """Deletes all listings one-by-one (cascades Reviews, Events, SocialPostTrackers)."""
    total = len(listings)
    deleted = 0

    for i, listing in enumerate(listings, 1):
        listing_id = listing["id"]
        try:
            await execute_graphql_operation("DeleteListing", {"id": listing_id})
            deleted += 1
            if i % 25 == 0 or i == total:
                BackendObservability.info(
                    f"  Deleted {i}/{total} listings..."
                )
        except RuntimeError as exc:
            BackendObservability.error(
                f"  ✗ Failed to delete listing {listing_id}: {exc}"
            )

    return deleted


async def delete_all_scan_logs(scan_logs: list[dict]) -> int:
    """Deletes all agent scan log entries one-by-one."""
    total = len(scan_logs)
    deleted = 0

    for i, log in enumerate(scan_logs, 1):
        log_id = log["id"]
        try:
            await execute_graphql_operation("DeleteAgentScanLog", {"id": log_id})
            deleted += 1
            if i % 25 == 0 or i == total:
                BackendObservability.info(
                    f"  Deleted {i}/{total} scan logs..."
                )
        except RuntimeError as exc:
            BackendObservability.error(
                f"  ✗ Failed to delete scan log {log_id}: {exc}"
            )

    return deleted


async def main(trace_id: str) -> None:
    """Orchestrates the full backup and reset workflow."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    BackendObservability.info(f"=== Database Backup & Reset [{timestamp}] ===")

    # Phase 1: Fetch all data
    BackendObservability.info("\n📥 Phase 1: Fetching all data...")
    data = await fetch_all_data()

    # Phase 2: Write backup files
    BackendObservability.info("\n💾 Phase 2: Writing backup files...")
    backup_files = write_backup_files(data, timestamp)

    # Phase 3: Delete all listings (cascades children)
    BackendObservability.info(
        f"\n🗑️  Phase 3: Deleting {len(data['listings'])} listings "
        "(cascading Reviews, Events, SocialPostTrackers)..."
    )
    listings_deleted = await delete_all_listings(data["listings"])

    # Phase 4: Delete all agent scan logs
    BackendObservability.info(
        f"\n🗑️  Phase 4: Deleting {len(data['scan_logs'])} agent scan logs..."
    )
    scan_logs_deleted = await delete_all_scan_logs(data["scan_logs"])

    # Summary
    BackendObservability.info("\n" + "=" * 50)
    BackendObservability.info("✅ BACKUP & RESET COMPLETE")
    BackendObservability.info("=" * 50)
    BackendObservability.info(f"  Listings backed up:    {len(data['listings'])}")
    BackendObservability.info(f"  Reviews backed up:     {len(data['reviews'])}")
    BackendObservability.info(f"  Events backed up:      {len(data['events'])}")
    BackendObservability.info(f"  Listings deleted:      {listings_deleted}")
    BackendObservability.info(
        f"  Scan logs deleted:     {scan_logs_deleted}"
    )
    BackendObservability.info(f"  Backup directory:      {BACKUP_DIR}")
    for key, path in backup_files.items():
        BackendObservability.info(f"    → {path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Back up and reset the Fina database to a clean state."
    )
    parser.add_argument(
        "--trace-id",
        required=True,
        help="Conversation/trace ID for observability correlation.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.trace_id))
