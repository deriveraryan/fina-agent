import os
import unittest
import tempfile
import json
from datetime import datetime
from features.scanning.tracker import (
    init_tracker,
    add_search,
    add_candidate,
    add_error,
    generate_report,
)


class TestWebFinderTracker(unittest.TestCase):
    """Unit tests for the deterministic web finder tracker and report generator."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tracker_path = os.path.join(self.temp_dir.name, "web_finder_tracker.json")
        self.template_path = os.path.join(self.temp_dir.name, "REPORT_TEMPLATE.md")
        self.suburbs_path = os.path.join(self.temp_dir.name, "top_suburbs_per_city.json")
        self.logs_dir = os.path.join(self.temp_dir.name, "logs")

        # Mock top_suburbs_per_city.json
        self.mock_suburbs = {
            "sydney": ["Chatswood", "Parramatta", "Blacktown", "Bondi Junction"],
            "melbourne": ["Craigieburn", "Point Cook"]
        }
        with open(self.suburbs_path, "w", encoding="utf-8") as f:
            json.dump(self.mock_suburbs, f)

        # Mock REPORT_TEMPLATE.md with suburb placeholders
        self.mock_template = """# Fina New Listing Web Finder Report — {CITY}

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_new_listing_web_finder |
| **Target City** | {CITY} |
| **Platforms Searched** | {PLATFORMS} |
| **Search Template Index** | `[{INDEX}]` |
| **Search Template String** | `{TEMPLATE_STRING}` |
| **Formatted Query** | `{FORMATTED_QUERY}` |
| **Execution Date** | {EXECUTION_DATE} |
| **Trace ID** | `{TRACE_ID}` |
| **Search Locations / Suburbs** | {SEARCH_SUBURBS} |

## Summary

| Metric | Count |
| :--- | :--- |
| **Web Searches Made** | {WEB_SEARCHES_MADE} |
| **Total Pages Read** | {TOTAL_PAGES_READ} |
| **Total Candidate Pages Evaluated** | {CANDIDATES_EVALUATED} |
| **Verified Listings Created** | {LISTINGS_CREATED} |
| **Candidates Rejected** | {CANDIDATES_REJECTED} |
| **Total Suburbs Searched** | {TOTAL_SUBURBS_SEARCHED} |
| **Errors Encountered** | {ERRORS_ENCOUNTERED} |

## Verified Community Listings

### Created Listings

{CREATED_LISTINGS}

## Skipped / Rejected Candidates

{REJECTED_TABLE}

## Search Log Details

{SEARCH_LOG_DETAILS}

## Errors & Warnings

{ERRORS_LIST}
"""
        with open(self.template_path, "w", encoding="utf-8") as f:
            f.write(self.mock_template)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_tracker_creates_file_with_defaults(self) -> None:
        """Initializing a tracker should create the state file with expected schema and fields."""
        init_tracker(
            city="Sydney",
            category="RESTAURANT",
            template_index=2,
            template_string="Filipino food truck in {city}",
            formatted_query="Filipino food truck in Sydney",
            trace_id="test-trace-id",
            tracker_path=self.tracker_path,
        )

        self.assertTrue(os.path.exists(self.tracker_path))
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["city"], "Sydney")
        self.assertEqual(data["category"], "RESTAURANT")
        self.assertEqual(data["search_template_index"], 2)
        self.assertEqual(data["search_template_string"], "Filipino food truck in {city}")
        self.assertEqual(data["formatted_query"], "Filipino food truck in Sydney")
        self.assertEqual(data["trace_id"], "test-trace-id")
        self.assertEqual(data["searches"], [])
        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["errors"], [])
        self.assertTrue("execution_date" in data)

    def test_add_search_appends_and_updates_metrics(self) -> None:
        """Adding searches should append to the list and increment metrics."""
        init_tracker("Sydney", "RESTAURANT", 2, "test", "test", "trace", self.tracker_path)

        add_search("query1", "Facebook", 1, self.tracker_path, suburbs_path=self.suburbs_path)
        add_search("query2", "Instagram", 2, self.tracker_path, suburbs_path=self.suburbs_path)

        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data["searches"]), 2)
        self.assertEqual(data["searches"][0]["query"], "query1")
        self.assertEqual(data["searches"][0]["platform"], "Facebook")
        self.assertEqual(data["searches"][0]["pages_read"], 1)

    def test_add_candidate_appends_evaluations(self) -> None:
        """Adding candidate should save all metadata and evaluation details."""
        init_tracker("Sydney", "RESTAURANT", 2, "test", "test", "trace", self.tracker_path)

        add_candidate(
            name="Bar-B-Skew",
            url="https://facebook.com/barbskew",
            platform="Facebook",
            status="CREATED",
            reason="Authentic food truck",
            db_id="12345",
            address="123 St",
            description="Nice truck",
            tags="google-search",
            category="RESTAURANT",
            tracker_path=self.tracker_path,
        )

        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data["candidates"]), 1)
        c = data["candidates"][0]
        self.assertEqual(c["name"], "Bar-B-Skew")
        self.assertEqual(c["status"], "CREATED")
        self.assertEqual(c["db_id"], "12345")

    def test_add_error_records_warnings(self) -> None:
        """Adding error should append message to error list."""
        init_tracker("Sydney", "RESTAURANT", 2, "test", "test", "trace", self.tracker_path)

        add_error("Network timeout on FB search", self.tracker_path)

        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["errors"], ["Network timeout on FB search"])

    def test_suburb_resolution_and_reporting(self) -> None:
        """The tracker should automatically resolve suburbs from search queries and populate log tables and metadata."""
        init_tracker("Sydney", "RESTAURANT", 1, "Filipino shop in {city}", "Filipino shop in Sydney", "trace-id-123", self.tracker_path)

        # 1. Search with "Chatswood" (exact match)
        add_search("Filipino restaurant in Chatswood site:facebook.com", "Facebook", 1, self.tracker_path, suburbs_path=self.suburbs_path)

        # 2. Search with "parramatta" (case-insensitive match)
        add_search("Filipino cafe in parramatta site:instagram.com", "Instagram", 2, self.tracker_path, suburbs_path=self.suburbs_path)

        # 3. Search without any suburb name
        add_search("Filipino grocery in Sydney -site:facebook.com", "General Web", 3, self.tracker_path, suburbs_path=self.suburbs_path)

        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["searches"][0]["suburb"], "Chatswood")
        self.assertEqual(data["searches"][1]["suburb"], "Parramatta")
        self.assertIsNone(data["searches"][2]["suburb"])

        # Generate the report
        report_file = generate_report(
            tracker_path=self.tracker_path,
            template_path=self.template_path,
            logs_dir=self.logs_dir,
            suburbs_path=self.suburbs_path,
        )

        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check metadata row
        self.assertIn("**Search Locations / Suburbs** | Chatswood, Parramatta", content)

        # Check summary count row
        self.assertIn("**Total Suburbs Searched** | 2", content)

        # Check log details table content
        self.assertIn("| Search Query | Platform | Pages Read | Location / Suburb |", content)
        self.assertIn("| Filipino restaurant in Chatswood site:facebook.com | Facebook | 1 | Chatswood |", content)
        self.assertIn("| Filipino cafe in parramatta site:instagram.com | Instagram | 2 | Parramatta |", content)
        self.assertIn("| Filipino grocery in Sydney -site:facebook.com | General Web | 3 | None |", content)


if __name__ == "__main__":
    unittest.main()
