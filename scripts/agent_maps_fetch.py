#!/usr/bin/env python3
"""CLI script to execute a single Google Places API text search query.

Accepts a pre-formatted search query and returns formatted place results as JSON.
"""

import os
import sys
import json
import argparse
import asyncio
import httpx
from typing import Any, Dict, List, Optional

# Enable FINA_AGENT_CLI_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add functions path to Python load path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.observability import BackendObservability
from features.scanning.maps_browser_parser import DAYS_MAP



def _parse_opening_hours(weekday_descriptions: List[str]) -> Optional[str]:
    """Parses standard Google weekday descriptions array to structured operatingHours JSON string."""
    result = {}
    for desc in weekday_descriptions:
        if ":" not in desc:
            continue
        parts = desc.split(":", 1)
        day = parts[0].strip().lower()
        hours = parts[1].strip()

        target_day = DAYS_MAP.get(day)
        if target_day:
            result[target_day] = hours

    if not result:
        return None
    return json.dumps(result)


def format_place(place: Dict[str, Any], city: str, category: str) -> Dict[str, Any]:
    """Formats a raw Place object from Places API (New) to a standardized schema."""
    place_id = place.get("id", "")
    display_name_obj = place.get("displayName") or {}
    name = display_name_obj.get("text", "")
    
    editorial_obj = place.get("editorialSummary") or {}
    editorial = editorial_obj.get("text", "")
    
    types = place.get("types", [])
    
    operating_hours_json = None
    hours_obj = place.get("regularOpeningHours") or {}
    weekday_descriptions = hours_obj.get("weekdayDescriptions")
    if weekday_descriptions:
        operating_hours_json = _parse_opening_hours(weekday_descriptions)
        
    location = place.get("location") or {}
    lat = location.get("latitude")
    lng = location.get("longitude")
    
    # Adopt the enum from the Google Places API businessStatus directly
    status = place.get("businessStatus", "OPERATIONAL")
    
    website = place.get("websiteUri")
    fb_url = None
    ig_url = None
    tt_url = None
    if website:
        website_lower = website.lower()
        if "facebook.com" in website_lower or "fb.com" in website_lower:
            fb_url = website
        elif "instagram.com" in website_lower or "instagr.am" in website_lower:
            ig_url = website
        elif "tiktok.com" in website_lower:
            tt_url = website
            
    return {
        "id": place_id,
        "name": name,
        "types": types,
        "address": place.get("formattedAddress", f"{city.title()} CBD, Australia"),
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
        "phone": place.get("internationalPhoneNumber"),
        "website": website,
        "facebookUrl": fb_url,
        "instagramUrl": ig_url,
        "tiktokUrl": tt_url,
        "hours": operating_hours_json,
        "description": editorial or f"A verified Filipino {category.lower()} in {city.title()}.",
        "sourceUrl": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
        "status": status
    }


async def _execute_places_text_search(query: str, api_key: str) -> List[Dict[str, Any]]:
    """Calls Google Places API (New) Text Search endpoint asynchronously."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.websiteUri,places.internationalPhoneNumber,places.regularOpeningHours,"
            "places.editorialSummary,places.types,places.businessStatus"
        )
    }
    body = {
        "textQuery": query,
        "languageCode": "en"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=body, headers=headers, timeout=20.0)
    if response.status_code != 200:
        raise RuntimeError(
            f"Places API returned status code {response.status_code}: {response.text}"
        )
    data = response.json()
    return data.get("places") or []


def load_valid_categories() -> list[str]:
    """Loads valid categories from data/categories.json, failing fast if loading fails."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/categories.json"))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Canonical category file not found at: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Category file at {path} must be a JSON object mapping category keys.")
    return list(data.keys())


async def main() -> None:
    """CLI entrypoint: execute a single Places API text search and output formatted results."""
    parser = argparse.ArgumentParser(
        description="Execute a single Google Places API text search query."
    )
    parser.add_argument("--query", type=str, required=True, help="Pre-formatted search query string.")
    parser.add_argument("--city", type=str, required=True, help="Target city name (metadata for format_place).")
    parser.add_argument(
        "--category",
        type=str,
        required=True,
        choices=load_valid_categories(),
        help="Target category (metadata for format_place).",
    )
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(
        f"Starting agent_maps_fetch.py with query='{args.query}', city={args.city}, category={args.category}",
        conversation_id=args.trace_id,
    )

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        BackendObservability.error(
            "GOOGLE_MAPS_API_KEY environment variable is not set.",
            conversation_id=args.trace_id,
        )
        sys.exit(1)

    raw_places = await _execute_places_text_search(args.query, api_key)
    BackendObservability.info(
        f"Places API returned {len(raw_places)} raw results.",
        conversation_id=args.trace_id,
    )

    places = [
        format_place(p, args.city, args.category)
        for p in raw_places
        if p.get("displayName", {}).get("text")
    ]
    BackendObservability.info(
        f"Formatted {len(places)} places from raw results.",
        conversation_id=args.trace_id,
    )

    output = {
        "places": places,
        "total": len(places),
    }
    sys.stdout.write(json.dumps(output))


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
