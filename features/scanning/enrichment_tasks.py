"""Module to manage the task-based state machine for the listing enrichment agent.

Generates one enrichment task per existing database listing for a city.
Provides enrichment-specific metric constants and task building.
Lifecycle functions are imported from task_lifecycle.
"""

from typing import Any, Dict, List, Sequence, Set


# Enrichment-specific metric and state field definitions
ENRICHMENT_ALLOWED_METRICS: Set[str] = {
    "listings_enriched",
    "reviews_extracted",
    "reviews_pushed",
    "socials_enriched",
    "descriptions_rewritten",
    "maps_visits",
}

ENRICHMENT_METRIC_FIELDS: Sequence[str] = (
    "listings_enriched",
    "reviews_extracted",
    "reviews_pushed",
    "socials_enriched",
    "descriptions_rewritten",
    "maps_visits",
)

ENRICHMENT_MUTABLE_FIELDS: Sequence[str] = (
    "status",
    "started_at",
    "completed_at",
    "listings_enriched",
    "reviews_extracted",
    "reviews_pushed",
    "socials_enriched",
    "descriptions_rewritten",
    "maps_visits",
    "errors",
)


def generate_enrichment_tasks(
    listings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert a list of listing dicts into enrichment task dicts.

    Each listing becomes exactly one task. The task captures the listing's
    identity, current description, source URL, and existing social URLs so
    the enrichment agent can skip already-filled fields and use the current
    description as synthesis input.

    Args:
        listings: A list of listing dictionaries as returned by the
            ``ListAdminListings`` GraphQL query.

    Returns:
        A list of task dictionaries, each with tracking metadata and
        metric fields initialised to zero.
    """
    tasks: List[Dict[str, Any]] = []

    for listing in listings:
        task = _build_enrichment_task(listing)
        tasks.append(task)

    return tasks


def _build_enrichment_task(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Build a single enrichment task dictionary from a listing.

    The task ID is set to the listing's database UUID, providing a natural
    unique key that maps 1:1 between tasks and listings.

    Args:
        listing: A listing dictionary from ``ListAdminListings``.

    Returns:
        A task dictionary with all required tracking fields initialised.
    """
    listing_id = listing.get("id")
    if not listing_id:
        raise ValueError(
            f"Listing is missing required 'id' field: {listing.get('name', '<unknown>')}"
        )

    return {
        # Identity (from listing)
        "id": listing_id,
        "listing_id": listing_id,
        "name": listing.get("name", ""),
        "city": listing.get("city", ""),
        "categories": listing.get("categories", []),
        "description": listing.get("description"),
        "source_url": listing.get("sourceUrl"),
        # Existing social URLs (for skip-check logic)
        "facebook_url": listing.get("facebookUrl"),
        "instagram_url": listing.get("instagramUrl"),
        "tiktok_url": listing.get("tiktokUrl"),
        # Task lifecycle state
        "status": "PENDING",
        "started_at": None,
        "completed_at": None,
        # Enrichment metrics (all initialised to zero)
        "listings_enriched": 0,
        "reviews_extracted": 0,
        "reviews_pushed": 0,
        "socials_enriched": 0,
        "descriptions_rewritten": 0,
        "maps_visits": 0,
        # Error tracking
        "errors": [],
    }
