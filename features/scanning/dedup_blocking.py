"""Deterministic blocking engine for post-hoc listing deduplication.

Pure-function module: takes a list of listing dicts, returns candidate
duplicate groups. No I/O, no side effects, no database calls.

Blocking strategy (any one triggers candidacy within the same city):
  1. Exact normalized name match
  2. Fuzzy name similarity (token_set_ratio > 85 via rapidfuzz)
  3. Shared non-null sourceUrl
"""

import re
from typing import Any

from rapidfuzz import fuzz

from features.scanning.dedup import normalize_name, FUZZY_NAME_THRESHOLD


# Common Australian address abbreviations → full forms.
# Only road-type suffixes are expanded to avoid false expansions
# (e.g., "St Kilda" should NOT become "Street Kilda").
ADDRESS_ABBREVIATIONS: dict[str, str] = {
    "st": "street",
    "rd": "road",
    "ave": "avenue",
    "dr": "drive",
    "pde": "parade",
    "pl": "place",
    "ct": "court",
    "cres": "crescent",
    "blvd": "boulevard",
    "hwy": "highway",
    "ln": "lane",
    "tce": "terrace",
    "cct": "circuit",
    "cl": "close",
    "gr": "grove",
    "pnt": "point",
    "sq": "square",
    "wy": "way",
}

# Fields excluded from merge and completeness (system-managed fields).
PROTECTED_FIELDS: frozenset[str] = frozenset({
    "id", "createdAt", "updatedAt", "descriptionEmbedding",
})



def normalize_address(address: str | None) -> str:
    """Normalizes street addresses for duplicate comparison.

    Lowercases, strips/collapses whitespace, and expands common Australian
    address abbreviations (e.g., Pde → Parade, St → Street).

    Only expands abbreviations that appear as the LAST word before a comma,
    end-of-string, or a suburb/state/postcode token to avoid false expansions
    like "St Kilda" → "Street Kilda".
    """
    if not address:
        return ""

    val = address.lower().strip()
    val = re.sub(r"\s+", " ", val)

    # Expand abbreviations only when they appear as a road-type suffix.
    # Pattern: word boundary + abbreviation + (comma, end-of-string, or
    # followed by a comma/space before suburb tokens).
    for abbrev, full in ADDRESS_ABBREVIATIONS.items():
        # Match abbreviation followed by comma, end-of-string, or space+digit
        # (postcode). This avoids expanding "St" in "St Kilda".
        pattern = rf"\b{re.escape(abbrev)}\b(?=\s*[,]|\s+\d|\s*$)"
        val = re.sub(pattern, full, val)

    val = re.sub(r"\s+", " ", val).strip()
    return val


def compute_field_completeness(listing: dict[str, Any]) -> int:
    """Counts non-null, non-empty fields in a listing dict.

    Empty strings, None values, and empty lists are not counted.
    """
    count = 0
    for key, value in listing.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        count += 1
    return count


