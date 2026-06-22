"""Full backup restore script — restores ALL missing listings and reviews.

Phase A: Fixes normalize_city to preserve underscores (GOLD_COAST stays GOLD_COAST).
Phase B: Re-creates ALL missing listings from backup (not just those with reviews).
Phase C: Restores ALL missing reviews from backup.

Constraints:
    - Does NOT generate descriptionEmbedding (leaves null to avoid Gemini API costs).
    - Uses correct city normalization (uppercase only, preserves underscores).
    - Idempotent: skips listings/reviews that already exist in the live DB.

Usage:
    python3 scripts/agent_restore_full.py \
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
    """Normalizes city strings — uppercase only, preserves underscores.

    GOLD_COAST stays GOLD_COAST (not 'GOLD COAST').
    Converts spaces to underscores for multi-word cities.
    """
    normalized = city.strip().upper()
    # Normalize 'GOLD COAST' (space) → 'GOLD_COAST' (underscore)
    normalized = normalized.replace(" ", "_")
    return normalized


def build_name_city_key(name: str, city: str) -> str:
    """Creates a normalized (name, city) composite key."""
    return f"{name.strip().lower()}||{normalize_city(city)}"


async def fetch_live_listings(trace_id: str) -> list[dict]:
    """Fetches all listings currently in the live database."""
    BackendObservability.trace(
        "Fetching all live listings via ListAllListings...",
        conversation_id=trace_id,
    )
    result = await execute_graphql_operation("ListAllListings", {})
    listings = result.get("data", {}).get("listings", [])
    BackendObservability.trace(
        f"Fetched {len(listings)} live listings.", conversation_id=trace_id
    )
    return listings


async def fetch_live_reviews(trace_id: str) -> list[dict]:
    """Fetches all reviews currently in the live database."""
    BackendObservability.trace(
        "Fetching all live reviews via ListAllReviews...",
        conversation_id=trace_id,
    )
    result = await execute_graphql_operation("ListAllReviews", {})
    reviews = result.get("data", {}).get("reviews", [])
    BackendObservability.trace(
        f"Fetched {len(reviews)} live reviews.", conversation_id=trace_id
    )
    return reviews


def build_listing_payload(backup_listing: dict) -> dict:
    """Builds a CreateListing payload from a backup listing record.

    Includes ALL fields from the backup except descriptionEmbedding.
    Uses correct city normalization (preserves underscores).
    """
    categories = backup_listing.get("categories")
    if categories is None:
        categories = []

    city = normalize_city(backup_listing.get("city", ""))

    payload = {
        "name": backup_listing["name"],
        "categories": categories,
        "city": city,
        "description": backup_listing.get("description", ""),
        "address": backup_listing.get("address", ""),
        "latitude": backup_listing.get("latitude", 0.0),
        "longitude": backup_listing.get("longitude", 0.0),
        "verificationStatus": backup_listing.get(
            "verificationStatus", "UNVERIFIED"
        ),
    }

    # Optional fields — only include if non-null
    optional_fields = [
        "phone",
        "website",
        "facebookUrl",
        "instagramUrl",
        "tiktokUrl",
        "facebookFollowers",
        "instagramFollowers",
        "tiktokFollowers",
        "operatingHours",
        "imageUrl",
        "tags",
        "sourceUrl",
        "status",
    ]
    for field in optional_fields:
        value = backup_listing.get(field)
        if value is not None:
            payload[field] = value

    return payload


async def restore_all(
    reviews_backup_path: str,
    listings_backup_path: str,
    trace_id: str,
) -> None:
    """Full restore pipeline.

    Phase B: Re-create ALL missing listings from backup.
    Phase C: Restore ALL missing reviews from backup.
    """
    # --- Load backup data ---
    BackendObservability.trace(
        f"Loading listings backup from: {listings_backup_path}",
        conversation_id=trace_id,
    )
    with open(listings_backup_path, "r") as f:
        backup_listings: list[dict] = json.load(f)
    BackendObservability.trace(
        f"Loaded {len(backup_listings)} backup listings.",
        conversation_id=trace_id,
    )

    BackendObservability.trace(
        f"Loading reviews backup from: {reviews_backup_path}",
        conversation_id=trace_id,
    )
    with open(reviews_backup_path, "r") as f:
        backup_reviews: list[dict] = json.load(f)
    BackendObservability.trace(
        f"Loaded {len(backup_reviews)} backup reviews.",
        conversation_id=trace_id,
    )

    backup_id_to_listing = {bl["id"]: bl for bl in backup_listings}

    # ============================================================
    # PHASE B: Re-create ALL missing listings
    # ============================================================
    BackendObservability.trace("=" * 60, conversation_id=trace_id)
    BackendObservability.trace(
        "PHASE B: Re-creating ALL missing listings", conversation_id=trace_id
    )
    BackendObservability.trace("=" * 60, conversation_id=trace_id)

    live_listings = await fetch_live_listings(trace_id)

    # Build live (name, city) → live listing ID index
    live_name_city_to_id: dict[str, str] = {}
    for ll in live_listings:
        key = build_name_city_key(ll["name"], ll["city"])
        if key not in live_name_city_to_id:
            live_name_city_to_id[key] = ll["id"]

    # Find ALL unmatched backup listings (not just those with reviews)
    unmatched_backup_listings: list[dict] = []
    seen_keys: set[str] = set()
    for bl in backup_listings:
        key = build_name_city_key(bl["name"], bl["city"])
        if key not in live_name_city_to_id and key not in seen_keys:
            unmatched_backup_listings.append(bl)
            seen_keys.add(key)

    BackendObservability.trace(
        f"Found {len(unmatched_backup_listings)} listings to re-create.",
        conversation_id=trace_id,
    )

    listing_stats = {"created": 0, "errors": 0, "by_city": {}}

    for i, bl in enumerate(unmatched_backup_listings, start=1):
        payload = build_listing_payload(bl)
        city = payload["city"]

        try:
            result = await execute_graphql_operation("CreateListing", payload)
            new_id = (
                result.get("data", {}).get("listing_insert", {}).get("id")
                or result.get("data", {}).get("createListing", {}).get("id")
            )
            if new_id:
                key = build_name_city_key(bl["name"], bl["city"])
                live_name_city_to_id[key] = new_id
                listing_stats["created"] += 1
                listing_stats["by_city"][city] = (
                    listing_stats["by_city"].get(city, 0) + 1
                )
                if listing_stats["created"] % 50 == 0:
                    BackendObservability.trace(
                        f"Phase B progress: {listing_stats['created']} created "
                        f"({i}/{len(unmatched_backup_listings)}).",
                        conversation_id=trace_id,
                    )
            else:
                BackendObservability.error(
                    f"[{i}/{len(unmatched_backup_listings)}] CreateListing "
                    f'returned no ID for "{bl["name"]}" — response: {result}',
                    conversation_id=trace_id,
                )
                listing_stats["errors"] += 1
        except Exception as exc:
            listing_stats["errors"] += 1
            BackendObservability.error(
                f"[{i}/{len(unmatched_backup_listings)}] Failed to create "
                f'listing "{bl["name"]}" (city: {city}): {exc}',
                conversation_id=trace_id,
            )

    phase_b_summary = (
        f"\n{'=' * 60}\n"
        f"PHASE B COMPLETE — Listing Restoration\n"
        f"{'=' * 60}\n"
        f"Listings to create:   {len(unmatched_backup_listings)}\n"
        f"Successfully created: {listing_stats['created']}\n"
        f"Errors:               {listing_stats['errors']}\n"
        f"By city:\n"
    )
    for city, count in sorted(
        listing_stats["by_city"].items(), key=lambda x: -x[1]
    ):
        phase_b_summary += f"  {city}: {count}\n"
    phase_b_summary += f"{'=' * 60}"

    BackendObservability.trace(phase_b_summary, conversation_id=trace_id)
    print(phase_b_summary, file=sys.stderr)

    # ============================================================
    # PHASE C: Restore ALL missing reviews
    # ============================================================
    BackendObservability.trace("=" * 60, conversation_id=trace_id)
    BackendObservability.trace(
        "PHASE C: Restoring all missing reviews", conversation_id=trace_id
    )
    BackendObservability.trace("=" * 60, conversation_id=trace_id)

    # Re-fetch live reviews for dedup
    live_reviews = await fetch_live_reviews(trace_id)
    live_ext_ids: set[str] = {
        r["externalSourceId"] for r in live_reviews if r.get("externalSourceId")
    }

    BackendObservability.trace(
        f"Dedup index: {len(live_ext_ids)} existing review externalSourceIds.",
        conversation_id=trace_id,
    )

    review_stats = {
        "total": len(backup_reviews),
        "matched": 0,
        "skipped_duplicate": 0,
        "skipped_no_match": 0,
        "pushed": 0,
        "errors": 0,
    }
    unmatched_listings_log: dict[str, str] = {}

    for i, review in enumerate(backup_reviews, start=1):
        backup_listing_id = review["listingId"]
        ext_source_id = review.get("externalSourceId", "")

        backup_listing = backup_id_to_listing.get(backup_listing_id)
        if not backup_listing:
            review_stats["skipped_no_match"] += 1
            continue

        key = build_name_city_key(backup_listing["name"], backup_listing["city"])
        live_listing_id = live_name_city_to_id.get(key)

        if not live_listing_id:
            if backup_listing_id not in unmatched_listings_log:
                unmatched_listings_log[backup_listing_id] = backup_listing[
                    "name"
                ]
                BackendObservability.error(
                    f"[{i}/{len(backup_reviews)}] No live listing match for "
                    f'"{backup_listing["name"]}" '
                    f"(city: {backup_listing['city']}). Skipping.",
                    conversation_id=trace_id,
                )
            review_stats["skipped_no_match"] += 1
            continue

        review_stats["matched"] += 1

        # Dedup by externalSourceId
        if ext_source_id and ext_source_id in live_ext_ids:
            review_stats["skipped_duplicate"] += 1
            continue

        payload = {
            "listingId": live_listing_id,
            "externalSourceId": ext_source_id,
            "authorName": review.get("authorName"),
            "rating": review.get("rating"),
            "text": review.get("text"),
            "publishedDate": review.get("publishedDate"),
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            await execute_graphql_operation("CreateReview", payload)
            review_stats["pushed"] += 1
            # Add to dedup set to avoid duplicate pushes within this run
            if ext_source_id:
                live_ext_ids.add(ext_source_id)
            if review_stats["pushed"] % 25 == 0:
                BackendObservability.trace(
                    f"Phase C progress: {review_stats['pushed']} reviews pushed "
                    f"({i}/{len(backup_reviews)} processed).",
                    conversation_id=trace_id,
                )
        except Exception as exc:
            err_msg = str(exc).lower()
            if (
                "unique" in err_msg
                or "constraint" in err_msg
                or "already exists" in err_msg
            ):
                review_stats["skipped_duplicate"] += 1
            else:
                review_stats["errors"] += 1
                BackendObservability.error(
                    f"[{i}/{len(backup_reviews)}] Failed to push review "
                    f"(externalSourceId={ext_source_id}): {exc}",
                    conversation_id=trace_id,
                )

    phase_c_summary = (
        f"\n{'=' * 60}\n"
        f"PHASE C COMPLETE — Review Restoration\n"
        f"{'=' * 60}\n"
        f"Total backup reviews:    {review_stats['total']}\n"
        f"Matched to live listing: {review_stats['matched']}\n"
        f"Skipped (duplicate):     {review_stats['skipped_duplicate']}\n"
        f"Skipped (no match):      {review_stats['skipped_no_match']}\n"
        f"Pushed (new):            {review_stats['pushed']}\n"
        f"Errors:                  {review_stats['errors']}\n"
        f"{'=' * 60}"
    )
    BackendObservability.trace(phase_c_summary, conversation_id=trace_id)
    print(phase_c_summary, file=sys.stderr)

    if unmatched_listings_log:
        BackendObservability.trace(
            f"\nStill-unmatched listings ({len(unmatched_listings_log)}):",
            conversation_id=trace_id,
        )
        for lid, name in unmatched_listings_log.items():
            BackendObservability.trace(
                f"  - {name} (backup ID: {lid})",
                conversation_id=trace_id,
            )

    # Final combined summary
    final = (
        f"\n{'=' * 60}\n"
        f"FULL RESTORE SUMMARY\n"
        f"{'=' * 60}\n"
        f"Listings re-created:        {listing_stats['created']}\n"
        f"Listing errors:             {listing_stats['errors']}\n"
        f"Reviews pushed:             {review_stats['pushed']}\n"
        f"Reviews skipped (dup):      {review_stats['skipped_duplicate']}\n"
        f"Reviews skipped (no match): {review_stats['skipped_no_match']}\n"
        f"Review errors:              {review_stats['errors']}\n"
        f"{'=' * 60}"
    )
    BackendObservability.trace(final, conversation_id=trace_id)
    print(final, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Full restore of ALL listings and reviews from backup."
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
        restore_all(
            reviews_backup_path=args.reviews_backup,
            listings_backup_path=args.listings_backup,
            trace_id=args.trace_id,
        )
    )


if __name__ == "__main__":
    main()
