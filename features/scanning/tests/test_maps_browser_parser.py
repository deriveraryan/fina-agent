"""Unit tests for maps_browser_parser module.

Tests pure parsing functions for extracting structured data from
Google Maps browser DOM text and URLs.
"""

import json
import unittest

from features.scanning.maps_browser_parser import (
    parse_lat_lng_from_url,
    parse_maps_opening_hours,
    parse_maps_address,
)


class TestParseLatLngFromUrl(unittest.TestCase):
    """Tests for extracting latitude/longitude from Google Maps URLs."""

    def test_standard_url_pattern(self) -> None:
        url = "https://www.google.com/maps/place/Some+Place/@-33.8688197,151.2092955,17z"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], -33.8688197, places=6)
        self.assertAlmostEqual(result[1], 151.2092955, places=6)

    def test_positive_lat_lng(self) -> None:
        url = "https://www.google.com/maps/place/Manila/@14.5995124,120.9842195,13z"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 14.5995124, places=6)
        self.assertAlmostEqual(result[1], 120.9842195, places=6)

    def test_negative_longitude(self) -> None:
        url = "https://www.google.com/maps/place/New+York/@40.7127753,-74.0059728,11z"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 40.7127753, places=6)
        self.assertAlmostEqual(result[1], -74.0059728, places=6)

    def test_search_url_pattern(self) -> None:
        url = "https://www.google.com/maps/search/Filipino+restaurant/@-33.8688,151.2093,15z"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], -33.8688, places=4)
        self.assertAlmostEqual(result[1], 151.2093, places=4)

    def test_url_with_data_suffix(self) -> None:
        """Maps URLs often have extra data parameters after the zoom level."""
        url = "https://www.google.com/maps/place/Test/@-33.8688,151.2093,17z/data=!3m1!4b1"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], -33.8688, places=4)
        self.assertAlmostEqual(result[1], 151.2093, places=4)

    def test_url_with_3d_4d_data_parameter(self) -> None:
        """Should parse exact place coordinates from !3d and !4d parameters in URL."""
        url = "https://www.google.com/maps/place/Casa+Filipina+Bakeshop+%26+Restaurant/@-33.9988874,150.5621008,11z/data=!4m11!1m3!2m2!1sFilipino+restaurant+near+Hoxton+Park,+SYDNEY!6e5!3m6!1s0x6b12eb9ce74e7bab:0x935797944b5a9659!8m2!3d-33.9988874!4d150.8669714"
        result = parse_lat_lng_from_url(url)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], -33.9988874, places=6)
        self.assertAlmostEqual(result[1], 150.8669714, places=6)

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(parse_lat_lng_from_url("https://www.google.com/maps"))
        self.assertIsNone(parse_lat_lng_from_url("https://www.google.com"))
        self.assertIsNone(parse_lat_lng_from_url(""))

    def test_none_input_returns_none(self) -> None:
        self.assertIsNone(parse_lat_lng_from_url(None))

    def test_malformed_coordinates(self) -> None:
        """Coordinates with non-numeric values should return None."""
        url = "https://www.google.com/maps/place/Test/@abc,def,17z"
        self.assertIsNone(parse_lat_lng_from_url(url))


