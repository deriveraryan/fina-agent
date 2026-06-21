"""Unit tests for enrichment_tasks module.

Tests the pure-function task generation logic that converts listing dicts
(from ListAdminListings) into enrichment task dicts for the task lifecycle
state machine.
"""

import unittest
from features.scanning.enrichment_tasks import (
    generate_enrichment_tasks,
    ENRICHMENT_ALLOWED_METRICS,
    ENRICHMENT_METRIC_FIELDS,
    ENRICHMENT_MUTABLE_FIELDS,
)
from features.scanning.task_lifecycle import merge_existing_state


class TestGenerateEnrichmentTasks(unittest.TestCase):
    """Tests for generate_enrichment_tasks()."""

    def _make_listing(self, **overrides) -> dict:
        """Helper to create a listing dict with sensible defaults."""
        listing = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "name": "Jollibee Parramatta",
            "city": "Sydney",
            "categories": ["RESTAURANT"],
            "description": "A popular Filipino fast food chain.",
            "address": "123 Church St, Parramatta NSW 2150",
            "sourceUrl": "https://www.google.com/maps/place/?q=place_id:ChIJ123",
            "facebookUrl": "https://www.facebook.com/JollibeeAU",
            "instagramUrl": None,
            "tiktokUrl": None,
            "facebookFollowers": 5000,
            "instagramFollowers": None,
            "tiktokFollowers": None,
            "verificationStatus": "VERIFIED",
            "status": "OPERATIONAL",
        }
        listing.update(overrides)
        return listing

    def test_generate_enrichment_tasks_from_listings(self):
        """Given a list of listing dicts, produces correctly structured tasks."""
        listings = [
            self._make_listing(
                id="uuid-1",
                name="Jollibee Parramatta",
                city="Sydney",
                categories=["RESTAURANT"],
            ),
            self._make_listing(
                id="uuid-2",
                name="Max's Restaurant",
                city="Sydney",
                categories=["RESTAURANT", "CAFE"],
            ),
        ]

        tasks = generate_enrichment_tasks(listings)

        self.assertEqual(len(tasks), 2)

        task_1 = tasks[0]
        self.assertEqual(task_1["id"], "uuid-1")
        self.assertEqual(task_1["listing_id"], "uuid-1")
        self.assertEqual(task_1["name"], "Jollibee Parramatta")
        self.assertEqual(task_1["city"], "Sydney")
        self.assertEqual(task_1["categories"], ["RESTAURANT"])
        self.assertEqual(task_1["status"], "PENDING")
        self.assertIsNone(task_1["started_at"])
        self.assertIsNone(task_1["completed_at"])
        self.assertEqual(task_1["errors"], [])

        task_2 = tasks[1]
        self.assertEqual(task_2["id"], "uuid-2")
        self.assertEqual(task_2["name"], "Max's Restaurant")
        self.assertEqual(task_2["categories"], ["RESTAURANT", "CAFE"])

    def test_generate_enrichment_tasks_empty_list(self):
        """Empty input produces empty output."""
        tasks = generate_enrichment_tasks([])
        self.assertEqual(tasks, [])

    def test_generate_enrichment_tasks_preserves_existing_social_urls(self):
        """Existing social URLs are captured in the task for skip-check logic."""
        listing = self._make_listing(
            id="uuid-social",
            facebookUrl="https://facebook.com/testbiz",
            instagramUrl="https://instagram.com/testbiz",
            tiktokUrl=None,
        )

        tasks = generate_enrichment_tasks([listing])

        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["facebook_url"], "https://facebook.com/testbiz")
        self.assertEqual(task["instagram_url"], "https://instagram.com/testbiz")
        self.assertIsNone(task["tiktok_url"])

    def test_enrichment_task_id_uses_listing_uuid(self):
        """Task ID is the listing's database UUID for natural uniqueness."""
        listing = self._make_listing(id="12345678-abcd-ef01-2345-678901234567")

        tasks = generate_enrichment_tasks([listing])

        self.assertEqual(tasks[0]["id"], "12345678-abcd-ef01-2345-678901234567")

    def test_all_metric_fields_initialised_to_zero(self):
        """All enrichment-specific metric fields start at 0."""
        listing = self._make_listing(id="uuid-metrics")

        tasks = generate_enrichment_tasks([listing])
        task = tasks[0]

        for field in ENRICHMENT_METRIC_FIELDS:
            self.assertEqual(
                task[field], 0,
                f"Metric field '{field}' should be initialised to 0",
            )

    def test_description_and_source_url_captured(self):
        """Current description and sourceUrl are captured for synthesis input."""
        listing = self._make_listing(
            id="uuid-desc",
            description="Best lechon in Sydney.",
            sourceUrl="https://maps.google.com/some-place",
        )

        tasks = generate_enrichment_tasks([listing])
        task = tasks[0]

        self.assertEqual(task["description"], "Best lechon in Sydney.")
        self.assertEqual(task["source_url"], "https://maps.google.com/some-place")

    def test_none_description_handled(self):
        """Listings with no description produce task with None description."""
        listing = self._make_listing(id="uuid-nodesc", description=None)

        tasks = generate_enrichment_tasks([listing])

        self.assertIsNone(tasks[0]["description"])

    def test_missing_listing_id_raises_value_error(self):
        """A listing missing 'id' raises ValueError with the listing name."""
        listing = {"name": "No ID Business", "city": "Sydney"}

        with self.assertRaises(ValueError) as ctx:
            generate_enrichment_tasks([listing])

        self.assertIn("No ID Business", str(ctx.exception))

    def test_listing_status_captured_for_closure_detection(self):
        """Listing's current status is captured as listing_status for closure detection."""
        listing_operational = self._make_listing(id="uuid-op", status="OPERATIONAL")
        listing_closed = self._make_listing(id="uuid-cl", status="CLOSED_PERMANENTLY")
        listing_no_status = self._make_listing(id="uuid-ns")
        del listing_no_status["status"]

        tasks = generate_enrichment_tasks([listing_operational, listing_closed, listing_no_status])

        self.assertEqual(tasks[0]["listing_status"], "OPERATIONAL")
        self.assertEqual(tasks[1]["listing_status"], "CLOSED_PERMANENTLY")
        self.assertEqual(tasks[2]["listing_status"], "OPERATIONAL")  # default

    def test_verification_status_captured_for_affiliation_assessment(self):
        """Listing's verificationStatus is captured for affiliation assessment."""
        listing_verified = self._make_listing(id="uuid-v", verificationStatus="VERIFIED")
        listing_unverified = self._make_listing(id="uuid-u", verificationStatus="UNVERIFIED")
        listing_no_status = self._make_listing(id="uuid-ns2")
        del listing_no_status["verificationStatus"]

        tasks = generate_enrichment_tasks([listing_verified, listing_unverified, listing_no_status])

        self.assertEqual(tasks[0]["verification_status"], "VERIFIED")
        self.assertEqual(tasks[1]["verification_status"], "UNVERIFIED")
        self.assertEqual(tasks[2]["verification_status"], "UNVERIFIED")  # default


