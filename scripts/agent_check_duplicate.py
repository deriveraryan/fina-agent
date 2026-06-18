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

from features.scanning.dedup import normalize_name
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

        # 1. URL Match Check
        if norm_cand_url and norm_cand_url in listing_urls:
            BackendObservability.info(
                f"Local duplicate found via URL match: '{listing.get('name')}' (ID: {listing.get('id')})",
                conversation_id=trace_id
            )
            return {"duplicate": True, "type": "url", "match": listing}

        # 2. Name Match Check
        listing_name = normalize_name(listing.get("name") or "")
        if norm_cand_name and norm_cand_name == listing_name:
            if not norm_cand_url:
                BackendObservability.info(
                    f"Local duplicate found via name match (no URL): '{listing.get('name')}' (ID: {listing.get('id')})",
                    conversation_id=trace_id
                )
                # Same name, and candidate has no URL -> duplicate
                return {"duplicate": True, "type": "name", "match": listing}
            else:
                # Same name, and candidate has a URL.
                # If this URL is already linked to the existing listing, it's a duplicate.
                # Otherwise, it's a new source (e.g. adding Instagram to a listing that has Facebook), so NOT a duplicate.
                if norm_cand_url in listing_urls:
                    BackendObservability.info(
                        f"Local duplicate found via name and URL match: '{listing.get('name')}' (ID: {listing.get('id')})",
                        conversation_id=trace_id
                    )
                    return {"duplicate": True, "type": "name_and_url", "match": listing}

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
    parser.add_argument("--trace-id", help="Trace correlation ID.")
    args = parser.parse_args()

    result = check_duplicate_in_cache(
        file_path=args.file,
        candidate_name=args.name,
        candidate_url=args.url,
        trace_id=args.trace_id,
    )

    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