def build_blocking_pairs(
    listings: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    """Generates candidate duplicate pairs using deterministic blocking keys.

    O(n²) pairwise comparison within the listing set. Suitable for city-level
    batches (typically <500 listings).

    Returns:
        List of (listingA, listingB, blocking_reason) tuples for pairs that
        match on ANY criterion:
          1. Exact normalized name
          2. Fuzzy name similarity (token_set_ratio > 85)
          3. Shared non-null sourceUrl
    """
    pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    n = len(listings)

    # Pre-compute normalized names for efficiency
    norm_names = [normalize_name(l.get("name", "")) for l in listings]

    for i in range(n):
        for j in range(i + 1, n):
            reasons: list[str] = []

            name_i = norm_names[i]
            name_j = norm_names[j]

            # 1. Exact normalized name match
            if name_i and name_j and name_i == name_j:
                reasons.append("exact_name_match")
            # 2. Fuzzy name similarity (only if not already exact match)
            elif name_i and name_j:
                score = fuzz.token_set_ratio(name_i, name_j)
                if score > FUZZY_NAME_THRESHOLD:
                    reasons.append(f"fuzzy_name_match (token_set_ratio={score:.0f})")

            # 3. Shared sourceUrl
            url_i = (listings[i].get("sourceUrl") or "").strip()
            url_j = (listings[j].get("sourceUrl") or "").strip()
            if url_i and url_j and url_i == url_j:
                reasons.append("shared_source_url")

            if reasons:
                pairs.append((listings[i], listings[j], " + ".join(reasons)))

    return pairs


def group_pairs_union_find(
    pairs: list[tuple[dict[str, Any], dict[str, Any], str]],
) -> list[list[dict[str, Any]]]:
    """Groups transitively connected listing pairs via Union-Find.

    If A≈B and B≈C, produces one group {A, B, C} even if A≉C directly.

    Returns:
        List of groups, where each group is a list of listing dicts.
    """
    if not pairs:
        return []

    # Collect all unique listings by id
    id_to_listing: dict[str, dict[str, Any]] = {}
    for a, b, _ in pairs:
        id_to_listing[a["id"]] = a
        id_to_listing[b["id"]] = b

    # Union-Find with path compression and union by rank
    parent: dict[str, str] = {lid: lid for lid in id_to_listing}
    rank: dict[str, int] = {lid: 0 for lid in id_to_listing}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx == ry:
            return
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1

    # Union all pairs
    for a, b, _ in pairs:
        union(a["id"], b["id"])

    # Group by root
    groups_map: dict[str, list[dict[str, Any]]] = {}
    for lid, listing in id_to_listing.items():
        root = find(lid)
        if root not in groups_map:
            groups_map[root] = []
        groups_map[root].append(listing)

    return list(groups_map.values())


def select_survivor(
    group: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Selects the survivor (record to keep) from a duplicate group.

    Selection criteria:
      1. Oldest createdAt (primary)
      2. Highest field completeness (tiebreak)

    Returns:
        (survivor, duplicates) where duplicates is the remaining listings.
    """
    if len(group) <= 1:
        return group[0], []

    def sort_key(listing: dict[str, Any]) -> tuple[str, int]:
        created = listing.get("createdAt") or "9999-12-31T23:59:59Z"
        completeness = compute_field_completeness(listing)
        # Sort by createdAt ascending (oldest first), then by completeness
        # descending (negate for descending in tuple sort).
        return (created, -completeness)

    sorted_group = sorted(group, key=sort_key)
    return sorted_group[0], sorted_group[1:]


def compute_merge_fields(
    survivor: dict[str, Any],
    duplicate: dict[str, Any],
) -> dict[str, Any]:
    """Computes fields to merge from a duplicate into the survivor.

    Only includes fields where the survivor value is null/empty AND
    the duplicate value is non-null/non-empty. Never overwrites existing
    survivor data. Skips protected system fields.

    Returns:
        Dict of field_name → duplicate_value for fields to merge.
    """
    merge: dict[str, Any] = {}
    for key, dup_value in duplicate.items():
        if key in PROTECTED_FIELDS:
            continue

        # Skip if duplicate value is empty
        if dup_value is None:
            continue
        if isinstance(dup_value, str) and dup_value == "":
            continue
        if isinstance(dup_value, list) and len(dup_value) == 0:
            continue

        # Only merge if survivor value is missing
        surv_value = survivor.get(key)
        is_empty = (
            surv_value is None
            or (isinstance(surv_value, str) and surv_value == "")
            or (isinstance(surv_value, list) and len(surv_value) == 0)
        )
        if is_empty:
            merge[key] = dup_value

    return merge


def generate_candidate_groups(
    listings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Orchestrates the full blocking pipeline.

    1. build_blocking_pairs — deterministic candidate pair generation
    2. group_pairs_union_find — transitive grouping
    3. Enrich each group with survivor selection, merge fields, completeness

    Returns:
        List of structured group dicts ready for the plan file.
    """
    pairs = build_blocking_pairs(listings)
    raw_groups = group_pairs_union_find(pairs)

    # Collect blocking reasons per group for reporting
    # Build a map of (id_a, id_b) → reason for reason aggregation
    pair_reasons: dict[frozenset[str], str] = {}
    for a, b, reason in pairs:
        pair_reasons[frozenset({a["id"], b["id"]})] = reason

    result: list[dict[str, Any]] = []
    for group_idx, group_listings in enumerate(raw_groups, start=1):
        survivor, duplicates = select_survivor(group_listings)

        # Collect all blocking reasons for this group
        group_ids = [l["id"] for l in group_listings]
        reasons: list[str] = []
        for i, id_a in enumerate(group_ids):
            for id_b in group_ids[i + 1:]:
                key = frozenset({id_a, id_b})
                if key in pair_reasons:
                    reasons.append(pair_reasons[key])

        # Compute per-candidate field completeness
        candidates = []
        for listing in group_listings:
            candidate = dict(listing)
            candidate["fieldCompleteness"] = compute_field_completeness(listing)
            candidates.append(candidate)

        # Compute aggregate merge fields (from all duplicates into survivor)
        aggregate_merge: dict[str, Any] = {}
        for dup in duplicates:
            dup_merge = compute_merge_fields(survivor, dup)
            # First duplicate's fields win for merge conflicts between duplicates
            for k, v in dup_merge.items():
                if k not in aggregate_merge:
                    aggregate_merge[k] = v

        result.append({
            "groupId": group_idx,
            "candidates": candidates,
            "blockingReasons": reasons,
            "suggestedSurvivorId": survivor["id"],
            "suggestedDuplicateIds": [d["id"] for d in duplicates],
            "verdict": None,
            "survivorId": None,
            "duplicateIds": [],
            "mergeFields": aggregate_merge,
            "executedAt": None,
            "reasoning": None,
        })

    return result
