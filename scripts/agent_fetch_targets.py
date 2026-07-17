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
    parser = argparse.ArgumentParser(description="Fetch Fina target listings from DB.")
    parser.add_argument("--type", choices=["missing-social", "business-socials", "city-listings", "all-city-listings", "social-post-tracker"], required=True)
    parser.add_argument("--city", type=str, default=None)
    parser.add_argument("--listing-id", type=str, default=None, help="Listing UUID for social-post-tracker query.")
    parser.add_argument("--platform", choices=["facebook", "instagram", "tiktok", "FACEBOOK", "INSTAGRAM", "TIKTOK"], type=str, default=None, help="Platform for social-post-tracker query.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(f"Starting agent_fetch_targets.py with type={args.type}, city={args.city}", conversation_id=args.trace_id)

    if args.type == "missing-social":
        variables = {}
        if args.city:
            variables["city"] = args.city
        BackendObservability.trace(f"Executing GraphQL operation ListListingsMissingSocial with variables: {variables}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(operation_name="ListListingsMissingSocial", variables=variables)
        listings = result.get("data", {}).get("listings", [])
        BackendObservability.info(f"Retrieved {len(listings)} listings missing social media links.", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(listings))
    elif args.type == "business-socials":
        if not args.city:
            BackendObservability.fatal("Validation Error: --city is required for business-socials", conversation_id=args.trace_id)
            sys.exit(1)
        BackendObservability.trace(f"Executing GraphQL operation ListAdminListings with variables: {{'city': '{args.city}', 'limit': 2000}}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(
            operation_name="ListAdminListings",
            variables={
                "city": args.city,
                "limit": 2000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED"]
            }
        )
        listings = result.get("data", {}).get("listings", [])
        targets = []
        for l in listings:
            if l.get("facebookUrl"):
                targets.append({"id": l["id"], "url": l["facebookUrl"]})
            if l.get("instagramUrl"):
                targets.append({"id": l["id"], "url": l["instagramUrl"]})
            if l.get("tiktokUrl"):
                targets.append({"id": l["id"], "url": l["tiktokUrl"]})
        BackendObservability.info(f"Retrieved {len(listings)} listings for {args.city}, extracted {len(targets)} social media targets.", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(targets))
    elif args.type == "city-listings":
        if not args.city:
            BackendObservability.fatal("Validation Error: --city is required for city-listings", conversation_id=args.trace_id)
            sys.exit(1)
        BackendObservability.trace(f"Executing GraphQL operation ListAdminListings with variables: {{'city': '{args.city}', 'limit': 2000}}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(
            operation_name="ListAdminListings",
            variables={
                "city": args.city,
                "limit": 2000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED", "FLAGGED"]
            }
        )
        listings = result.get("data", {}).get("listings", [])
        BackendObservability.info(f"Retrieved {len(listings)} listings for {args.city} deduplication context.", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(listings))
    elif args.type == "all-city-listings":
        if not args.city:
            BackendObservability.fatal("Validation Error: --city is required for all-city-listings", conversation_id=args.trace_id)
            sys.exit(1)
        BackendObservability.trace(f"Executing GraphQL operation ListAdminListings (all statuses) with variables: {{'city': '{args.city}', 'limit': 2000}}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(
            operation_name="ListAdminListings",
            variables={
                "city": args.city,
                "limit": 2000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED", "FLAGGED"]
            }
        )
        listings = result.get("data", {}).get("listings", [])
        BackendObservability.info(f"Retrieved {len(listings)} listings (all statuses) for {args.city} deduplication context.", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(listings))
    elif args.type == "social-post-tracker":
        if not args.listing_id or not args.platform:
            BackendObservability.fatal("Validation Error: --listing-id and --platform are required for social-post-tracker", conversation_id=args.trace_id)
            sys.exit(1)
        platform_upper = args.platform.upper()
        variables = {
            "listingId": args.listing_id,
            "platform": platform_upper
        }
        BackendObservability.trace(f"Executing GraphQL operation GetSocialPostTracker with variables: {variables}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(operation_name="GetSocialPostTracker", variables=variables)
        trackers = result.get("data", {}).get("socialPostTrackers", [])
        output_data = trackers[0] if trackers else None
        BackendObservability.info(f"Retrieved social post tracker for listing={args.listing_id}, platform={platform_upper}. Found: {output_data is not None}", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(output_data))

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
