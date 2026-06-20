"""Ad-hoc script to restore review records from a backup JSON file.

Matches backup listings to live listings using (name, city) with normalized
city values, then pushes backup reviews via the CreateReview mutation,
skipping any reviews whose externalSourceId already exists in the live DB.

Usage:
    python3 scripts/agent_restore_reviews.py \
        --reviews-backup ../fina/backup/reviews_backup_20260614_025422.json \
        --listings-backup ../fina/backup/listings_backup_20260614_025422.json \
        --trace-id <CONVERSATION_ID>
"""

import os
import sys
import json
import asyncio
import argparse

# Enable FINA_AGENT_CLI_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add parent path for imports
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)

from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability


def normalize_city(city: str) -> str:
    """Normalizes city strings for consistent matching.

    Handles casing variations (sydney, Sydney, SYDNEY) and
    underscore/space variations (GOLD_COAST vs GOLD COAST).
    """
    return city.strip().upper().replace("_", " ")


def build_backup_lookup(
    backup_listings: list[dict],
) -> dict[str, dict]:
    """Builds a map from backup listing ID -> listing record."""
    return {listing["id"]: listing for listing in backup_listings}


def build_name_city_key(name: str, city: str) -> str:
    """Creates a normalized (name, city) composite key."""
    return f"{name.strip().lower()}||{normalize_city(city)}"


async def fetch_live_listings(trace_id: str) -> list[dict]:
    """Fetches all listings currently in the live database."""
    BackendObservability.trace("Fetching all live listings via ListAllListings...", conversation_id=trace_id)
    result = await execute_graphql_operation("ListAllListings", {})
    listings = result.get("data", {}).get("listings", [])
    BackendObservability.trace(f"Fetched {len(listings)} live listings.", conversation_id=trace_id)
    return listings


async def fetch_live_reviews(trace_id: str) -> list[dict]:
    """Fetches all reviews currently in the live database."""
    BackendObservability.trace("Fetching all live reviews via ListAllReviews...", conversation_id=trace_id)
    result = await execute_graphql_operation("ListAllReviews", {})
    reviews = result.get("data", {}).get("reviews", [])
    BackendObservability.trace(f"Fetched {len(reviews)} live reviews.", conversation_id=trace_id)
    return reviews


