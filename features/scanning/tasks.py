"""Core task orchestration for directory scanning pipelines.

Implements the dual-mode pattern (Rule 1.14): standalone async functions
that are callable from both Cloud Scheduler triggers and the local
Antigravity runner. Scans external sources, deduplicates results,
and writes new listings/events to SQL Connect via GraphQL mutations.
"""

import os
import time
from datetime import datetime
from typing import Any

from features.scanning.sources.social_scanner import scrape_social_events
from features.scanning.sources.geocoder import geocode_address
from features.scanning.dedup import check_duplicate, merge_listing_data
from features.shared.observability import BackendObservability
from features.shared.graphql_client import execute_graphql_operation

CITIES: list[str] = [
    "SYDNEY",
    "MELBOURNE",
    "BRISBANE",
    "PERTH",
    "ADELAIDE",
    "DARWIN",
    "HOBART",
    "CANBERRA",
    "GOLD_COAST",
]

LISTING_CATEGORIES: list[str] = ["RESTAURANT", "CAFE", "SHOP", "CHURCH", "COMMUNITY", "GOVERNMENT"]




# ─── Event Scan Pipeline ──────────────────────────────────


async def run_event_scan_all_cities() -> None:
    """Iterates all target cities and runs the event scan pipeline for each."""
    BackendObservability.info("Starting event scan across all cities.")
    for city in CITIES:
        try:
            result = await scan_city_events(city)
            BackendObservability.info(
                f"Event scan completed for {city}.",
                found=result.get("found", 0),
                created=result.get("created", 0),
            )
        except Exception as exc:
            BackendObservability.error(
                f"Event scan failed for {city}.", exception=exc
            )


async def scan_city_events(city: str) -> dict[str, int]:
    """Retrieves verified local directories, crawls their social profiles, and indexes events.

    Args:
        city: Target city identifier (e.g. 'SYDNEY').

    Returns:
        Summary dict with keys: found, created, updated, duration_ms.
    """
    start_ms = time.perf_counter()
    found = 0
    created = 0
    updated = 0
    flagged = 0
    status = "SUCCESS"
    error_message: str | None = None

    try:
        # 1. Fetch listings currently present in the city
        response = await execute_graphql_operation(
            operation_name="ListListings",
            variables={"city": city},
        )
        listings = ((response or {}).get("data") or {}).get("listings") or []

        # Filter listings to only verify events from highly credible (VERIFIED) social pages
        verified_social_listings = [
            l for l in listings
            if l.get("verificationStatus") == "VERIFIED" and l.get("sourceUrl")
        ]

        BackendObservability.info(
            f"Found {len(verified_social_listings)} verified organizations in {city} to scan for events."
        )

        for listing in verified_social_listings:
            profile_url = listing["sourceUrl"]
            
            # Scrape event data directly from this organization's page
            raw_events = await scrape_social_events(profile_url, city)
            found += len(raw_events)

            for event in raw_events:
                existing = await check_duplicate(
                    name=event["name"],
                    city=city,
                    description=event.get("description"),
                )

                if existing:
                    updated += 1
                else:
                    # Resolve event street address to exact coordinates
                    event_address = event.get("address") or listing["address"]
                    lat, lng = await geocode_address(event_address, city)
                    from features.shared.embeddings import get_embedding
                    desc = event.get("description") or f"Filipino community event in {city.lower()}."
                    vector = get_embedding(desc)

                    await execute_graphql_operation(
                        operation_name="CreateEvent",
                        variables={
                            "name": event["name"],
                            "city": city,
                            "description": desc,
                            "imageUrl": event.get("imageUrl"),
                            "venueName": event.get("venueName") or listing["name"],
                            "address": event_address,
                            "latitude": lat,
                            "longitude": lng,
                            "startDate": event["startDate"],
                            "endDate": event.get("endDate"),
                            "isRecurring": event.get("isRecurring", False),
                            "recurrenceRule": event.get("recurrenceRule"),
                            "website": event.get("website") or profile_url,
                            "facebookUrl": profile_url if "facebook.com" in profile_url else None,
                            "sourceUrl": profile_url,
                            "tags": event.get("tags", "filipino,community,social"),
                            "verificationStatus": "VERIFIED", # Auto-trusted since source is verified!
                            "descriptionEmbedding": vector,
                        },
                    )
                    created += 1
    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
        BackendObservability.error(
            f"Event scan pipeline error for {city}.", exception=exc
        )

    duration_ms = int((time.perf_counter() - start_ms) * 1000)

    try:
        await execute_graphql_operation(
            operation_name="LogAgentScan",
            variables={
                "city": city,
                "source": "FACEBOOK",
                "scanType": "EVENT",
                "listingsFound": found,
                "listingsCreated": created,
                "listingsUpdated": updated,
                "listingsFlagged": flagged,
                "durationMs": duration_ms,
                "status": status,
                "errorMessage": error_message,
            },
        )
    except Exception as log_exc:
        BackendObservability.error(
            f"Failed to log event scan results for {city}.", exception=log_exc
        )

    return {
        "found": found,
        "created": created,
        "updated": updated,
        "duration_ms": duration_ms,
    }


