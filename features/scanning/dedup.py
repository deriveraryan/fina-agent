"""Deduplication and name normalization engine for Fina directory listings.
"""

import re
from typing import Any
from features.shared.observability import BackendObservability


def normalize_name(name: str) -> str:
    """Normalizes business names for duplicate comparison.

    Converts to lowercase, strips trailing/leading whitespace, collapses multiple
    spaces, and removes common corporate designators (e.g. Pty Ltd, Inc).
    """
    if not name:
        return ""
    # Lowercase & strip
    val = name.lower().strip()
    # Remove corporate suffixes with optional trailing dots
    val = re.sub(
        r"\b(pty\s+ltd|pty\.?\s*ltd|ltd|inc|incorporated|llc)\b\.?",
        "",
        val,
    )
    # Collapse whitespace and clean up trailing punctuation
    val = re.sub(r"\s+", " ", val).strip().rstrip("., ")
    return val


def merge_listing_data(
    existing: dict[str, Any], new_data: dict[str, Any]
) -> dict[str, Any]:
    """Merges new listing fields into an existing listing dict.

    Overwrites existing values if the incoming new value is not null and not empty.
    Returns a new merged dict.
    """
    merged = dict(existing)
    for key, value in new_data.items():
        if key in ("id", "createdAt", "updatedAt", "descriptionEmbedding"):
            continue

        if key == "categories":
            if value:
                existing_cats = existing.get("categories") or []
                merged[key] = list(set(existing_cats + value))
        elif key in ("facebookFollowers", "instagramFollowers", "tiktokFollowers"):
            if value is not None:
                merged[key] = value
        else:
            if value is not None and value != "":
                merged[key] = value
    return merged


def deduplicate_batch(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicates a batch of listings in-memory.

    If two listings share the same sourceUrl (if available) or the same 
    normalized name, they are merged into one.
    """
    deduped = {}
    for listing in listings:
        source_url = listing.get("sourceUrl")
        norm_name = normalize_name(listing.get("name", ""))
        
        # Prefer source_url as the grouping key, fallback to norm_name
        key = source_url if source_url else norm_name
        if not key:
            continue
            
        if key in deduped:
            deduped[key] = merge_listing_data(deduped[key], listing)
        else:
            deduped[key] = listing
            
    return list(deduped.values())


async def check_duplicate(
    name: str,
    city: str,
    description: str | None = None,
    source_url: str | None = None,
    categories: list[str] | None = None,
    trace_id: str | None = None,
    generate_embeddings: bool = False,
) -> dict[str, Any] | None:
    """Checks if a directory listing already exists in the database.

    1. First check: exact sourceUrl match (if provided).
    2. Second check: exact normalized name match in the target city.
    3. Third check: semantic similarity via pgvector.

    Returns the duplicate listing as a dict if found, otherwise None.
    """
    from features.shared.graphql_client import execute_graphql_operation

    normalized_new = normalize_name(name)
    BackendObservability.trace(
        f"Deduplication check for '{name}' in {city} (normalized: '{normalized_new}')",
        conversation_id=trace_id
    )

    # 1. Exact match check against active listings in the city
    try:
        response = await execute_graphql_operation(
            operation_name="ListAdminListings",
            variables={
                "city": city,
                "limit": 1000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED"]
            },
        )
        listings = ((response or {}).get("data") or {}).get("listings") or []
        for listing in listings:
            # 1. Exact Source URL match
            if source_url and listing.get("sourceUrl") == source_url:
                BackendObservability.info(
                    f"Duplicate found via exact sourceUrl match: '{listing.get('name')}' (ID: {listing.get('id')})",
                    conversation_id=trace_id
                )
                return listing
                
            # 2. Exact Name match
            if normalize_name(listing.get("name", "")) == normalized_new:
                BackendObservability.info(
                    f"Duplicate found via exact name match: '{listing.get('name')}' (ID: {listing.get('id')})",
                    conversation_id=trace_id
                )
                return listing
    except Exception as exc:
        BackendObservability.error(
            "Error during exact match deduplication check.",
            exception=exc,
            conversation_id=trace_id
        )

    if not generate_embeddings:
        return None

    # 2. Semantic match check via pgvector (client-side embedding)
    try:
        cats_str = ",".join(categories or [])
        base_desc = f"{name} is a Filipino {cats_str} located in {city}."
        desc_for_embedding = f"{base_desc} {description}" if description else base_desc
        
        from features.shared.embeddings import get_embedding
        embedding = get_embedding(desc_for_embedding, trace_id)
        if embedding is None:
            BackendObservability.warning(
                "Embedding generation failed for duplicate check. Skipping semantic deduplication.",
                conversation_id=trace_id
            )
            response = {}
        else:
            BackendObservability.trace(
                f"Executing semantic search for duplicate check with text: '{desc_for_embedding}'",
                conversation_id=trace_id
            )
            
            response = await execute_graphql_operation(
                operation_name="SemanticSearchListings",
                variables={
                    "city": city,
                    "queryEmbedding": embedding
                },
            )
        # Semantic search returns listings_descriptionEmbedding_similarity list
        results = ((response or {}).get("data") or {}).get("listings_descriptionEmbedding_similarity") or []
        for result in results:
            result_name = result.get("name", "")
            # Enforce tight similarity check (either name matches or is a high overlap)
            if normalize_name(result_name) == normalized_new:
                BackendObservability.info(
                    f"Duplicate found via semantic name match: '{result_name}' (ID: {result.get('id')})",
                    conversation_id=trace_id
                )
                return result

            # Jaccard word-overlap check for fuzzy matching
            words_new = set(normalized_new.split())
            words_existing = set(normalize_name(result_name).split())
            if words_new and words_existing:
                intersection = words_new.intersection(words_existing)
                union = words_new.union(words_existing)
                jaccard = len(intersection) / len(union)
                if jaccard > 0.7:
                    BackendObservability.info(
                        f"Duplicate found via fuzzy name overlap ({jaccard:.2f}): '{result_name}' (ID: {result.get('id')})",
                        conversation_id=trace_id
                    )
                    return result
    except Exception as exc:
        BackendObservability.error(
            "Error during semantic deduplication check.",
            exception=exc,
            conversation_id=trace_id
        )

    return None
