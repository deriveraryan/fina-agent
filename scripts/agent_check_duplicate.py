import os
import sys
import json
import argparse
from typing import Any

# Enable FINA_AGENT_CLI_MODE to route logs to stderr, keeping stdout clean for JSON
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add project root to path to allow features imports
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.scanning.dedup import normalize_name, detect_merge_updates, fuzzy_name_match
from features.shared.observability import BackendObservability
from features.scanning.url_normalization import (
    normalize_facebook_url,
    normalize_instagram_url,
    normalize_tiktok_url,
)


def normalize_candidate_url(url: str) -> str:
    """Helper to normalize social media URLs for comparison."""
    if not url:
        return ""
    url_lower = url.lower()
    if "facebook.com" in url_lower or "fb.com" in url_lower:
        norm = normalize_facebook_url(url)
        return norm if norm else url
    elif "instagram.com" in url_lower or "instagr.am" in url_lower:
        norm = normalize_instagram_url(url)
        return norm if norm else url
    elif "tiktok.com" in url_lower:
        norm = normalize_tiktok_url(url)
        return norm if norm else url
    return url.strip().rstrip("/")


def check_duplicate_in_cache(
    file_path: str,
    candidate_name: str | None = None,
    candidate_url: str | None = None,
    trace_id: str | None = None,
    website: str | None = None,
    phone: str | None = None,
    hours: str | None = None,
    description: str | None = None,
    facebook_url: str | None = None,
    instagram_url: str | None = None,
    tiktok_url: str | None = None,
    categories: list[str] | None = None,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    facebook_followers: int | None = None,
    instagram_followers: int | None = None,
    tiktok_followers: int | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Checks if a candidate is a duplicate within a local JSON listings file."""
    if not os.path.exists(file_path):
        sys.stderr.write(f"Error: File '{file_path}' does not exist.\n")
        sys.exit(1)

    try:
        with open(file_path, "r") as f:
            listings = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Error reading JSON file: {exc}\n")
        sys.exit(1)

    norm_cand_url = normalize_candidate_url(candidate_url) if candidate_url else ""
    norm_cand_name = normalize_name(candidate_name) if candidate_name else ""

    BackendObservability.info(
        f"Checking duplicates in local cache '{file_path}' (name='{candidate_name}', url='{candidate_url}')",
        conversation_id=trace_id
    )

    for listing in listings:
        # Normalize listing details
        listing_fb = normalize_candidate_url(listing.get("facebookUrl") or "")
        listing_ig = normalize_candidate_url(listing.get("instagramUrl") or "")
        listing_tt = normalize_candidate_url(listing.get("tiktokUrl") or "")
        listing_urls = {u for u in (listing_fb, listing_ig, listing_tt) if u}

        is_duplicate = False
        dup_type = ""

        # 1. URL Match Check
        if norm_cand_url and norm_cand_url in listing_urls:
            is_duplicate = True
            dup_type = "url"

        # 2. Name Match Check
        listing_name = normalize_name(listing.get("name") or "")
        if not is_duplicate and norm_cand_name and norm_cand_name == listing_name:
            if not norm_cand_url:
                is_duplicate = True
                dup_type = "name"
            else:
                if norm_cand_url in listing_urls:
                    is_duplicate = True
                    dup_type = "name_and_url"

        if is_duplicate:
            # Candidate matches an existing listing. Check if it has new/updated fields.
            candidate_fields = {
                "website": website,
                "phone": phone,
                "email": email,
                "operatingHours": hours,
                "description": description,
                "facebookUrl": facebook_url,
                "instagramUrl": instagram_url,
                "tiktokUrl": tiktok_url,
                "categories": categories,
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
                "facebookFollowers": facebook_followers,
                "instagramFollowers": instagram_followers,
                "tiktokFollowers": tiktok_followers,
            }
            
            # Map candidate_url to the appropriate platform if not already specified
            if candidate_url:
                url_lower = candidate_url.lower()
                if "facebook.com" in url_lower or "fb.com" in url_lower:
                    if not candidate_fields["facebookUrl"]:
                        candidate_fields["facebookUrl"] = candidate_url
                elif "instagram.com" in url_lower or "instagr.am" in url_lower:
                    if not candidate_fields["instagramUrl"]:
                        candidate_fields["instagramUrl"] = candidate_url
                elif "tiktok.com" in url_lower:
                    if not candidate_fields["tiktokUrl"]:
                        candidate_fields["tiktokUrl"] = candidate_url
                else:
                    if not candidate_fields["website"]:
                        candidate_fields["website"] = candidate_url

            has_updates = detect_merge_updates(
                candidate_fields,
                listing,
                normalize_url_fn=normalize_candidate_url,
            )

            if has_updates:
                BackendObservability.info(
                    f"Local duplicate found, but candidate has new or updated info for '{listing.get('name')}' (ID: {listing.get('id')}). Pushing for merge.",
                    conversation_id=trace_id
                )
                return {"duplicate": False, "should_merge": True, "match": listing}

            BackendObservability.info(
                f"Local duplicate found via {dup_type} match: '{listing.get('name')}' (ID: {listing.get('id')}) with no new info.",
                conversation_id=trace_id
            )
            return {"duplicate": True, "type": dup_type, "match": listing}
    # 3. Fuzzy Name Match — surface near-misses for agent review
    fuzzy_matches: list[dict[str, Any]] = []
    if norm_cand_name:
        for listing in listings:
            listing_name = listing.get("name") or ""
            is_match, score = fuzzy_name_match(candidate_name or "", listing_name)
            if is_match:
                fuzzy_matches.append({
                    "id": listing.get("id"),
                    "name": listing_name,
                    "score": round(score, 1),
                    "address": listing.get("address"),
                })

    if fuzzy_matches:
        # Sort by score descending
        fuzzy_matches.sort(key=lambda m: m["score"], reverse=True)
        BackendObservability.info(
            f"No exact duplicate, but {len(fuzzy_matches)} fuzzy match(es) found for '{candidate_name}'. "
            f"Top match: '{fuzzy_matches[0]['name']}' (score={fuzzy_matches[0]['score']})",
            conversation_id=trace_id
        )
        return {"duplicate": False, "fuzzy_matches": fuzzy_matches}

    BackendObservability.info(
        "No local duplicate found in cache.",
        conversation_id=trace_id
    )
    return {"duplicate": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local Fina listings file for duplicates.")
    parser.add_argument("--file", required=True, help="Path to local listings JSON file.")
    parser.add_argument("--name", help="Business name to check.")
    parser.add_argument("--url", help="Social media URL to check.")
    parser.add_argument("--website", help="Website URL to check.")
    parser.add_argument("--phone", help="Phone number to check.")
    parser.add_argument("--hours", help="Operating hours to check.")
    parser.add_argument("--description", help="Description text to check.")
    parser.add_argument("--facebook-url", help="Facebook URL to check.")
    parser.add_argument("--instagram-url", help="Instagram URL to check.")
    parser.add_argument("--tiktok-url", help="Tiktok URL to check.")
    parser.add_argument("--categories", help="Comma-separated categories to check.")
    parser.add_argument("--address", help="Address to check.")
    parser.add_argument("--latitude", type=float, help="Latitude to check.")
    parser.add_argument("--longitude", type=float, help="Longitude to check.")
    parser.add_argument("--facebook-followers", type=int, help="Facebook followers count to check.")
    parser.add_argument("--instagram-followers", type=int, help="Instagram followers count to check.")
    parser.add_argument("--tiktok-followers", type=int, help="Tiktok followers count to check.")
    parser.add_argument("--email", help="Email address to check.")
    parser.add_argument("--trace-id", help="Trace correlation ID.")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None

    result = check_duplicate_in_cache(
        file_path=args.file,
        candidate_name=args.name,
        candidate_url=args.url,
        trace_id=args.trace_id,
        website=args.website,
        phone=args.phone,
        hours=args.hours,
        description=args.description,
        facebook_url=args.facebook_url,
        instagram_url=args.instagram_url,
        tiktok_url=args.tiktok_url,
        categories=cats,
        address=args.address,
        latitude=args.latitude,
        longitude=args.longitude,
        facebook_followers=args.facebook_followers,
        instagram_followers=args.instagram_followers,
        tiktok_followers=args.tiktok_followers,
        email=args.email,
    )

    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
