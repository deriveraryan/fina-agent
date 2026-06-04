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
    parser.add_argument("--type", choices=["missing-social", "business-socials"], required=True)
    parser.add_argument("--city", type=str, default=None)
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
        BackendObservability.trace(f"Executing GraphQL operation ListCityListings with variables: {{'city': '{args.city}'}}", conversation_id=args.trace_id)
        result = await execute_graphql_operation(operation_name="ListCityListings", variables={"city": args.city})
        listings = result.get("data", {}).get("listings", [])
        urls = []
        for l in listings:
            if l.get("facebookUrl"):
                urls.append(l["facebookUrl"])
            if l.get("instagramUrl"):
                urls.append(l["instagramUrl"])
        BackendObservability.info(f"Retrieved {len(listings)} listings for {args.city}, extracted {len(urls)} social media URLs.", conversation_id=args.trace_id)
        sys.stdout.write(json.dumps(urls))

if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