class TestParseMapsOpeningHours(unittest.TestCase):
    """Tests for parsing Maps browser opening hours text."""

    def test_standard_weekday_hours(self) -> None:
        hours_text = (
            "Monday: 9 AM – 5 PM\n"
            "Tuesday: 9 AM – 5 PM\n"
            "Wednesday: 9 AM – 5 PM\n"
            "Thursday: 9 AM – 5 PM\n"
            "Friday: 9 AM – 5 PM\n"
            "Saturday: 10 AM – 3 PM\n"
            "Sunday: Closed"
        )
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "9 AM – 5 PM")
        self.assertEqual(parsed["tue"], "9 AM – 5 PM")
        self.assertEqual(parsed["sat"], "10 AM – 3 PM")
        self.assertEqual(parsed["sun"], "Closed")

    def test_open_24_hours(self) -> None:
        hours_text = (
            "Monday: Open 24 hours\n"
            "Tuesday: Open 24 hours\n"
            "Wednesday: Open 24 hours\n"
            "Thursday: Open 24 hours\n"
            "Friday: Open 24 hours\n"
            "Saturday: Open 24 hours\n"
            "Sunday: Open 24 hours"
        )
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "Open 24 hours")
        self.assertEqual(parsed["sun"], "Open 24 hours")

    def test_all_closed(self) -> None:
        hours_text = (
            "Monday: Closed\n"
            "Tuesday: Closed\n"
            "Wednesday: Closed\n"
            "Thursday: Closed\n"
            "Friday: Closed\n"
            "Saturday: Closed\n"
            "Sunday: Closed"
        )
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
            self.assertEqual(parsed[day], "Closed")

    def test_semicolon_separator(self) -> None:
        """Maps sometimes uses semicolons instead of newlines."""
        hours_text = "Monday: 9 AM – 5 PM; Tuesday: 10 AM – 6 PM; Wednesday: 9 AM – 5 PM"
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "9 AM – 5 PM")
        self.assertEqual(parsed["tue"], "10 AM – 6 PM")

    def test_multiple_time_ranges(self) -> None:
        """Some businesses have split hours (e.g., lunch and dinner)."""
        hours_text = "Monday: 11 AM – 2 PM, 5 PM – 9 PM\nTuesday: 11 AM – 2 PM, 5 PM – 9 PM"
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "11 AM – 2 PM, 5 PM – 9 PM")

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(parse_maps_opening_hours(""))
        self.assertIsNone(parse_maps_opening_hours(None))

    def test_no_recognizable_days_returns_none(self) -> None:
        self.assertIsNone(parse_maps_opening_hours("No hours available"))

    def test_extra_whitespace_handling(self) -> None:
        hours_text = "  Monday:   9 AM – 5 PM  \n  Tuesday:   10 AM – 4 PM  "
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "9 AM – 5 PM")
        self.assertEqual(parsed["tue"], "10 AM – 4 PM")

    def test_case_insensitive_day_names(self) -> None:
        hours_text = "MONDAY: 9 AM – 5 PM\ntuesday: 10 AM – 4 PM"
        result = parse_maps_opening_hours(hours_text)
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["mon"], "9 AM – 5 PM")
        self.assertEqual(parsed["tue"], "10 AM – 4 PM")


class TestParseMapsAddress(unittest.TestCase):
    """Tests for normalizing Maps address text."""

    def test_standard_address(self) -> None:
        self.assertEqual(
            parse_maps_address("123 George St, Sydney NSW 2000, Australia"),
            "123 George St, Sydney NSW 2000, Australia",
        )

    def test_strips_unicode_icons(self) -> None:
        self.assertEqual(
            parse_maps_address("54 Oxford Rd, Ingleburn NSW 2565"),
            "54 Oxford Rd, Ingleburn NSW 2565",
        )

    def test_strips_whitespace(self) -> None:
        self.assertEqual(
            parse_maps_address("  123 George St, Sydney NSW 2000  "),
            "123 George St, Sydney NSW 2000",
        )

    def test_normalizes_internal_whitespace(self) -> None:
        self.assertEqual(
            parse_maps_address("123  George   St,  Sydney  NSW  2000"),
            "123 George St, Sydney NSW 2000",
        )

    def test_strips_newlines(self) -> None:
        self.assertEqual(
            parse_maps_address("123 George St\nSydney NSW 2000"),
            "123 George St, Sydney NSW 2000",
        )

    def test_empty_returns_empty(self) -> None:
        self.assertEqual(parse_maps_address(""), "")
        self.assertEqual(parse_maps_address("   "), "")

    def test_none_returns_empty(self) -> None:
        self.assertEqual(parse_maps_address(None), "")


if __name__ == "__main__":
    unittest.main()
