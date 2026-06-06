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

async def process_single_item(operation: str, item_dict: dict, trace_id: str) -> dict:
    if operation == "CreateListing":
        if "category" in item_dict and "categories" not in item_dict:
            cat = item_dict.pop("category")
            item_dict["categories"] = [cat] if cat else []
        if "tags" in item_dict and isinstance(item_dict["tags"], list):
            item_dict["tags"] = ",".join([str(t) for t in item_dict["tags"]])

    reviews_to_push = []
    if operation == "CreateListing":
        from features.scanning.dedup import check_duplicate, merge_listing_data
        
        reviews_to_push = item_dict.pop("reviews", [])
        
        city = item_dict.get("city")
        name = item_dict.get("name")
        description = item_dict.get("description")
        source_url = item_dict.get("sourceUrl")
        
        if not name or not isinstance(name, str) or not name.strip():
            BackendObservability.error("Validation Error: 'name' is required and must be a non-empty string.", conversation_id=trace_id)
            return {"error": "Validation Error: 'name' is required"}
        if not city or not isinstance(city, str) or not city.strip():
            BackendObservability.error("Validation Error: 'city' is required and must be a non-empty string.", conversation_id=trace_id)
            return {"error": "Validation Error: 'city' is required"}
        if description is not None and not isinstance(description, str):
            BackendObservability.error("Validation Error: 'description' must be a string if provided.", conversation_id=trace_id)
            return {"error": "Validation Error: 'description' must be a string"}

        # 1. Deduplicate
        BackendObservability.trace(f"Deduplication check for listing name='{name}' in city='{city}'", conversation_id=trace_id)
        existing = await check_duplicate(
            name=name,
            city=city,
            description=description,
            source_url=source_url,
            categories=item_dict.get("categories", []),
            trace_id=trace_id,
        )
        
        if existing:
            BackendObservability.info(f"Duplicate found: existing listing ID='{existing['id']}'. Merging...", conversation_id=trace_id)
            # 2. Merge duplicate
            merged = merge_listing_data(existing, item_dict)
            if merged != existing:
                BackendObservability.trace(f"Listing data changed. Pushing updates for listing ID={existing['id']}", conversation_id=trace_id)
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
                            "status": merged.get("status"),
                        },
                    )
                    BackendObservability.info(f"Successfully updated duplicate listing ID={existing['id']} data/status.", conversation_id=trace_id)
                except Exception as exc:
                    BackendObservability.error(
                        f"Failed to update duplicate listing data/status for ID {existing['id']}",
                        exception=exc,
                        conversation_id=trace_id
                    )
            else:
                BackendObservability.info(f"Duplicate listing ID={existing['id']} matches perfectly, no data/status updates needed.", conversation_id=trace_id)
            
            for rev in reviews_to_push:
                try:
                    await execute_graphql_operation("CreateReview", {**rev, "listingId": existing["id"]})
                except Exception as exc:
                    BackendObservability.error(f"Failed to push review for duplicate listing ID={existing['id']}", exception=exc, conversation_id=trace_id)
                    
            return {"status": "MERGED", "existingId": existing["id"]}
            
        # 3. Create (Generate Embeddings + Geocode if missing)
        BackendObservability.info(f"No duplicate found for '{name}'. Preparing to create new listing...", conversation_id=trace_id)
        lat = item_dict.get("latitude")
        lng = item_dict.get("longitude")
        if lat is None or lng is None:
            from features.scanning.sources.geocoder import geocode_address
            addr = item_dict.get("address") or city
            BackendObservability.trace(f"No coordinates provided. Geocoding address: '{addr}'", conversation_id=trace_id)
            lat, lng = await geocode_address(addr, city)
            item_dict["latitude"] = lat
            item_dict["longitude"] = lng
            BackendObservability.info(f"Geocoded address to coordinates: ({lat}, {lng})", conversation_id=trace_id)
            
        if not item_dict.get("descriptionEmbedding"):
            from features.shared.embeddings import get_embedding
            cats_str = ",".join(item_dict.get("categories", []))
            base_desc = f"{name} is a Filipino {cats_str} located in {city}."
            desc_for_embedding = f"{base_desc} {description}" if description else base_desc
            BackendObservability.trace(f"Generating description embedding for: '{desc_for_embedding}'", conversation_id=trace_id)
            emb = get_embedding(desc_for_embedding, conversation_id=trace_id)
            if emb is not None:
                item_dict["descriptionEmbedding"] = emb
                BackendObservability.trace("Successfully generated description embedding.", conversation_id=trace_id)
            else:
                BackendObservability.warning("Could not generate description embedding. Proceeding without descriptionEmbedding.", conversation_id=trace_id)

        if not item_dict.get("verificationStatus"):
            item_dict["verificationStatus"] = "UNVERIFIED"

    BackendObservability.trace(f"Executing GraphQL operation: '{operation}' with variables: {item_dict}", conversation_id=trace_id)
    result = await execute_graphql_operation(operation_name=operation, variables=item_dict)
    BackendObservability.info(f"Successfully executed GraphQL operation: '{operation}'", conversation_id=trace_id)
    
    if operation == "CreateListing":
        new_id = result.get("data", {}).get("createListing", {}).get("id") or result.get("data", {}).get("listing_insert", {}).get("id")
        if new_id:
            for rev in reviews_to_push:
                try:
                    await execute_graphql_operation("CreateReview", {**rev, "listingId": new_id})
                except Exception as exc:
                    BackendObservability.error(f"Failed to push review for new listing ID={new_id}", exception=exc, conversation_id=trace_id)

    return result


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

        vars_parsed = json.loads(raw_variables)
    except Exception as e:
        BackendObservability.fatal(f"Error reading/parsing variables: {e}", exception=e, conversation_id=args.trace_id)
        sys.exit(1)

    is_bulk = isinstance(vars_parsed, list)
    items_to_process = vars_parsed if is_bulk else [vars_parsed]

    if not items_to_process or not isinstance(items_to_process[0], dict):
        BackendObservability.fatal("Validation Error: Variables must be a JSON object or a list of JSON objects.", conversation_id=args.trace_id)
        sys.exit(1)
        
    actual_op = args.operation
    if is_bulk and args.operation == "BulkCreateListing":
        actual_op = "CreateListing"

    if actual_op == "CreateListing":
        from features.scanning.heuristics import should_exclude_listing
        from features.scanning.dedup import deduplicate_batch
        
        valid_items = []
        for item in items_to_process:
            if not should_exclude_listing(item):
                valid_items.append(item)
                
        if is_bulk:
            items_to_process = deduplicate_batch(valid_items)
            BackendObservability.info(f"Bulk payload filtered and deduped from {len(vars_parsed)} down to {len(items_to_process)} items.", conversation_id=args.trace_id)
        else:
            items_to_process = valid_items

    results = []
    has_error = False
    for item_dict in items_to_process:
        try:
            res = await process_single_item(actual_op, item_dict, args.trace_id)
            if "error" in res:
                has_error = True
            results.append(res)
        except Exception as e:
            BackendObservability.error(f"GraphQL push operation failed for an item: {e}", exception=e, conversation_id=args.trace_id)
            results.append({"error": str(e)})
            has_error = True

    if is_bulk:
        sys.stdout.write(json.dumps(results))
    else:
        sys.stdout.write(json.dumps(results[0] if results else {"status": "SKIPPED"}))

    # Clean up the temporary variables file if one was used and execution succeeded
    if args.variables.startswith("@") and not has_error:
        file_path = args.variables[1:]
        try:
            os.remove(file_path)
            BackendObservability.trace(f"Cleaned up temporary variables file: {file_path}", conversation_id=args.trace_id)
        except Exception as e:
            BackendObservability.warning(f"Failed to clean up temporary variables file {file_path}: {e}", conversation_id=args.trace_id)

    if has_error and not is_bulk:
        sys.exit(1)


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
