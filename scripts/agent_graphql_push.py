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

async def main() -> None:
    parser = argparse.ArgumentParser(description="Push data to Fina DB via GraphQL.")
    parser.add_argument("--operation", type=str, required=True)
    parser.add_argument("--variables", type=str, required=True)
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(f"Starting agent_graphql_push.py with operation={args.operation}", conversation_id=args.trace_id)

    try:
        raw_variables = args.variables
        if raw_variables.startswith("@"):
            file_path = raw_variables[1:]
            BackendObservability.trace(f"Loading variables from file: '{file_path}'", conversation_id=args.trace_id)
            with open(file_path, "r") as f:
                raw_variables = f.read()

        vars_dict = json.loads(raw_variables)
        if not isinstance(vars_dict, dict):
            BackendObservability.fatal("Validation Error: Variables must be a JSON object/dictionary.", conversation_id=args.trace_id)
            sys.exit(1)
        BackendObservability.trace(f"Parsed variables: {vars_dict}", conversation_id=args.trace_id)
        if args.operation == "CreateListing":
            if "category" in vars_dict and "categories" not in vars_dict:
                cat = vars_dict.pop("category")
                vars_dict["categories"] = [cat] if cat else []
    except SystemExit:
        raise
    except Exception as e:
        BackendObservability.fatal(f"Error parsing variables JSON: {e}", exception=e, conversation_id=args.trace_id)
        sys.exit(1)

    if args.operation == "CreateListing":
        from features.scanning.dedup import check_duplicate, merge_listing_data
        
        city = vars_dict.get("city")
        name = vars_dict.get("name")
        description = vars_dict.get("description")
        
        if not name or not isinstance(name, str) or not name.strip():
            BackendObservability.fatal("Validation Error: 'name' is required and must be a non-empty string.", conversation_id=args.trace_id)
            sys.exit(1)
        if not city or not isinstance(city, str) or not city.strip():
            BackendObservability.fatal("Validation Error: 'city' is required and must be a non-empty string.", conversation_id=args.trace_id)
            sys.exit(1)
        if description is not None and not isinstance(description, str):
            BackendObservability.fatal("Validation Error: 'description' must be a string if provided.", conversation_id=args.trace_id)
            sys.exit(1)

        # 1. Deduplicate
        BackendObservability.trace(f"Deduplication check for listing name='{name}' in city='{city}'", conversation_id=args.trace_id)
        existing = await check_duplicate(name=name, city=city, description=description)
        
        if existing:
            BackendObservability.info(f"Duplicate found: existing listing ID='{existing['id']}'. Merging...", conversation_id=args.trace_id)
            # 2. Merge duplicate
            merged = merge_listing_data(existing, vars_dict)
            if merged != existing:
                BackendObservability.trace(f"Listing data changed. Pushing updates for listing ID={existing['id']}", conversation_id=args.trace_id)
                try:
                    await execute_graphql_operation(
                        operation_name="UpdateListingStatus",
                        variables={
                            "id": existing["id"],
                            "verificationStatus": merged.get("verificationStatus", "UNVERIFIED"),
                        },
                    )
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
                    BackendObservability.info(f"Successfully updated duplicate listing ID={existing['id']} data/status.", conversation_id=args.trace_id)
                except Exception as exc:
                    BackendObservability.error(
                        f"Failed to update duplicate listing data/status for ID {existing['id']}",
                        exception=exc,
                        conversation_id=args.trace_id
                    )
            else:
                BackendObservability.info(f"Duplicate listing ID={existing['id']} matches perfectly, no data/status updates needed.", conversation_id=args.trace_id)
            
            result = {"status": "MERGED", "existingId": existing["id"]}
            sys.stdout.write(json.dumps(result))
            return
            
        # 3. Create (Generate Embeddings + Geocode if missing)
        BackendObservability.info(f"No duplicate found for '{name}'. Preparing to create new listing...", conversation_id=args.trace_id)
        lat = vars_dict.get("latitude")
        lng = vars_dict.get("longitude")
        if lat is None or lng is None:
            from features.scanning.sources.geocoder import geocode_address
            addr = vars_dict.get("address") or city
            BackendObservability.trace(f"No coordinates provided. Geocoding address: '{addr}'", conversation_id=args.trace_id)
            lat, lng = await geocode_address(addr, city)
            vars_dict["latitude"] = lat
            vars_dict["longitude"] = lng
            BackendObservability.info(f"Geocoded address to coordinates: ({lat}, {lng})", conversation_id=args.trace_id)
            
        if not vars_dict.get("descriptionEmbedding"):
            from features.shared.embeddings import get_embedding
            desc = description or f"Filipino listing in {city}"
            BackendObservability.trace(f"Generating description embedding for: '{desc}'", conversation_id=args.trace_id)
            vars_dict["descriptionEmbedding"] = get_embedding(desc)
            BackendObservability.trace("Successfully generated description embedding.", conversation_id=args.trace_id)


        if not vars_dict.get("verificationStatus"):
            vars_dict["verificationStatus"] = "UNVERIFIED"

    BackendObservability.trace(f"Executing GraphQL operation: '{args.operation}' with variables: {vars_dict}", conversation_id=args.trace_id)
    result = await execute_graphql_operation(operation_name=args.operation, variables=vars_dict)
    BackendObservability.info(f"Successfully executed GraphQL operation: '{args.operation}'", conversation_id=args.trace_id)
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
