"""Google Places API scanner utilizing Gemini verification.

Integrates with the Google Places API (New) using Text Search and field masking,
and executes a Gemini verification prompt to verify Filipino association.
"""

import os
import json
import re
import asyncio
import time
import httpx
from typing import Any
from google import genai
from features.shared.observability import BackendObservability, trace_performance

# Strict 60 RPM (1-second spacing) rate-limiting lock and timestamp
_gemini_rate_limit_lock = asyncio.Lock()
_last_gemini_request_time = 0.0



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
    ]
}


async def discover_places_listings(city: str, category: str) -> list[dict[str, Any]]:
    """Discovers local directories using Google Places API and filters using Gemini.

    Args:
        city: City name (e.g. 'SYDNEY').
        category: Core category targeting (e.g. 'RESTAURANT').

    Returns:
        List of listing dicts containing name, address, phone, website, operatingHours, etc.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "mock-key":
        BackendObservability.warning(
            f"GOOGLE_MAPS_API_KEY is '{api_key or 'None'}'. Running Google Places scanner in mock mode."
        )
        return _get_mock_listings(city, category)

    templates = SEARCH_TEMPLATES.get(category, [])
    if not templates:
        return []

    discovered: list[dict[str, Any]] = []
    seen_place_ids: set[str] = set()

    for template in templates:
        query = template.format(city=city.title())
        BackendObservability.info(f"Searching Google Places for: '{query}'")

        try:
            places = await _execute_places_text_search(query, api_key)
            for place in places:
                place_id = place.get("id")
                if not place_id or place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                # Extract basic attributes
                display_name_obj = place.get("displayName") or {}
                name = display_name_obj.get("text", "")
                if not name:
                    continue

                # Run Filipino affiliation check using Gemini
                editorial_obj = place.get("editorialSummary") or {}
                editorial = editorial_obj.get("text", "")
                types = place.get("types", [])

                # Extract top reviews text for richer context
                reviews_list = place.get("reviews", [])
                review_texts = [
                    r.get("text", {}).get("text", "")
                    for r in reviews_list
                    if isinstance(r, dict) and r.get("text", {}).get("text")
                ]

                is_filipino = await verify_filipino_affiliation(
                    name=name,
                    types=types,
                    editorial_summary=editorial,
                    reviews=review_texts
                )

                if not is_filipino:
                    BackendObservability.trace(
                        f"Skipping place '{name}' - Gemini verified non-Filipino."
                    )
                    continue

                BackendObservability.info(f"Verified Filipino affiliation for: '{name}'")

                # Parse operating hours
                operating_hours_json = None
                hours_obj = place.get("regularOpeningHours") or {}
                weekday_descriptions = hours_obj.get("weekdayDescriptions")
                if weekday_descriptions:
                    operating_hours_json = _parse_opening_hours(weekday_descriptions)

                # Resolve coordinates
                location = place.get("location") or {}
                lat = location.get("latitude")
                lng = location.get("longitude")

                if lat is None or lng is None:
                    continue

                discovered.append({
                    "name": name,
                    "category": category,
                    "city": city,
                    "address": place.get("formattedAddress", f"{city.title()} CBD, Australia"),
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "phone": place.get("internationalPhoneNumber"),
                    "website": place.get("websiteUri"),
                    "operatingHours": operating_hours_json,
                    "description": editorial or f"A verified Filipino {category.lower()} in {city.title()}.",
                    "imageUrl": None,
                    "sourceUrl": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    "tags": f"filipino,{category.lower()},google-maps",
                })

        except Exception as exc:
            BackendObservability.error(
                f"Error executing search query for '{query}'",
                exception=exc
            )

    return discovered


async def _execute_places_text_search(query: str, api_key: str) -> list[dict[str, Any]]:
    """Calls Google Places API (New) Text Search endpoint asynchronously."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.location,"
            "places.websiteUri,places.internationalPhoneNumber,places.regularOpeningHours,"
            "places.editorialSummary,places.types,places.reviews"
        )
    }
    body = {
        "textQuery": query,
        "languageCode": "en"
    }

    async with httpx.AsyncClient() as client:
        with trace_performance("places_text_search", budget=5.0):
            response = await client.post(url, json=body, headers=headers, timeout=20.0)

        if response.status_code != 200:
            raise RuntimeError(
                f"Places API returned status code {response.status_code}: {response.text}"
            )

        data = response.json()
        return data.get("places", [])


