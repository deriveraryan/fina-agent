import os
import sys
import argparse
import asyncio

# Add root folder to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from features.shared.graphql_client import execute_graphql_operation
from features.shared.embeddings import get_embedding
from features.shared.observability import BackendObservability

CITIES = ["SYDNEY", "MELBOURNE", "BRISBANE", "ADELAIDE", "PERTH", "HOBART", "DARWIN", "CANBERRA", "GOLD COAST", "NEWCASTLE"]

async def migrate_city(city: str, trace_id: str | None = None):
    BackendObservability.info(f"Fetching listings for {city}...", conversation_id=trace_id)
    try:
        res = await execute_graphql_operation("ListCityListings", {"city": city})
        listings = res.get("data", {}).get("listings", [])
        BackendObservability.info(f"Found {len(listings)} listings in {city}.", conversation_id=trace_id)
        
        for idx, listing in enumerate(listings):
            id_ = listing["id"]
            name = listing["name"]
            categories = listing.get("categories", [])
            description = listing.get("description", "")
            
            # Generate embedding text
            cats_str = ",".join(categories or [])
            base_desc = f"{name} is a Filipino {cats_str} located in {city}."
            embedding_text = f"{base_desc} {description}" if description else base_desc
            
            BackendObservability.trace(f"[{idx+1}/{len(listings)}] Generating embedding for '{name}'...", conversation_id=trace_id)
            embedding = get_embedding(embedding_text, conversation_id=trace_id)
            if not embedding:
                BackendObservability.warning(f"Failed to generate embedding for '{name}' (ID: {id_})", conversation_id=trace_id)
                continue
                
            # Update embedding in database
            BackendObservability.trace(f"Updating '{name}' in database...", conversation_id=trace_id)
            await execute_graphql_operation("UpdateListingData", {
                "id": id_,
                "descriptionEmbedding": embedding
            })
            BackendObservability.info(f"Successfully updated '{name}' (ID: {id_}).", conversation_id=trace_id)
            
            # Respect rate limit (0.2s delay as agreed)
            await asyncio.sleep(0.2)
            
    except Exception as e:
        BackendObservability.error(f"Error migrating {city}: {e}", exception=e, conversation_id=trace_id)

async def main():
    parser = argparse.ArgumentParser(description="One-time vector embedding migration script.")
    parser.add_argument("--city", type=str, help="Specific city to migrate (optional).")
    parser.add_argument("--trace-id", type=str, help="Trace correlation ID (optional).")
    args = parser.parse_args()

    trace_id = args.trace_id
    BackendObservability.info("Starting vector embedding migration...", conversation_id=trace_id)
    
    cities_to_migrate = [args.city.upper()] if args.city else CITIES
    for city in cities_to_migrate:
        await migrate_city(city, trace_id=trace_id)
        
    BackendObservability.info("Migration complete!", conversation_id=trace_id)

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
