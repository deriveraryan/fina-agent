"""Unit tests for geocoding street addresses and fallback mapping.

Runs completely offline using unittest mocks.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from features.scanning.sources.geocoder import geocode_address, get_city_fallback_coordinates


class TestGeocoder(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for the geocoding engine."""

    @patch("httpx.AsyncClient.get")
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "fake-key"})
    async def test_geocoder_resolution_success(self, mock_get: AsyncMock) -> None:
        """Tests that geocode_address resolves street addresses to coordinates correctly via Google Geocoding API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "geometry": {
                        "location": {
                            "lat": -33.8688,
                            "lng": 151.2093,
                        }
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        lat, lng = await geocode_address("483 George St, Sydney NSW 2000", "SYDNEY")

        self.assertEqual(lat, -33.8688)
        self.assertEqual(lng, 151.2093)
        mock_get.assert_called_once()

    @patch("httpx.AsyncClient.get")
    async def test_geocoder_resolution_fallback_no_key(self, mock_get: AsyncMock) -> None:
        """Tests that geocode_address falls back to default city center when no Google key is configured."""
        with patch.dict("os.environ", {}, clear=True):
            lat, lng = await geocode_address("483 George St, Sydney NSW 2000", "SYDNEY")
            
            # Default fallback for SYDNEY is -33.8688, 151.2093
            self.assertEqual(lat, -33.8688)
            self.assertEqual(lng, 151.2093)
            mock_get.assert_not_called()

    async def test_geocoder_empty_address(self) -> None:
        """Tests that geocode_address handles empty strings by immediately returning fallbacks."""
        lat, lng = await geocode_address("", "MELBOURNE")
        self.assertEqual(lat, -37.8136)
        self.assertEqual(lng, 144.9631)


if __name__ == "__main__":
    unittest.main()
