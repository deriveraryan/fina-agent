#!/usr/bin/env python3
"""CLI agent script to generate and back-fill vector embeddings for listings missing them."""
import os
import sys
import json
import argparse
import asyncio
# Enable FINA_AGENT_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add parent directory to path to allow importing modules
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.graphql_client import execute_graphql_operation
from features.shared.embeddings import get_embedding
from features.shared.observability import BackendObservability

async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate vector description embeddings for listings missing them.")
    parser.add_argument("--city", type=str, required=True, help="Target city (e.g. SYDNEY, MELBOURNE).")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on the number of listings to process.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    city_upper = args.city.upper()
    BackendObservability.info(
        f"Starting agent_generate_embeddings.py for city={city_upper}, limit={args.limit}",
        conversation_id=args.trace_id
    )

    try:
        BackendObservability.trace(
            f"Querying ListListingsMissingEmbedding for city={city_upper}",
            conversation_id=args.trace_id
        )
        res = await execute_graphql_operation("ListListingsMissingEmbedding", {"city": city_upper})
        listings = res.get("data", {}).get("listings", [])
    except Exception as e:
        BackendObservability.fatal(
            f"Failed to query listings missing embedding: {e}",
            exception=e,
            conversation_id=args.trace_id
        )
        sys.exit(1)

    total_missing = len(listings)
    BackendObservability.info(
        f"Found {total_missing} listings missing descriptionEmbedding in {city_upper}.",
        conversation_id=args.trace_id
    )

    if args.limit is not None:
        listings = listings[:args.limit]
        BackendObservability.info(
            f"Limiting execution run to process {len(listings)} listings.",
            conversation_id=args.trace_id
        )

    processed_count = 0
    generated_count = 0
    error_count = 0
    updated_listings = []

    for idx, listing in enumerate(listings):
        listing_id = listing.get("id")
        name = listing.get("name")
        categories = listing.get("categories", [])
        description = listing.get("description", "")

        processed_count += 1
        
        # Build standard composite text template for embedding
        cats_str = ",".join(categories or [])
        base_desc = f"{name} is a Filipino {cats_str} located in {city_upper}."
        embedding_text = f"{base_desc} {description}" if description else base_desc

        BackendObservability.trace(
            f"[{idx+1}/{len(listings)}] Generating embedding for '{name}' (ID: {listing_id})",
            conversation_id=args.trace_id
        )
        
        try:
            embedding = get_embedding(embedding_text, conversation_id=args.trace_id)
            if not embedding:
                BackendObservability.warning(
                    f"Embedding generation returned empty for '{name}'",
                    conversation_id=args.trace_id
                )
                error_count += 1
                continue

            BackendObservability.trace(
                f"Updating descriptionEmbedding for '{name}' in database...",
                conversation_id=args.trace_id
            )
            
            await execute_graphql_operation("UpdateListingData", {
                "id": listing_id,
                "descriptionEmbedding": embedding
            })
            
            generated_count += 1
            updated_listings.append({"id": listing_id, "name": name})
            BackendObservability.info(
                f"Successfully updated descriptionEmbedding for '{name}'",
                conversation_id=args.trace_id
            )
        except Exception as e:
            BackendObservability.error(
                f"Failed to generate/update embedding for '{name}': {e}",
                exception=e,
                conversation_id=args.trace_id
            )
            error_count += 1

        # Respect API rate limits with 0.2s pause
        await asyncio.sleep(0.2)

    # Output JSON summary to stdout
    sys.stdout.write(json.dumps({
        "listings_missing": total_missing,
        "listings_processed": processed_count,
        "embeddings_generated": generated_count,
        "errors_encountered": error_count,
        "updated_listings": updated_listings
    }))

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