async def restore_reviews(
    reviews_backup_path: str,
    listings_backup_path: str,
    trace_id: str,
) -> None:
    """Main restore pipeline.

    1. Load backup files (reviews + listings).
    2. Fetch live listings and live reviews.
    3. Build (name, city) -> live listing ID mapping.
    4. For each backup review, resolve its backup listingId to a live listing ID.
    5. Skip if externalSourceId already exists in live reviews.
    6. Push via CreateReview mutation.
    """
    # --- Step 1: Load backup data ---
    BackendObservability.trace(f"Loading reviews backup from: {reviews_backup_path}", conversation_id=trace_id)
    with open(reviews_backup_path, "r") as f:
        backup_reviews: list[dict] = json.load(f)
    BackendObservability.trace(f"Loaded {len(backup_reviews)} backup reviews.", conversation_id=trace_id)

    BackendObservability.trace(f"Loading listings backup from: {listings_backup_path}", conversation_id=trace_id)
    with open(listings_backup_path, "r") as f:
        backup_listings: list[dict] = json.load(f)
    BackendObservability.trace(f"Loaded {len(backup_listings)} backup listings.", conversation_id=trace_id)

    # --- Step 2: Fetch live state ---
    live_listings = await fetch_live_listings(trace_id)
    live_reviews = await fetch_live_reviews(trace_id)

    # --- Step 3: Build lookup indices ---
    # Backup listing ID -> backup listing record
    backup_id_to_listing = build_backup_lookup(backup_listings)

    # Live (name, city) -> live listing ID (first match wins for duplicates)
    live_name_city_to_id: dict[str, str] = {}
    for live_listing in live_listings:
        key = build_name_city_key(live_listing["name"], live_listing["city"])
        if key not in live_name_city_to_id:
            live_name_city_to_id[key] = live_listing["id"]

    # Live externalSourceId set for dedup
    live_ext_ids: set[str] = {
        r["externalSourceId"] for r in live_reviews if r.get("externalSourceId")
    }

    BackendObservability.trace(
        f"Built indices: {len(live_name_city_to_id)} unique live (name,city) keys, "
        f"{len(live_ext_ids)} existing review externalSourceIds.",
        conversation_id=trace_id,
    )

    # --- Step 4 & 5 & 6: Match, dedup, push ---
    stats = {
        "total_backup_reviews": len(backup_reviews),
        "matched": 0,
        "skipped_duplicate": 0,
        "skipped_no_match": 0,
        "pushed": 0,
        "errors": 0,
    }
    unmatched_listings: dict[str, str] = {}  # backup_listing_id -> name

    for i, review in enumerate(backup_reviews, start=1):
        backup_listing_id = review["listingId"]
        ext_source_id = review.get("externalSourceId", "")

        # Resolve backup listing ID to name + city
        backup_listing = backup_id_to_listing.get(backup_listing_id)
        if not backup_listing:
            BackendObservability.error(
                f"[{i}/{len(backup_reviews)}] Backup listing ID {backup_listing_id} not found in backup listings file. Skipping.",
                conversation_id=trace_id,
            )
            stats["skipped_no_match"] += 1
            continue

        # Build key and find live match
        key = build_name_city_key(backup_listing["name"], backup_listing["city"])
        live_listing_id = live_name_city_to_id.get(key)

        if not live_listing_id:
            if backup_listing_id not in unmatched_listings:
                unmatched_listings[backup_listing_id] = backup_listing["name"]
                BackendObservability.error(
                    f"[{i}/{len(backup_reviews)}] No live listing match for "
                    f"\"{backup_listing['name']}\" (city: {backup_listing['city']}). "
                    f"Skipping all reviews for this listing.",
                    conversation_id=trace_id,
                )
            stats["skipped_no_match"] += 1
            continue

        stats["matched"] += 1

        # Check for duplicate by externalSourceId
        if ext_source_id and ext_source_id in live_ext_ids:
            stats["skipped_duplicate"] += 1
            continue

        # Build CreateReview payload
        payload = {
            "listingId": live_listing_id,
            "externalSourceId": ext_source_id,
            "authorName": review.get("authorName"),
            "rating": review.get("rating"),
            "text": review.get("text"),
            "publishedDate": review.get("publishedDate"),
        }

        # Remove None values to avoid sending nulls for optional fields
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            await execute_graphql_operation("CreateReview", payload)
            stats["pushed"] += 1
            if stats["pushed"] % 50 == 0:
                BackendObservability.trace(
                    f"Progress: {stats['pushed']} reviews pushed so far ({i}/{len(backup_reviews)} processed).",
                    conversation_id=trace_id,
                )
        except Exception as exc:
            stats["errors"] += 1
            BackendObservability.error(
                f"[{i}/{len(backup_reviews)}] Failed to push review (externalSourceId={ext_source_id}): {exc}",
                conversation_id=trace_id,
            )

    # --- Summary ---
    summary = (
        f"\n{'=' * 60}\n"
        f"RESTORE COMPLETE\n"
        f"{'=' * 60}\n"
        f"Total backup reviews:    {stats['total_backup_reviews']}\n"
        f"Matched to live listing: {stats['matched']}\n"
        f"Skipped (duplicate):     {stats['skipped_duplicate']}\n"
        f"Skipped (no match):      {stats['skipped_no_match']}\n"
        f"Pushed (new):            {stats['pushed']}\n"
        f"Errors:                  {stats['errors']}\n"
        f"{'=' * 60}"
    )
    BackendObservability.trace(summary, conversation_id=trace_id)

    if unmatched_listings:
        BackendObservability.trace(
            f"\nUnmatched backup listings ({len(unmatched_listings)}):",
            conversation_id=trace_id,
        )
        for lid, name in unmatched_listings.items():
            BackendObservability.trace(f"  - {name} (backup ID: {lid})", conversation_id=trace_id)

    # Also print summary to stdout for visibility
    print(summary, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore review records from backup JSON files."
    )
    parser.add_argument(
        "--reviews-backup",
        required=True,
        help="Path to the reviews backup JSON file.",
    )
    parser.add_argument(
        "--listings-backup",
        required=True,
        help="Path to the listings backup JSON file.",
    )
    parser.add_argument(
        "--trace-id",
        required=True,
        help="Conversation/trace ID for observability correlation.",
    )
    args = parser.parse_args()

    asyncio.run(
        restore_reviews(
            reviews_backup_path=args.reviews_backup,
            listings_backup_path=args.listings_backup,
            trace_id=args.trace_id,
        )
    )


if __name__ == "__main__":
    main()