class TestEnrichmentMetricsConstants(unittest.TestCase):
    """Tests for enrichment-specific metric constants."""

    def test_allowed_metrics_contains_expected_fields(self):
        """ENRICHMENT_ALLOWED_METRICS has the correct enrichment metric names."""
        expected = {
            "listings_enriched",
            "reviews_extracted",
            "reviews_pushed",
            "socials_enriched",
            "descriptions_rewritten",
            "maps_visits",
            "statuses_updated",
            "listings_flagged",
        }
        self.assertEqual(ENRICHMENT_ALLOWED_METRICS, expected)

    def test_metric_fields_is_sequence_of_allowed_metrics(self):
        """ENRICHMENT_METRIC_FIELDS contains exactly the allowed metrics."""
        self.assertEqual(set(ENRICHMENT_METRIC_FIELDS), ENRICHMENT_ALLOWED_METRICS)

    def test_mutable_fields_contains_status_and_timestamps(self):
        """ENRICHMENT_MUTABLE_FIELDS includes lifecycle state + metrics + errors."""
        for required in ("status", "started_at", "completed_at", "errors"):
            self.assertIn(
                required,
                ENRICHMENT_MUTABLE_FIELDS,
                f"'{required}' must be in ENRICHMENT_MUTABLE_FIELDS",
            )

    def test_mutable_fields_contains_all_metric_fields(self):
        """All metric fields are also mutable (for state merge on --force)."""
        for metric in ENRICHMENT_METRIC_FIELDS:
            self.assertIn(
                metric,
                ENRICHMENT_MUTABLE_FIELDS,
                f"Metric '{metric}' must be in ENRICHMENT_MUTABLE_FIELDS",
            )


class TestForceRegenerationMergesState(unittest.TestCase):
    """Tests for state preservation when --force regenerates tasks."""

    def test_merge_preserves_completed_status(self):
        """When regenerating tasks with --force, completed tasks keep their state."""
        existing_tasks = [
            {
                "id": "uuid-1",
                "status": "COMPLETED",
                "started_at": "2026-06-19T10:00:00+00:00",
                "completed_at": "2026-06-19T10:30:00+00:00",
                "listings_enriched": 1,
                "reviews_extracted": 5,
                "reviews_pushed": 5,
                "socials_enriched": 1,
                "descriptions_rewritten": 1,
                "maps_visits": 1,
                "statuses_updated": 0,
                "listings_flagged": 0,
                "errors": [],
            },
        ]

        new_tasks = [
            {
                "id": "uuid-1",
                "status": "PENDING",
                "started_at": None,
                "completed_at": None,
                "listings_enriched": 0,
                "reviews_extracted": 0,
                "reviews_pushed": 0,
                "socials_enriched": 0,
                "descriptions_rewritten": 0,
                "maps_visits": 0,
                "statuses_updated": 0,
                "listings_flagged": 0,
                "errors": [],
            },
            {
                "id": "uuid-2",
                "status": "PENDING",
                "started_at": None,
                "completed_at": None,
                "listings_enriched": 0,
                "reviews_extracted": 0,
                "reviews_pushed": 0,
                "socials_enriched": 0,
                "descriptions_rewritten": 0,
                "maps_visits": 0,
                "statuses_updated": 0,
                "listings_flagged": 0,
                "errors": [],
            },
        ]

        result = merge_existing_state(
            new_tasks, existing_tasks, ENRICHMENT_MUTABLE_FIELDS
        )

        self.assertEqual(result["merged_count"], 1)
        self.assertEqual(result["new_count"], 1)
        self.assertEqual(result["removed_count"], 0)

        # uuid-1 should have preserved its COMPLETED state
        self.assertEqual(new_tasks[0]["status"], "COMPLETED")
        self.assertEqual(new_tasks[0]["listings_enriched"], 1)
        self.assertEqual(new_tasks[0]["reviews_extracted"], 5)

        # uuid-2 should remain PENDING
        self.assertEqual(new_tasks[1]["status"], "PENDING")
        self.assertEqual(new_tasks[1]["listings_enriched"], 0)


if __name__ == "__main__":
    unittest.main()
