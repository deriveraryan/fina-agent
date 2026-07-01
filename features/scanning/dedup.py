"""Deduplication and name normalization engine for Fina directory listings.
"""

import json
import re
from typing import Any

from rapidfuzz import fuzz

from features.shared.observability import BackendObservability


# Minimum fuzzy name similarity score to consider a match.
# Shared by dedup.py and dedup_blocking.py to prevent threshold drift.
FUZZY_NAME_THRESHOLD: int = 85


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


def fuzzy_name_match(
    name_a: str,
    name_b: str,
    threshold: int = FUZZY_NAME_THRESHOLD,
) -> tuple[bool, float]:
    """Fuzzy name comparison using rapidfuzz token_set_ratio.

    Normalizes both names (lowercase, strip corporate suffixes) before
    comparison. Catches spacing/concatenation variations like
    'CJ Migration' vs 'CJMigration' that exact matching misses.

    Args:
        name_a: First business name.
        name_b: Second business name.
        threshold: Minimum score to consider a match (0-100).

    Returns:
        (is_match, score) tuple where score is 0-100.
    """
    norm_a = normalize_name(name_a)
    norm_b = normalize_name(name_b)
    if not norm_a or not norm_b:
        return False, 0.0
    score = fuzz.token_set_ratio(norm_a, norm_b)
    return score > threshold, float(score)


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
                merged[key] = value
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


def _clean_phone(phone: str) -> str:
    """Strips all non-digit characters for phone number comparison."""
    return re.sub(r"\D", "", phone)


def detect_merge_updates(
    candidate_fields: dict[str, Any],
    existing_listing: dict[str, Any],
    normalize_url_fn: Any = None,
) -> bool:
    """Detects whether a candidate has new or updated fields compared to an existing listing.

    Compares candidate field values against the existing listing, applying
    type-aware normalization for URLs, phone numbers, and JSON operating hours.

    Args:
        candidate_fields: Dict of field names to candidate values.
        existing_listing: Dict representing the existing database listing.
        normalize_url_fn: Optional callable to normalize URL strings for comparison.

    Returns:
        True if the candidate contains at least one field with new or different data.
    """
    url_fields = ("facebookUrl", "instagramUrl", "tiktokUrl", "website")

    for field, cand_val in candidate_fields.items():
        if cand_val in (None, "", []):
            continue

        exist_val = existing_listing.get(field)

        # Existing field is empty — candidate has new data
        if exist_val is None or exist_val == "" or exist_val == []:
            return True

        if field in url_fields:
            norm_cand = normalize_url_fn(cand_val) if normalize_url_fn else cand_val.strip().rstrip("/")
            norm_exist = normalize_url_fn(exist_val) if normalize_url_fn else exist_val.strip().rstrip("/")
            if norm_cand != norm_exist:
                return True
        elif field == "phone":
            if _clean_phone(cand_val) != _clean_phone(exist_val):
                return True
        elif field == "operatingHours":
            try:
                cand_h = json.loads(cand_val) if isinstance(cand_val, str) else cand_val
                exist_h = json.loads(exist_val) if isinstance(exist_val, str) else exist_val
                if cand_h != exist_h:
                    return True
            except Exception:
                if cand_val != exist_val:
                    return True
        elif field == "categories":
            try:
                if set(cand_val) != set(exist_val):
                    return True
            except TypeError:
                if cand_val != exist_val:
                    return True
        elif field == "address":
            if cand_val.strip().lower() != exist_val.strip().lower():
                return True
        elif field in ("latitude", "longitude"):
            try:
                if abs(float(cand_val) - float(exist_val)) > 1e-6:
                    return True
            except (ValueError, TypeError):
                if cand_val != exist_val:
                    return True
        elif field in ("facebookFollowers", "instagramFollowers", "tiktokFollowers"):
            try:
                if int(cand_val) != int(exist_val):
                    return True
            except (ValueError, TypeError):
                if cand_val != exist_val:
                    return True
        else:
            if cand_val != exist_val:
                return True

    return False


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
                "limit": 2000,
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

            # Fuzzy name match via rapidfuzz (replaces Jaccard word-overlap
            # which missed concatenated-word variations like CJMigration)
            is_fuzzy, fuzzy_score = fuzzy_name_match(result_name, name)
            if is_fuzzy:
                BackendObservability.info(
                    f"Duplicate found via fuzzy name match (score={fuzzy_score:.0f}): '{result_name}' (ID: {result.get('id')})",
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
