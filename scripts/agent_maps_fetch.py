#!/usr/bin/env python3
"""CLI script to search Google Places with pagination and caching support.

Saves Place API costs and avoids agent context bloat by caching results locally.
"""

import os
import sys
import json
import argparse
import asyncio
import httpx
from typing import Any

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

# Global AsyncClient instance for connection reuse
_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


# Search keyword templates per category
SEARCH_TEMPLATES: dict[str, list[str]] = {
    "RESTAURANT": [
        "Filipino restaurant in {city}",
        "Pinoy food in {city}"
    ],
    "CAFE": [
        "Filipino cafe in {city}",
        "Filipino coffee in {city}"
    ],
    "SHOP": [
        "Filipino grocery in {city}",
        "Filipino shop in {city}",
        "Filipino supermarket in {city}"
    ],
    "CHURCH": [
        "Filipino Christian church in {city}",
        "Tagalog mass in {city}",
        "Filipino Catholic in {city}"
    ],
    "COMMUNITY": [
        "Filipino community association in {city}",
        "Filipino community group in {city}",
        "Filipino association in {city}",
        "Filipino club in {city}"
    ],
    "GOVERNMENT": [
        "Philippine consulate in {city}",
        "Philippine embassy in {city}",
        "Philippine honorary consulate in {city}"
    ],
    "SERVICES": [
        "Filipino services in {city}",
        "Filipino business in {city}",
        "Filipino accountant in {city}",
        "Filipino logistics in {city}",
        "Filipino freight in {city}",
        "Filipino travel agency in {city}"
    ]
}


def _parse_opening_hours(weekday_descriptions: list[str]) -> str | None:
    """Parses standard Google weekday descriptions array to structured operatingHours JSON string."""
    days_map = {
        "monday": "mon",
        "tuesday": "tue",
        "wednesday": "wed",
        "thursday": "thu",
        "friday": "fri",
        "saturday": "sat",
        "sunday": "sun",
    }
    result = {}
    for desc in weekday_descriptions:
        if ":" not in desc:
            continue
        parts = desc.split(":", 1)
        day = parts[0].strip().lower()
        hours = parts[1].strip()

        target_day = days_map.get(day)
        if target_day:
            result[target_day] = hours

    if not result:
        return None
    return json.dumps(result)


