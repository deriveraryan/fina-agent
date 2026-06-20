"""Module to manage the task-based state machine for the events listing agent.

Generates one events task per existing database listing that has social URLs.
Provides events-specific metric constants and task building.
Lifecycle functions are imported from task_lifecycle.
"""

from typing import Any, Dict, List, Sequence, Set


# Events-specific metric and state field definitions
EVENTS_ALLOWED_METRICS: Set[str] = {
    "events_discovered",
    "events_pushed",
    "social_urls_scanned",
    "follower_counts_updated",
    "bookmarks_updated",
}

EVENTS_METRIC_FIELDS: Sequence[str] = (
    "events_discovered",
    "events_pushed",
    "social_urls_scanned",
    "follower_counts_updated",
    "bookmarks_updated",
)

EVENTS_MUTABLE_FIELDS: Sequence[str] = (
    "status",
    "started_at",
    "completed_at",
    "events_discovered",
    "events_pushed",
    "social_urls_scanned",
    "follower_counts_updated",
    "bookmarks_updated",
    "errors",
)


def _has_social_urls(listing: Dict[str, Any]) -> bool:
    """Check if a listing has at least one non-null social URL.

    Args:
        listing: A listing dictionary from ``ListAdminListings``.

    Returns:
        True if the listing has at least one social URL.
    """
    return bool(
        listing.get("facebookUrl")
        or listing.get("instagramUrl")
        or listing.get("tiktokUrl")
    )


def generate_events_tasks(
    listings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert a list of listing dicts into events task dicts.

    Only listings with at least one social URL (Facebook, Instagram, or
    TikTok) are included. Listings without social URLs are skipped since
    there are no pages to scan for events.

    Args:
        listings: A list of listing dictionaries as returned by the
            ``ListAdminListings`` GraphQL query.

    Returns:
        A list of task dictionaries, each with tracking metadata and
        metric fields initialised to zero.
    """
    tasks: List[Dict[str, Any]] = []

    for listing in listings:
        if _has_social_urls(listing):
            task = _build_events_task(listing)
            tasks.append(task)

    return tasks


def _build_events_task(listing: Dict[str, Any]) -> Dict[str, Any]:
    """Build a single events task dictionary from a listing.

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
        # Social URLs to scan
        "facebook_url": listing.get("facebookUrl"),
        "instagram_url": listing.get("instagramUrl"),
        "tiktok_url": listing.get("tiktokUrl"),
        # Task lifecycle state
        "status": "PENDING",
        "started_at": None,
        "completed_at": None,
        # Events metrics (all initialised to zero)
        "events_discovered": 0,
        "events_pushed": 0,
        "social_urls_scanned": 0,
        "follower_counts_updated": 0,
        "bookmarks_updated": 0,
        # Error tracking
        "errors": [],
    }