async def verify_filipino_affiliation(
    name: str,
    types: list[str],
    editorial_summary: str,
    reviews: list[str]
) -> bool:
    """Uses Gemini to analyze place information and verify if it represents a Filipino entity."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        # Default fallback in case the API key is not configured in local environment tests
        # We perform simple substring heuristics as fallback
        name_lower = name.lower()
        keywords = ["filipino", "pinoy", "inasal", "lechon", "sari", "adobo", "tagalog", "kapamilya", "cebu", "manila"]
        if any(k in name_lower for k in keywords):
            return True
        return False

    prompt = (
        "Analyze this business/organization details to determine if it is authentic Filipino-affiliated "
        "(e.g., owned by Filipinos, serves Filipino cuisine, sells Filipino products, holds Filipino Tagalog/fellowship services, "
        "or has a clear connection to the Filipino diaspora in Australia).\n\n"
        f"Name: {name}\n"
        f"Types: {types}\n"
        f"Editorial Summary: {editorial_summary}\n"
        f"Reviews: {reviews[:3]}\n\n"
        "Respond with a single JSON object having one key: 'is_filipino' (boolean value, true or false). "
        "Do not output markdown block wrappers."
    )

    global _last_gemini_request_time
    async with _gemini_rate_limit_lock:
        max_retries = 3
        for attempt in range(max_retries):
            now = time.time()
            elapsed = now - _last_gemini_request_time
            # Space out calls by at least 1.0 second to limit to 60 RPM
            if elapsed < 1.0:
                sleep_duration = 1.0 - elapsed
                BackendObservability.info(
                    f"Gemini API rate limiter: sleeping for {sleep_duration:.2f}s to respect 60 RPM limit."
                )
                await asyncio.sleep(sleep_duration)

            # Record the start time of the actual API call
            _last_gemini_request_time = time.time()

            try:
                client = genai.Client()
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=prompt
                )
                text = response.text
                if not text:
                    return False

                # Attempt to parse json
                json_match = re.search(r"({.*})", text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    return bool(parsed.get("is_filipino", False))

                # Basic text check in case JSON formatting was missed
                return "true" in text.lower()
            except Exception as exc:
                exc_str = str(exc)
                if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                    retry_seconds = 15.0  # default fallback retry delay
                    
                    # Extract the "Please retry in X.Xs" delay
                    match = re.search(r"Please retry in ([0-9.]+)\s*s", exc_str, re.IGNORECASE)
                    if match:
                        try:
                            retry_seconds = float(match.group(1))
                        except ValueError:
                            pass
                    elif "retryDelay" in exc_str:
                        match_delay = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"]([0-9]+)s['\"]", exc_str)
                        if match_delay:
                            try:
                                retry_seconds = float(match_delay.group(1))
                            except ValueError:
                                pass
                    
                    # Add 0.5s padding to be safe
                    sleep_time = retry_seconds + 0.5
                    
                    if attempt < max_retries - 1:
                        BackendObservability.warning(
                            f"Gemini API 429 rate limit hit for '{name}'. Sleeping/throttling for {sleep_time:.2f}s before retry attempt {attempt + 2}/{max_retries}."
                        )
                        _last_gemini_request_time = time.time() + sleep_time
                        await asyncio.sleep(sleep_time)
                        continue

                BackendObservability.warning(
                    f"Failed Gemini verification for place '{name}' after {attempt + 1} attempts, falling back to keyword heuristics.",
                    exception=exc
                )
                break

        # Quick fallback heuristic
        name_lower = name.lower()
        keywords = ["filipino", "pinoy", "inasal", "lechon", "sari", "adobo", "tagalog", "kapamilya", "cebu", "manila"]
        return any(k in name_lower for k in keywords)


def _parse_opening_hours(weekday_descriptions: list[str]) -> str | None:
    """Parses standard Google weekday descriptions array to structured operatingHours JSON string.

    Format: {"mon": "9:00-17:00", ...}
    """
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
            # Map "Closed" or hours directly
            result[target_day] = hours

    if not result:
        return None
    return json.dumps(result)


def _get_mock_listings(city: str, category: str) -> list[dict[str, Any]]:
    """Returns mock/stub listing results for offline/test environments."""
    city_title = city.title()
    if category == "RESTAURANT":
        return [
            {
                "name": f"Mock Manila Diner {city_title}",
                "category": category,
                "city": city,
                "address": f"123 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"123 Collins St, {city_title} VIC 3000",
                "latitude": -33.8688 if city == "SYDNEY" else -37.8136,
                "longitude": 151.2093 if city == "SYDNEY" else 144.9631,
                "phone": "+61 2 9999 1111",
                "website": "https://maniladiner.example.com",
                "operatingHours": '{"mon":"11:00 AM – 9:00 PM","tue":"11:00 AM – 9:00 PM","wed":"11:00 AM – 9:00 PM","thu":"11:00 AM – 9:00 PM","fri":"11:00 AM – 10:00 PM","sat":"11:00 AM – 10:00 PM","sun":"11:00 AM – 9:00 PM"}',
                "description": "Authentic Manila style diners serving signature lechon and adobo.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_restaurant_1",
                "tags": "filipino,restaurant,google-maps",
            }
        ]
    elif category == "CAFE":
        return [
            {
                "name": f"Mock Pinoy Brew {city_title}",
                "category": category,
                "city": city,
                "address": f"45 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"45 Collins St, {city_title} VIC 3000",
                "latitude": -33.8695 if city == "SYDNEY" else -37.8142,
                "longitude": 151.2085 if city == "SYDNEY" else 144.9625,
                "phone": "+61 2 9999 2222",
                "website": "https://pinoybrew.example.com",
                "operatingHours": '{"mon":"7:00 AM – 4:00 PM","tue":"7:00 AM – 4:00 PM","wed":"7:00 AM – 4:00 PM","thu":"7:00 AM – 4:00 PM","fri":"7:00 AM – 4:00 PM","sat":"8:00 AM – 3:00 PM","sun":"Closed"}',
                "description": "Cozy café featuring specialty ube lattes and pandesal toast.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_cafe_1",
                "tags": "filipino,cafe,google-maps",
            }
        ]
    elif category == "SHOP":
        return [
            {
                "name": f"Mock Sari Sari Mart {city_title}",
                "category": category,
                "city": city,
                "address": f"88 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"88 Collins St, {city_title} VIC 3000",
                "latitude": -33.8702 if city == "SYDNEY" else -37.8150,
                "longitude": 151.2078 if city == "SYDNEY" else 144.9618,
                "phone": "+61 2 9999 3333",
                "website": "https://sarisarimart.example.com",
                "operatingHours": '{"mon":"9:00 AM – 7:00 PM","tue":"9:00 AM – 7:00 PM","wed":"9:00 AM – 7:00 PM","thu":"9:00 AM – 8:00 PM","fri":"9:00 AM – 8:00 PM","sat":"9:00 AM – 6:00 PM","sun":"10:00 AM – 5:00 PM"}',
                "description": "Well stocked grocery store with Filipino brand goods and imported ingredients.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_shop_1",
                "tags": "filipino,shop,google-maps",
            }
        ]
    elif category == "CHURCH":
        return [
            {
                "name": f"Mock Tagalog Fellowship {city_title}",
                "category": category,
                "city": city,
                "address": f"10 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"10 Collins St, {city_title} VIC 3000",
                "latitude": -33.8680 if city == "SYDNEY" else -37.8125,
                "longitude": 151.2100 if city == "SYDNEY" else 144.9640,
                "phone": "+61 2 9999 4444",
                "website": "https://tagalogfellowship.example.com",
                "operatingHours": '{"sun":"9:00 AM – 1:00 PM"}',
                "description": "Filipino Christian worship service and community fellowship.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_church_1",
                "tags": "filipino,church,google-maps",
            }
        ]
    elif category == "COMMUNITY":
        return [
            {
                "name": f"Mock Filipino Community Association {city_title}",
                "category": category,
                "city": city,
                "address": f"100 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"100 Collins St, {city_title} VIC 3000",
                "latitude": -33.8680 if city == "SYDNEY" else -37.8125,
                "longitude": 151.2100 if city == "SYDNEY" else 144.9640,
                "phone": "+61 2 9999 5555",
                "website": "https://filcommunity.example.com",
                "operatingHours": '{"sun":"9:00 AM – 5:00 PM"}',
                "description": f"Filipino community group in {city_title}.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_community_1",
                "tags": "filipino,community,google-maps",
            }
        ]
    elif category == "GOVERNMENT":
        return [
            {
                "name": f"Mock Philippine Consulate {city_title}",
                "category": category,
                "city": city,
                "address": f"15 Pitt St, {city_title} NSW 2000" if city == "SYDNEY" else f"15 Collins St, {city_title} VIC 3000",
                "latitude": -33.8685 if city == "SYDNEY" else -37.8130,
                "longitude": 151.2095 if city == "SYDNEY" else 144.9635,
                "phone": "+61 2 9999 6666",
                "website": "https://phconsulate.example.com",
                "operatingHours": '{"mon":"9:00 AM – 5:00 PM","tue":"9:00 AM – 5:00 PM","wed":"9:00 AM – 5:00 PM","thu":"9:00 AM – 5:00 PM","fri":"9:00 AM – 5:00 PM"}',
                "description": f"Philippine consular services office in {city_title}.",
                "imageUrl": None,
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:mock_gov_1",
                "tags": "filipino,gov,google-maps",
            }
        ]
    return []