def format_place(place: dict, city: str, category: str) -> dict:
    """Formats a raw Place object from Places API (New) to a standardized schema."""
    place_id = place.get("id", "")
    display_name_obj = place.get("displayName") or {}
    name = display_name_obj.get("text", "")
    
    editorial_obj = place.get("editorialSummary") or {}
    editorial = editorial_obj.get("text", "")
    
    types = place.get("types", [])
    
    reviews_list = place.get("reviews") or []
    structured_reviews = []
    for r in reviews_list:
        if not isinstance(r, dict):
            continue
        text = r.get("text", {}).get("text")
        if not text:
            continue
        structured_reviews.append({
            "externalSourceId": r.get("name"),
            "authorName": r.get("authorAttribution", {}).get("displayName"),
            "rating": r.get("rating"),
            "text": text,
            "publishedDate": r.get("publishTime")
        })
    
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
    
    return {
        "id": place_id,
        "name": name,
        "types": types,
        "address": place.get("formattedAddress", f"{city.title()} CBD, Australia"),
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
        "phone": place.get("internationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "hours": operating_hours_json,
        "description": editorial or f"A verified Filipino {category.lower()} in {city.title()}.",
        "reviews": structured_reviews,
        "sourceUrl": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
        "status": status
    }


async def _execute_places_text_search(query: str, api_key: str) -> list[dict[str, Any]]:
    """Calls Google Places API (New) Text Search endpoint asynchronously."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.websiteUri,places.internationalPhoneNumber,places.regularOpeningHours,"
            "places.editorialSummary,places.types,places.reviews,places.businessStatus"
        )
    }
    body = {
        "textQuery": query,
        "languageCode": "en"
    }

    client = _get_client()
    response = await client.post(url, json=body, headers=headers, timeout=20.0)
    if response.status_code != 200:
        raise RuntimeError(
            f"Places API returned status code {response.status_code}: {response.text}"
        )
    data = response.json()
    return data.get("places") or []


def _get_mock_places(city: str, category: str) -> list[dict[str, Any]]:
    """Returns raw mock Place objects matching Google Places API schema."""
    city_title = city.title()
    if category == "RESTAURANT":
        return [
            {
                "id": "mock_restaurant_1",
                "displayName": {"text": f"Mock Manila Diner {city_title}"},
                "types": ["restaurant", "food", "establishment"],
                "formattedAddress": f"123 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"123 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8688 if city == "SYDNEY" else -37.8136,
                    "longitude": 151.2093 if city == "SYDNEY" else 144.9631
                },
                "internationalPhoneNumber": "+61 2 9999 1111",
                "websiteUri": "https://maniladiner.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 11:00 AM – 9:00 PM",
                        "Tuesday: 11:00 AM – 9:00 PM",
                        "Wednesday: 11:00 AM – 9:00 PM",
                        "Thursday: 11:00 AM – 9:00 PM",
                        "Friday: 11:00 AM – 10:00 PM",
                        "Saturday: 11:00 AM – 10:00 PM",
                        "Sunday: 11:00 AM – 9:00 PM"
                    ]
                },
                "editorialSummary": {"text": "Authentic Manila style diners serving signature lechon and adobo."},
                "reviews": [
                    {
                        "name": "places/mock_restaurant_1/reviews/0",
                        "authorAttribution": {"displayName": "Juan Dela Cruz"},
                        "rating": 5.0,
                        "text": {"text": "Great chicken inasal and helpful staff."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    },
                    {
                        "name": "places/mock_restaurant_1/reviews/1",
                        "authorAttribution": {"displayName": "Maria Clara"},
                        "rating": 4.0,
                        "text": {"text": "Very clean place with amazing pork sisig!"},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "CAFE":
        return [
            {
                "id": "mock_cafe_1",
                "displayName": {"text": f"Mock Pinoy Brew {city_title}"},
                "types": ["cafe", "food", "establishment"],
                "formattedAddress": f"45 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"45 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8695 if city == "SYDNEY" else -37.8142,
                    "longitude": 151.2085 if city == "SYDNEY" else 144.9625
                },
                "internationalPhoneNumber": "+61 2 9999 2222",
                "websiteUri": "https://pinoybrew.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 7:00 AM – 4:00 PM",
                        "Tuesday: 7:00 AM – 4:00 PM",
                        "Wednesday: 7:00 AM – 4:00 PM",
                        "Thursday: 7:00 AM – 4:00 PM",
                        "Friday: 7:00 AM – 4:00 PM",
                        "Saturday: 8:00 AM – 3:00 PM",
                        "Sunday: Closed"
                    ]
                },
                "editorialSummary": {"text": "Cozy café featuring specialty ube lattes and pandesal toast."},
                "reviews": [
                    {
                        "name": "places/mock_cafe_1/reviews/0",
                        "authorAttribution": {"displayName": "Jose Rizal"},
                        "rating": 5.0,
                        "text": {"text": "Fabulous ube cake and friendly barista."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "SHOP":
        return [
            {
                "id": "mock_shop_1",
                "displayName": {"text": f"Mock Sari Sari Mart {city_title}"},
                "types": ["grocery_store", "store", "establishment"],
                "formattedAddress": f"88 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"88 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8702 if city == "SYDNEY" else -37.8150,
                    "longitude": 151.2078 if city == "SYDNEY" else 144.9618
                },
                "internationalPhoneNumber": "+61 2 9999 3333",
                "websiteUri": "https://sarisarimart.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 9:00 AM – 7:00 PM",
                        "Tuesday: 9:00 AM – 7:00 PM",
                        "Wednesday: 9:00 AM – 7:00 PM",
                        "Thursday: 9:00 AM – 8:00 PM",
                        "Friday: 9:00 AM – 8:00 PM",
                        "Saturday: 9:00 AM – 6:00 PM",
                        "Sunday: 10:00 AM – 5:00 PM"
                    ]
                },
                "editorialSummary": {"text": "Well stocked grocery store with Filipino brand goods and imported ingredients."},
                "reviews": [
                    {
                        "name": "places/mock_shop_1/reviews/0",
                        "authorAttribution": {"displayName": "Andres Bonifacio"},
                        "rating": 4.5,
                        "text": {"text": "Has all the Filipino snacks and sauces I miss!"},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "CHURCH":
        return [
            {
                "id": "mock_church_1",
                "displayName": {"text": f"Mock Tagalog Fellowship {city_title}"},
                "types": ["place_of_worship", "church", "establishment"],
                "formattedAddress": f"10 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"10 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8680 if city == "SYDNEY" else -37.8125,
                    "longitude": 151.2100 if city == "SYDNEY" else 144.9640
                },
                "internationalPhoneNumber": "+61 2 9999 4444",
                "websiteUri": "https://tagalogfellowship.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Sunday: 9:00 AM – 1:00 PM"
                    ]
                },
                "editorialSummary": {"text": "Filipino Christian worship service and community fellowship."},
                "reviews": [
                    {
                        "name": "places/mock_church_1/reviews/0",
                        "authorAttribution": {"displayName": "Gabriela Silang"},
                        "rating": 5.0,
                        "text": {"text": "Very warm and welcoming community."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "COMMUNITY":
        return [
            {
                "id": "mock_community_1",
                "displayName": {"text": f"Mock Filipino Community Association {city_title}"},
                "types": ["association", "group", "establishment"],
                "formattedAddress": f"100 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"100 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8680 if city == "SYDNEY" else -37.8125,
                    "longitude": 151.2100 if city == "SYDNEY" else 144.9640
                },
                "internationalPhoneNumber": "+61 2 9999 5555",
                "websiteUri": "https://filcommunity.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Sunday: 9:00 AM – 5:00 PM"
                    ]
                },
                "editorialSummary": {"text": f"Filipino community group in {city_title}."},
                "reviews": [
                    {
                        "name": "places/mock_community_1/reviews/0",
                        "authorAttribution": {"displayName": "Melchora Aquino"},
                        "rating": 4.8,
                        "text": {"text": "Very active and helpful community."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "GOVERNMENT":
        return [
            {
                "id": "mock_gov_1",
                "displayName": {"text": f"Mock Philippine Consulate {city_title}"},
                "types": ["local_government_office", "government_office", "establishment"],
                "formattedAddress": f"15 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"15 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8685 if city == "SYDNEY" else -37.8130,
                    "longitude": 151.2095 if city == "SYDNEY" else 144.9635
                },
                "internationalPhoneNumber": "+61 2 9999 6666",
                "websiteUri": "https://phconsulate.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 9:00 AM – 5:00 PM",
                        "Tuesday: 9:00 AM – 5:00 PM",
                        "Wednesday: 9:00 AM – 5:00 PM",
                        "Thursday: 9:00 AM – 5:00 PM",
                        "Friday: 9:00 AM – 5:00 PM"
                    ]
                },
                "editorialSummary": {"text": f"Philippine consular services office in {city_title}."},
                "reviews": [
                    {
                        "name": "places/mock_gov_1/reviews/0",
                        "authorAttribution": {"displayName": "Emilio Aguinaldo"},
                        "rating": 4.2,
                        "text": {"text": "Fast service and friendly staff."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    elif category == "SERVICES":
        return [
            {
                "id": "mock_services_1",
                "displayName": {"text": f"Mock Services Business {city_title}"},
                "types": ["professional_service", "establishment"],
                "formattedAddress": f"20 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"20 Collins St, {city_title} VIC 3000",
                "location": {
                    "latitude": -33.8690 if city == "SYDNEY" else -37.8140,
                    "longitude": 151.2105 if city == "SYDNEY" else 144.9645
                },
                "internationalPhoneNumber": "+61 2 9999 7777",
                "websiteUri": "https://services.example.com",
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 9:00 AM – 5:00 PM",
                        "Tuesday: 9:00 AM – 5:00 PM",
                        "Wednesday: 9:00 AM – 5:00 PM",
                        "Thursday: 9:00 AM – 5:00 PM",
                        "Friday: 9:00 AM – 5:00 PM"
                    ]
                },
                "editorialSummary": {"text": f"A verified Filipino services in {city_title}."},
                "reviews": [
                    {
                        "name": "places/mock_services_1/reviews/0",
                        "authorAttribution": {"displayName": "Ramon Magsaysay"},
                        "rating": 4.9,
                        "text": {"text": "Excellent tax and accounting consultation service."},
                        "publishTime": "2026-06-06T00:00:00Z"
                    }
                ]
            }
        ]
    return []


def load_valid_categories() -> list[str]:
    """Loads valid categories from data/categories.json, defaulting to standard set if loading fails."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/categories.json"))
    default_categories = ["RESTAURANT", "CAFE", "SHOP", "CHURCH", "GOVERNMENT", "COMMUNITY", "SERVICES"]
    if not os.path.exists(path):
        return default_categories
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return list(data.keys())
    except Exception:
        return default_categories


