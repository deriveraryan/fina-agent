"""Pure parsing functions for extracting structured data from Google Maps browser output.

Provides deterministic parsers for lat/lng coordinates from URLs,
opening hours from visible text, and address normalization. These are
used by the fina_listing_web_search agent during Round 4 (Google Maps
browser search) to convert raw browser-extracted text into the
standardized listing payload format.
"""

import json
import re
from typing import Optional, Tuple


# Regex pattern for extracting lat/lng from Google Maps URLs.
# Matches patterns like: @-33.8688197,151.2092955,17z
_LAT_LNG_PATTERN = re.compile(
    r"@(-?\d+\.?\d*),(-?\d+\.?\d*),\d+\.?\d*z"
)

# Maps day names to short keys used in the operatingHours JSON schema.
# Public constant — also imported by agent_places_api_fetch.py to avoid duplication.
DAYS_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def parse_lat_lng_from_url(url: Optional[str]) -> Optional[Tuple[float, float]]:
    """Extract latitude and longitude from a Google Maps URL.

    Parses the @lat,lng,zoomz pattern or the !3dlat!4dlng data pattern
    commonly found in Google Maps place and search URLs after navigation.

    Args:
        url: A Google Maps URL string.

    Returns:
        A (latitude, longitude) tuple of floats, or None if the pattern
        is not found or coordinates cannot be parsed.
    """
    if not url:
        return None

    # First try parsing actual place coordinates from data parameter if present
    match_data = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", url)
    if match_data:
        try:
            return (float(match_data.group(1)), float(match_data.group(2)))
        except (ValueError, TypeError):
            pass

    # Fallback to the map viewport center coordinates
    match = _LAT_LNG_PATTERN.search(url)
    if not match:
        return None

    try:
        lat = float(match.group(1))
        lng = float(match.group(2))
        return (lat, lng)
    except (ValueError, TypeError):
        return None


def parse_maps_opening_hours(hours_text: Optional[str]) -> Optional[str]:
    """Parse Maps browser opening hours text to structured JSON string.

    Converts visible text from the Maps hours section (e.g.,
    "Monday: 9 AM – 5 PM\\nTuesday: 10 AM – 4 PM") into the
    standardized JSON format: {"mon": "9 AM – 5 PM", "tue": "10 AM – 4 PM"}.

    Handles newline-separated, semicolon-separated, and mixed formats.
    Day names are matched case-insensitively.

    Args:
        hours_text: Raw hours text extracted from the Maps detail panel.

    Returns:
        A JSON string of day-keyed hours, or None if no recognizable
        day patterns are found or input is empty.
    """
    if not hours_text:
        return None

    result = {}

    # Replace private use area newline markers with actual newlines
    hours_text = hours_text.replace("", "\n")

    # Split on newlines and semicolons to handle both formats
    lines = re.split(r"[\n;]", hours_text)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to find which day name this line starts with
        line_lower = line.lower()
        matched_day = None
        for day_name in DAYS_MAP:
            if line_lower.startswith(day_name):
                matched_day = day_name
                break

        if not matched_day:
            continue

        # Extract the hours part by removing the day name prefix
        hours_part = line[len(matched_day):].strip()
        # If there is a colon or comma separator, strip it
        while hours_part and (hours_part.startswith(":") or hours_part.startswith(",")):
            hours_part = hours_part[1:].strip()

        short_day = DAYS_MAP[matched_day]
        if hours_part:
            result[short_day] = hours_part

    if not result:
        return None

    return json.dumps(result)


def parse_maps_address(raw_address: Optional[str]) -> str:
    """Normalize a raw address string extracted from the Maps detail panel.

    Strips leading/trailing whitespace, replaces newlines with comma
    separators, and collapses multiple internal spaces into single spaces.
    Also strips Google Maps private use area icon characters.

    Args:
        raw_address: Raw address text from the Maps business info panel.

    Returns:
        A cleaned, normalized address string. Returns empty string
        for None or whitespace-only input.
    """
    if not raw_address:
        return ""

    # Strip Google Maps icon characters (Private Use Area)
    cleaned = re.sub(r"[\ue000-\uf8ff]", "", raw_address)

    # Replace newlines with comma-space for multi-line addresses
    cleaned = cleaned.replace("\n", ", ")

    # Collapse multiple spaces into single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()
