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
from features.shared.observability import BackendObservability

async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Fina listings for auditing.")
    parser.add_argument("--city", type=str, required=True, help="Target city to fetch listings for.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of listings to return.")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(
        f"Starting agent_audit_listings.py with city={args.city}, limit={args.limit}, offset={args.offset}",
        conversation_id=args.trace_id
    )

    # Query listings by city
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
        f"Retrieved {total_listings} listings for {args.city}. Returning slice of {len(listings_slice)} (offset {args.offset}).",
        conversation_id=args.trace_id
    )

    # Format listings to output
    formatted_listings = []
    for l in listings_slice:
        formatted_listings.append({
            "id": l.get("id"),
            "name": l.get("name"),
            "categories": l.get("categories", []),
            "description": l.get("description", ""),
            "tags": l.get("tags", "")
        })

    # Output JSON to stdout
    has_more = total_listings > args.offset + args.limit
    sys.stdout.write(json.dumps({
        "listings": formatted_listings,
        "total": total_listings,
        "has_more": has_more
    }))

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