async def main() -> None:
    parser = argparse.ArgumentParser(description="Query Google Places API candidates with caching and pagination.")
    parser.add_argument("--city", type=str, required=True, help="Target city name.")
    parser.add_argument("--category", type=str, required=True, choices=load_valid_categories(), help="Target category.")
    parser.add_argument("--limit", type=int, default=10, help="Number of results to return.")
    parser.add_argument("--offset", type=int, default=0, help="Offset to start returning results from.")
    parser.add_argument("--refresh", action="store_true", help="Bypass local cache and query live Places API.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    BackendObservability.info(f"Starting agent_maps_fetch.py with city={args.city}, category={args.category}, limit={args.limit}, offset={args.offset}", conversation_id=args.trace_id)

    city_key = args.city.lower().replace(" ", "_")
    cat_key = args.category.lower()
    
    # Save cache file in the .antigravity_saves directory
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.antigravity_saves"))
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"maps_cache_{city_key}_{cat_key}.json")

    places = []

    # Try cache hit
    if os.path.exists(cache_path) and not args.refresh:
        BackendObservability.trace(f"Cache file found: {cache_path}", conversation_id=args.trace_id)
        try:
            with open(cache_path, "r") as f:
                places = json.loads(f.read())
            BackendObservability.info(f"Cache hit: loaded {len(places)} places from local cache", conversation_id=args.trace_id)
        except Exception as exc:
            BackendObservability.warning(f"Failed to read cache from {cache_path}: {exc}", conversation_id=args.trace_id)
            places = []
    else:
        if args.refresh:
            BackendObservability.trace("Bypassing cache due to --refresh flag", conversation_id=args.trace_id)
        else:
            BackendObservability.trace(f"Cache file not found at {cache_path}", conversation_id=args.trace_id)

    # Cache miss
    if not places:
        BackendObservability.info("Cache miss. Fetching candidates...", conversation_id=args.trace_id)
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        
        raw_places = []
        if not api_key or api_key == "mock-key":
            BackendObservability.info("GOOGLE_MAPS_API_KEY not configured or is 'mock-key'. Falling back to local mock data.", conversation_id=args.trace_id)
            # Running offline/mock mode
            raw_places = _get_mock_places(args.city, args.category)
            BackendObservability.trace(f"Loaded {len(raw_places)} mock places.", conversation_id=args.trace_id)
        else:
            templates = SEARCH_TEMPLATES.get(args.category, [])
            seen_ids = set()
            
            # Load suburbs for the target city
            suburbs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/top_suburbs_per_city.json"))
            suburbs = []
            if os.path.exists(suburbs_path):
                try:
                    with open(suburbs_path, "r") as f:
                        suburbs_data = json.load(f)
                        suburbs = suburbs_data.get(args.city.lower(), [])
                except Exception as exc:
                    BackendObservability.warning(f"Failed to load top_suburbs_per_city.json: {exc}", conversation_id=args.trace_id)
            
            locations = [args.city.title()]
            for sub in suburbs:
                locations.append(f"{sub}, {args.city.title()}")

            BackendObservability.info(f"Querying Google Places API using {len(templates)} keyword templates across {len(locations)} locations", conversation_id=args.trace_id)
            for template in templates:
                for loc in locations:
                    query = template.format(city=loc)
                    BackendObservability.trace(f"Executing Places search for query: '{query}'", conversation_id=args.trace_id)
                    try:
                        results = await _execute_places_text_search(query, api_key)
                        BackendObservability.trace(f"Places search query '{query}' returned {len(results)} raw results", conversation_id=args.trace_id)
                        for r in results:
                            p_id = r.get("id")
                            if p_id and p_id not in seen_ids:
                                seen_ids.add(p_id)
                                raw_places.append(r)
                    except Exception as exc:
                        BackendObservability.error(f"Error querying Places API for query '{query}': {exc}", exception=exc, conversation_id=args.trace_id)

        # Format raw places to the standardized client schema
        places = [format_place(p, args.city, args.category) for p in raw_places if p.get("displayName", {}).get("text")]
        BackendObservability.info(f"Standardized {len(places)} places from raw results.", conversation_id=args.trace_id)

        # Write to cache file
        try:
            with open(cache_path, "w") as f:
                f.write(json.dumps(places, indent=2))
            BackendObservability.trace(f"Successfully cached {len(places)} places at {cache_path}", conversation_id=args.trace_id)
        except Exception as exc:
            BackendObservability.warning(f"Error writing to cache file: {exc}", conversation_id=args.trace_id)

    # Apply pagination
    total = len(places)
    offset = args.offset
    limit = args.limit
    paginated_places = places[offset:offset+limit]
    has_more = offset + limit < total
    BackendObservability.info(f"Returning {len(paginated_places)}/{total} places (has_more={has_more})", conversation_id=args.trace_id)

    # Print JSON output to stdout
    output = {
        "places": paginated_places,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": has_more
    }
    sys.stdout.write(json.dumps(output))


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
