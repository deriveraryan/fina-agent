"""Shared database fetch utilities for task generation scripts.

Provides common async functions for fetching listings from the database,
used by multiple task manager CLI scripts to avoid code duplication.
"""

from features.shared.observability import BackendObservability


async def fetch_city_listings(city: str, trace_id: str | None = None) -> list[dict]:
    """Fetch all listings for a city from the database via ListAdminListings.

    Retrieves both VERIFIED and UNVERIFIED listings to ensure comprehensive
    coverage across discovery, enrichment, and events workflows.

    Args:
        city: Target city name (e.g. "Sydney").
        trace_id: Trace correlation ID for observability.

    Returns:
        A list of listing dictionaries.
    """
    BackendObservability.trace(
        f"Fetching all listings for city={city} via ListAdminListings",
        conversation_id=trace_id,
    )
    from features.shared.graphql_client import execute_graphql_operation
    result = await execute_graphql_operation(
        operation_name="ListAdminListings",
        variables={
            "city": city,
            "limit": 2000,
            "verificationStatuses": ["VERIFIED", "UNVERIFIED"],
        },
    )
    listings = result.get("data", {}).get("listings", [])
    BackendObservability.info(
        f"Retrieved {len(listings)} listings for {city}.",
        conversation_id=trace_id,
    )
    return listings
