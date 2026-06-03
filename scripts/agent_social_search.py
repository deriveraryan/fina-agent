#!/usr/bin/env python3
"""CLI script to search Facebook/Instagram for Filipino community pages with pagination and caching.

Mirrors the agent_maps_fetch.py pattern: caches candidate URLs locally to avoid
redundant browser automation and prevent agent context bloat.

Usage:
    python scripts/agent_social_search.py --city SYDNEY --category COMMUNITY --platform facebook --limit 10 --offset 0
"""

import os
import sys
import json
import argparse
import asyncio

# Enable FINA_AGENT_CLI_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add functions path to python path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability



def _get_mock_candidates(city: str, category: str, platform: str) -> list[dict]:
    """Returns mock social page candidates for offline/TDD testing."""
    city_title = city.title()
    if platform == "facebook":
        return [
            {
                "url": f"https://facebook.com/mock-filipino-{category.lower()}-{city.lower()}-1",
                "name": f"Mock Filipino {category.title()} {city_title} 1",
                "description": f"A Filipino {category.lower()} community group in {city_title}.",
                "platform": "facebook"
            },
            {
                "url": f"https://facebook.com/mock-filipino-{category.lower()}-{city.lower()}-2",
                "name": f"Mock Filipino {category.title()} {city_title} 2",
                "description": f"Another Filipino {category.lower()} group in {city_title}.",
                "platform": "facebook"
            }
        ]
    elif platform == "instagram":
        return [
            {
                "url": f"https://instagram.com/mock-filipino-{category.lower()}-{city.lower()}-1",
                "name": f"Mock Filipino {category.title()} {city_title} IG",
                "description": f"A Filipino {category.lower()} Instagram page in {city_title}.",
                "platform": "instagram"
            }
        ]
    return []


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Facebook/Instagram for Filipino community pages with caching and pagination."
    )
    parser.add_argument("--city", type=str, required=True, help="Target city name.")
    parser.add_argument(
        "--category", type=str, required=True,
        choices=["RESTAURANT", "CAFE", "SHOP", "CHURCH", "GOVERNMENT", "COMMUNITY"],
        help="Target category."
    )
    parser.add_argument(
        "--platform", type=str, required=True,
        choices=["facebook", "instagram"],
        help="Social platform to search."
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of results to return.")
    parser.add_argument("--offset", type=int, default=0, help="Offset to start returning results from.")
    parser.add_argument("--refresh", action="store_true", help="Bypass local cache and search live.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(f"Starting agent_social_search.py with city={args.city}, category={args.category}, platform={args.platform}, limit={args.limit}, offset={args.offset}", conversation_id=args.trace_id)

    city_key = args.city.lower().replace(" ", "_")
    cat_key = args.category.lower()
    platform_key = args.platform.lower()

    # Save cache file in the .antigravity_saves directory
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.antigravity_saves"))
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"social_cache_{platform_key}_{city_key}_{cat_key}.json")

    candidates: list[dict] = []

    # Try cache hit
    if os.path.exists(cache_path) and not args.refresh:
        BackendObservability.trace(f"Cache file found: {cache_path}", conversation_id=args.trace_id)
        try:
            with open(cache_path, "r") as f:
                candidates = json.loads(f.read())
            BackendObservability.info(f"Cache hit: loaded {len(candidates)} candidates from local cache", conversation_id=args.trace_id)
        except Exception as exc:
            BackendObservability.warning(f"Failed to read cache from {cache_path}: {exc}", conversation_id=args.trace_id)
            candidates = []
    else:
        if args.refresh:
            BackendObservability.trace("Bypassing cache due to --refresh flag", conversation_id=args.trace_id)
        else:
            BackendObservability.trace(f"Cache file not found at {cache_path}", conversation_id=args.trace_id)

    # Cache miss — use mock candidates for now (live browser search is done by the subagent)
    if not candidates:
        BackendObservability.info("Cache miss. Fetching mock social candidates...", conversation_id=args.trace_id)
        candidates = _get_mock_candidates(args.city, args.category, args.platform)
        BackendObservability.trace(f"Loaded {len(candidates)} mock candidates.", conversation_id=args.trace_id)

        # Write to cache file
        try:
            with open(cache_path, "w") as f:
                f.write(json.dumps(candidates, indent=2))
            BackendObservability.trace(f"Successfully cached {len(candidates)} candidates at {cache_path}", conversation_id=args.trace_id)
        except Exception as exc:
            BackendObservability.warning(f"Error writing to cache file: {exc}", conversation_id=args.trace_id)

    # Fetch existing listings for deduplication
    BackendObservability.info(f"Fetching existing listings for city {args.city} to deduplicate candidates", conversation_id=args.trace_id)
    try:
        db_res = await execute_graphql_operation(
            operation_name="ListCitySocialUrls",
            variables={"city": args.city}
        )
        listings = db_res.get("data", {}).get("listings", [])
        existing_urls = set()
        for l in listings:
            if l.get("facebookUrl"):
                existing_urls.add(l["facebookUrl"].strip().lower())
            if l.get("instagramUrl"):
                existing_urls.add(l["instagramUrl"].strip().lower())
        BackendObservability.trace(f"Found {len(existing_urls)} existing social URLs in Listing database.", conversation_id=args.trace_id)
    except Exception as exc:
        BackendObservability.error(f"Failed to query existing social URLs: {exc}", exception=exc, conversation_id=args.trace_id)
        existing_urls = set()

    # Filter out candidates whose URL is already found in the database
    filtered_candidates = []
    for c in candidates:
        url = c.get("url", "").strip().lower()
        if url in existing_urls:
            BackendObservability.trace(f"Filtered out duplicate candidate URL: {url}", conversation_id=args.trace_id)
        else:
            filtered_candidates.append(c)
    
    dup_count = len(candidates) - len(filtered_candidates)
    BackendObservability.info(f"Deduplication completed. Filtered out {dup_count} duplicates. {len(filtered_candidates)} candidates remain.", conversation_id=args.trace_id)
    candidates = filtered_candidates

    # Apply pagination
    total = len(candidates)
    offset = args.offset
    limit = args.limit
    paginated = candidates[offset:offset + limit]
    has_more = offset + limit < total
    BackendObservability.info(f"Returning {len(paginated)}/{total} candidates (has_more={has_more})", conversation_id=args.trace_id)

    # Print JSON output to stdout
    output = {
        "candidates": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": has_more
    }
    sys.stdout.write(json.dumps(output))



if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