# ─── Google Maps Scan Pipeline ─────────────────────────────


async def run_maps_scan_all_cities() -> dict[str, dict[str, Any]]:
    """Iterates all target cities and runs the Google Maps Places scan pipeline for each."""
    BackendObservability.info("Starting Google Maps places scan across all cities.")
    results = {}
    for city in CITIES:
        try:
            result = await scan_city_maps_listings(city)
            BackendObservability.info(
                f"Google Maps scan completed for {city}.",
                found=result.get("found", 0),
                created=result.get("created", 0),
                updated=result.get("updated", 0),
            )
            results[city] = result
        except Exception as exc:
            BackendObservability.error(
                f"Google Maps scan failed for {city}.", exception=exc
            )
            results[city] = {"error": str(exc)}
    return results


async def scan_city_maps_listings(city: str) -> dict[str, int]:
    """Scans Google Places for Filipino businesses/churches, deduplicates, and persists them.

    Args:
        city: Target city identifier (e.g. 'SYDNEY').

    Returns:
        Summary dict with keys: found, created, updated, flagged, duration_ms.
    """
    start_ms = time.perf_counter()
    found = 0
    created = 0
    updated = 0
    flagged = 0
    status = "SUCCESS"
    error_message: str | None = None

    try:
        from features.scanning.sources.maps_scanner import discover_places_listings

        for category in LISTING_CATEGORIES:
            raw_listings = await discover_places_listings(city, category)
            found += len(raw_listings)

            for listing in raw_listings:
                existing = await check_duplicate(
                    name=listing["name"],
                    city=city,
                    description=listing.get("description"),
                )

                if existing:
                    merged = merge_listing_data(existing, listing)
                    if merged != existing:
                        await execute_graphql_operation(
                            operation_name="UpdateListingData",
                            variables={
                                "id": existing["id"],
                                "categories": merged.get("categories"),
                                "phone": merged.get("phone"),
                                "website": merged.get("website"),
                                "facebookUrl": merged.get("facebookUrl"),
                                "instagramUrl": merged.get("instagramUrl"),
                                "tiktokUrl": merged.get("tiktokUrl"),
                                "operatingHours": merged.get("operatingHours"),
                                "imageUrl": merged.get("imageUrl"),
                                "tags": merged.get("tags"),
                                "sourceUrl": merged.get("sourceUrl"),
                            },
                        )
                        updated += 1
                else:
                    from features.shared.embeddings import get_embedding
                    desc = listing.get("description") or f"A Filipino {category.lower()} in {city.lower()}."
                    vector = get_embedding(desc)
                    await execute_graphql_operation(
                        operation_name="CreateListing",
                        variables={
                            "name": listing["name"],
                            "categories": [listing.get("category", category)],
                            "city": city,
                            "description": desc,
                            "address": listing["address"],
                            "latitude": listing["latitude"],
                            "longitude": listing["longitude"],
                            "phone": listing.get("phone"),
                            "website": listing.get("website"),
                            "facebookUrl": listing.get("facebookUrl"),
                            "instagramUrl": listing.get("instagramUrl"),
                            "tiktokUrl": None,
                            "operatingHours": listing.get("operatingHours"),
                            "imageUrl": listing.get("imageUrl"),
                            "tags": listing.get("tags"),
                            "sourceUrl": listing.get("sourceUrl"),
                            "verificationStatus": "UNVERIFIED",
                            "descriptionEmbedding": vector,
                        },
                    )
                    created += 1

    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
        BackendObservability.error(
            f"Google Maps scan pipeline error for {city}.", exception=exc
        )

    duration_ms = int((time.perf_counter() - start_ms) * 1000)

    # Log scan metadata
    try:
        await execute_graphql_operation(
            operation_name="LogAgentScan",
            variables={
                "city": city,
                "source": "GOOGLE_MAPS",
                "scanType": "LISTING",
                "listingsFound": found,
                "listingsCreated": created,
                "listingsUpdated": updated,
                "listingsFlagged": flagged,
                "durationMs": duration_ms,
                "status": status,
                "errorMessage": error_message,
            },
        )
    except Exception as log_exc:
        BackendObservability.error(
            f"Failed to log scan results for {city}.", exception=log_exc
        )

    return {
        "found": found,
        "created": created,
        "updated": updated,
        "flagged": flagged,
        "duration_ms": duration_ms,
    }


