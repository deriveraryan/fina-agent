"""Google Maps Geocoding API utility for resolving street addresses to coordinates.
"""

import os
from typing import Any
import httpx
from features.shared.observability import BackendObservability

# Global AsyncClient instance for connection reuse
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


# Predefined central coordinates for major Australian cities to use as fallback
CITY_CENTRAL_COORDINATES: dict[str, tuple[float, float]] = {
    "SYDNEY": (-33.8688, 151.2093),
    "MELBOURNE": (-37.8136, 144.9631),
    "BRISBANE": (-27.4705, 153.0260),
    "PERTH": (-31.9505, 115.8605),
    "ADELAIDE": (-34.9285, 138.6007),
    "DARWIN": (-12.4634, 130.8456),
    "HOBART": (-42.8821, 147.3272),
    "CANBERRA": (-35.2809, 149.1300),
    "GOLD COAST": (-28.0167, 153.4000),
    "GOLD_COAST": (-28.0167, 153.4000),
}


AUSTRALIA_DEFAULT_CENTER: tuple[float, float] = (-35.2809, 149.1300)  # Canberra, ACT


def get_city_fallback_coordinates(city_context: str) -> tuple[float, float]:
    """Retrieves central coordinates for a city, falling back to Canberra if unknown."""
    normalized_city = city_context.upper().strip().replace("_", " ")
    coords = CITY_CENTRAL_COORDINATES.get(normalized_city)
    if coords:
        return coords
    BackendObservability.warning(
        f"Unknown city context '{city_context}' for coordinates mapping. "
        f"Using default Australian center (Canberra) {AUSTRALIA_DEFAULT_CENTER} instead."
    )
    return AUSTRALIA_DEFAULT_CENTER



async def geocode_address(address: str, city_context: str) -> tuple[float, float]:
    """Converts a textual street address into exact (latitude, longitude) coordinates.

    Uses the Google Maps Geocoding API if GOOGLE_MAPS_API_KEY is available;
    otherwise falls back to the central coordinates of the target city.

    Args:
        address: Text address to geocode.
        city_context: Target city identifier (e.g. 'SYDNEY') for backup coordinates.

    Returns:
        A tuple of (latitude, longitude) floats.
    """
    if not address or address.strip() == "":
        BackendObservability.warning(
            f"Empty address supplied for geocoding in {city_context}. Falling back to city center."
        )
        return get_city_fallback_coordinates(city_context)

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        BackendObservability.warning(
            "GOOGLE_MAPS_API_KEY is not configured. Falling back to city center for address: "
            f"'{address}'"
        )
        return get_city_fallback_coordinates(city_context)

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": f"{address}, Australia",
        "key": api_key,
    }

    try:
        client = _get_client()
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        results: list[dict[str, Any]] = data.get("results", [])
        if not results:
            BackendObservability.warning(
                f"Geocoding API returned zero results for address: '{address}'. Falling back to city center."
            )
            return get_city_fallback_coordinates(city_context)

        location = results[0].get("geometry", {}).get("location", {})
        lat = float(location.get("lat", 0.0))
        lng = float(location.get("lng", 0.0))

        BackendObservability.info(
            f"Geocoding success: '{address}' -> ({lat}, {lng})"
        )
        return lat, lng

    except Exception as exc:
        BackendObservability.error(
            f"Geocoding failed for address: '{address}'. Falling back to city center.",
            exception=exc,
        )
        return get_city_fallback_coordinates(city_context)

