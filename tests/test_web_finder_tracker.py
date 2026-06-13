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
        self.logs_dir = os.path.join(self.temp_dir.name, "logs")

        # Mock REPORT_TEMPLATE.md
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

## Summary

| Metric | Count |
| :--- | :--- |
| **Web Searches Made** | {WEB_SEARCHES_MADE} |
| **Total Pages Read** | {TOTAL_PAGES_READ} |
| **Total Candidate Pages Evaluated** | {CANDIDATES_EVALUATED} |
| **Verified Listings Created** | {LISTINGS_CREATED} |
| **Candidates Rejected** | {CANDIDATES_REJECTED} |
| **Errors Encountered** | {ERRORS_ENCOUNTERED} |

## Verified Community Listings

### Created Listings

{CREATED_LISTINGS}

## Skipped / Rejected Candidates

{REJECTED_TABLE}

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

        add_search("query1", "Facebook", 1, self.tracker_path)
        add_search("query2", "Instagram", 2, self.tracker_path)

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

    def test_generate_report_produces_valid_markdown(self) -> None:
        """Report generation should correctly compile data, sort categories/platforms, and format markdown."""
        init_tracker("Sydney", "RESTAURANT", 1, "Filipino shop in {city}", "Filipino shop in Sydney", "trace-id-123", self.tracker_path)

        add_search("query1", "Facebook", 2, self.tracker_path)
        add_search("query2", "Instagram", 3, self.tracker_path)

        # Candidate 1: Created (Facebook)
        add_candidate(
            name="Z-Restaurant",
            url="https://facebook.com/zrest",
            platform="Facebook",
            status="CREATED",
            reason="Lumpia specialty",
            db_id="db-z",
            address="456 Rd",
            description="Special lumpia",
            tags="google-search",
            category="RESTAURANT",
            tracker_path=self.tracker_path,
        )

        # Candidate 2: Created (Instagram) - platform ordering check (Facebook should come before Instagram)
        add_candidate(
            name="A-Restaurant",
            url="https://instagram.com/arest",
            platform="Instagram",
            status="CREATED",
            reason="Adobo house",
            db_id="db-a",
            address="123 Rd",
            description="Special adobo",
            tags="google-search",
            category="RESTAURANT",
            tracker_path=self.tracker_path,
        )

        # Candidate 3: Created (Facebook) - alphabetical check (A-Rest should come before Z-Rest if same platform, but FB is first)
        add_candidate(
            name="B-Restaurant",
            url="https://facebook.com/brest",
            platform="Facebook",
            status="CREATED",
            reason="BBQ style",
            db_id="db-b",
            address="789 Rd",
            description="Pinoy BBQ",
            tags="google-search",
            category="RESTAURANT",
            tracker_path=self.tracker_path,
        )

        # Candidate 4: Duplicate
        add_candidate(
            name="Duplicate Shop",
            url="https://facebook.com/dupe",
            platform="Facebook",
            status="DUPLICATE",
            reason="Already in DB",
            db_id=None,
            address=None,
            description=None,
            tags=None,
            category=None,
            tracker_path=self.tracker_path,
        )

        # Candidate 5: Rejected
        add_candidate(
            name="Generic Sushi",
            url="https://instagram.com/sushi",
            platform="Instagram",
            status="REJECTED",
            reason="Not Filipino-affiliated",
            db_id=None,
            address=None,
            description=None,
            tags=None,
            category=None,
            tracker_path=self.tracker_path,
        )

        add_error("Slow network warning", self.tracker_path)

        # Generate report
        report_file = generate_report(
            tracker_path=self.tracker_path,
            template_path=self.template_path,
            logs_dir=self.logs_dir,
        )

        self.assertTrue(os.path.exists(report_file))

        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check metrics replacements
        self.assertIn("**Web Searches Made** | 2", content)
        self.assertIn("**Total Pages Read** | 5", content)
        self.assertIn("**Total Candidate Pages Evaluated** | 5", content)
        self.assertIn("**Verified Listings Created** | 3", content)
        self.assertIn("**Candidates Rejected** | 2", content)
        self.assertIn("**Errors Encountered** | 1", content)

        # Check Created Listings sorting and formatting
        # Grouped under #### RESTAURANT
        self.assertIn("#### RESTAURANT", content)
        # Sorted by platform (Facebook first, then Instagram), then alphabetically.
        # Order of created:
        # 1. B-Restaurant (Facebook)
        # 2. Z-Restaurant (Facebook)
        # 3. A-Restaurant (Instagram)
        idx_b = content.index("B-Restaurant")
        idx_z = content.index("Z-Restaurant")
        idx_a = content.index("A-Restaurant")

        self.assertTrue(idx_b < idx_z < idx_a)

        # Check Rejected Candidates table
        self.assertIn("Duplicate Shop", content)
        self.assertIn("Already in DB", content)
        self.assertIn("Generic Sushi", content)

        # Check errors list
        self.assertIn("Slow network warning", content)


if __name__ == "__main__":
    unittest.main()