async def run_social_enrich_all_cities(platforms: list[str]) -> None:
    """Iterates all target cities and runs the social media URL enrichment pipeline for each."""
    BackendObservability.info(f"Starting social media URL enrichment task for platforms: {platforms}")
    
    for city in CITIES:
        try:
            result = await enrich_city_social_urls(city, platforms)
            BackendObservability.info(
                f"Social media enrichment completed for {city}.",
                found=result.get("found", 0),
                updated=result.get("updated", 0),
                status=result.get("status", "SUCCESS")
            )
        except Exception as exc:
            BackendObservability.error(
                f"Social media enrichment failed for {city}.", exception=exc
            )
            
    # Clean up the shared crawler at the very end
    try:
        from features.scanning.sources.social_enricher import close_crawler
        await close_crawler()
    except Exception as exc:
        BackendObservability.error("Failed to close Crawl4AI crawler at end of run", exception=exc)


async def enrich_city_social_urls(city: str, platforms: list[str]) -> dict[str, int]:
    """Fetches all listings in a city missing social urls and enriches them via Crawl4AI/browser-use.

    Args:
        city: City identifier (e.g. 'SYDNEY').
        platforms: List of social networks to enrich (e.g. ['facebook', 'instagram', 'tiktok']).

    Returns:
        A dict of scan statistics: found, updated, duration_ms, status.
    """
    start_ms = time.perf_counter()
    found = 0
    updated = 0
    status = "SUCCESS"
    error_message: str | None = None

    try:
        # Fetch listings missing at least one social media URL
        response = await execute_graphql_operation(
            operation_name="ListListingsMissingSocial",
            variables={"city": city}
        )
        listings = ((response or {}).get("data") or {}).get("listings") or []

        # Client-side filter to only listings that actually miss URLs for the REQUESTED platforms
        target_listings = []
        for l in listings:
            missing_any = False
            for p in platforms:
                if not l.get(f"{p}Url"):
                    missing_any = True
                    break
            if missing_any:
                target_listings.append(l)

        BackendObservability.info(
            f"Found {len(target_listings)} listings in {city} missing social URLs for target platforms: {platforms}"
        )

        from features.scanning.sources.social_enricher import enrich_listing_social

        for listing in target_listings:
            try:
                # Perform enrichment lookup
                enriched_urls = await enrich_listing_social(listing, platforms)
                
                # Check if any new URLs were discovered
                has_updates = False
                facebook_url = listing.get("facebookUrl")
                instagram_url = listing.get("instagramUrl")
                tiktok_url = listing.get("tiktokUrl")

                if enriched_urls.get("facebookUrl") and enriched_urls["facebookUrl"] != facebook_url:
                    facebook_url = enriched_urls["facebookUrl"]
                    has_updates = True
                if enriched_urls.get("instagramUrl") and enriched_urls["instagramUrl"] != instagram_url:
                    instagram_url = enriched_urls["instagramUrl"]
                    has_updates = True
                if enriched_urls.get("tiktokUrl") and enriched_urls["tiktokUrl"] != tiktok_url:
                    tiktok_url = enriched_urls["tiktokUrl"]
                    has_updates = True

                if has_updates:
                    found += 1
                    # Save enriched urls back to the database
                    await execute_graphql_operation(
                        operation_name="UpdateListingSocialUrls",
                        variables={
                            "id": listing["id"],
                            "facebookUrl": facebook_url,
                            "instagramUrl": instagram_url,
                            "tiktokUrl": tiktok_url,
                        }
                    )
                    updated += 1
                    BackendObservability.info(
                        f"Successfully enriched social URLs for listing '{listing['name']}': fb={facebook_url}, ig={instagram_url}, tt={tiktok_url}"
                    )
            except Exception as item_exc:
                BackendObservability.error(
                    f"Failed to enrich social URLs for listing '{listing.get('name')}' ({listing.get('id')})",
                    exception=item_exc
                )

    except Exception as exc:
        status = "FAILED"
        error_message = str(exc)
        BackendObservability.error(
            f"Social enrichment pipeline failed for city {city}.", exception=exc
        )

    duration_ms = int((time.perf_counter() - start_ms) * 1000)

    # Log agent scan log
    try:
        await execute_graphql_operation(
            operation_name="LogAgentScan",
            variables={
                "city": city,
                "source": "GOOGLE_SEARCH",
                "scanType": "SOCIAL_ENRICH",
                "listingsFound": found,
                "listingsCreated": 0,
                "listingsUpdated": updated,
                "listingsFlagged": 0,
                "durationMs": duration_ms,
                "status": status,
                "errorMessage": error_message,
            }
        )
    except Exception as log_exc:
        BackendObservability.error("Failed to log agent scan log for enrichment.", exception=log_exc)

    return {
        "found": found,
        "updated": updated,
        "duration_ms": duration_ms,
        "status": status,
    }


