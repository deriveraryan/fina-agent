"""Unit tests for the Google Places Text Search API discovery module.

Runs completely offline using unittest mocks.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from features.scanning.sources.maps_scanner import discover_places_listings, _parse_opening_hours


class TestMapsScanner(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for the Google Places Text Search API scanner."""

    async def test_maps_scanner_mock_mode(self) -> None:
        """Tests that discover_places_listings correctly returns mock results in fallback/mock mode."""
        with patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "mock-key"}):
            results = await discover_places_listings("SYDNEY", "RESTAURANT")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["name"], "Mock Manila Diner Sydney")
            self.assertEqual(results[0]["category"], "RESTAURANT")
            self.assertEqual(results[0]["city"], "SYDNEY")
            self.assertEqual(results[0]["phone"], "+61 2 9999 1111")

    @patch("httpx.AsyncClient.post")
    @patch("features.scanning.sources.maps_scanner.verify_filipino_affiliation")
    async def test_maps_scanner_text_search_parsing(self, mock_verify: AsyncMock, mock_post: AsyncMock) -> None:
        """Tests that discover_places_listings correctly queries Places API and parses returned details."""
        mock_verify.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "places": [
                {
                    "id": "place_id_123",
                    "displayName": {"text": "Pinoy Restaurant Sydney"},
                    "formattedAddress": "100 Pitt St, Sydney NSW 2000",
                    "location": {"latitude": -33.86, "longitude": 151.2},
                    "types": ["restaurant", "food"],
                    "regularOpeningHours": {
                        "weekdayDescriptions": [
                            "Monday: 9:00 AM – 5:00 PM",
                            "Tuesday: 9:00 AM – 5:00 PM"
                        ]
                    },
                    "websiteUri": "https://pinoyrestaurant.example.com",
                    "internationalPhoneNumber": "+61 2 9999 5555"
                }
            ]
        }
        mock_post.return_value = mock_response

        with patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "real-api-key"}):
            results = await discover_places_listings("SYDNEY", "RESTAURANT")
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["name"], "Pinoy Restaurant Sydney")
            self.assertEqual(results[0]["address"], "100 Pitt St, Sydney NSW 2000")
            self.assertEqual(results[0]["latitude"], -33.86)
            self.assertEqual(results[0]["longitude"], 151.2)
            self.assertEqual(results[0]["phone"], "+61 2 9999 5555")
            self.assertEqual(results[0]["website"], "https://pinoyrestaurant.example.com")
            self.assertIn("mon", results[0]["operatingHours"])

    def test_parse_opening_hours(self) -> None:
        """Tests opening hours conversions from Google array format to structured JSON string."""
        weekday_descriptions = [
            "Monday: 9:00 AM – 5:00 PM",
            "Tuesday: Closed",
            "Sunday: 10:00 AM – 2:00 PM"
        ]
        parsed = _parse_opening_hours(weekday_descriptions)
        self.assertIsNotNone(parsed)
        self.assertIn('"mon": "9:00 AM \\u2013 5:00 PM"', parsed)
        self.assertIn('"tue": "Closed"', parsed)
        self.assertIn('"sun": "10:00 AM \\u2013 2:00 PM"', parsed)


if __name__ == "__main__":
    unittest.main()
