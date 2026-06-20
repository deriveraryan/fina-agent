"""Unit tests for the events_tasks module.

Tests the task generation logic for the events listing agent,
including social URL filtering and task structure validation.
"""

import unittest
from features.scanning.events_tasks import (
    generate_events_tasks,
    _has_social_urls,
    _build_events_task,
    EVENTS_ALLOWED_METRICS,
    EVENTS_METRIC_FIELDS,
    EVENTS_MUTABLE_FIELDS,
)


class TestHasSocialUrls(unittest.TestCase):
    """Tests for the _has_social_urls filter function."""

    def test_listing_with_facebook_url(self) -> None:
        listing = {"facebookUrl": "https://facebook.com/test"}
        self.assertTrue(_has_social_urls(listing))

    def test_listing_with_instagram_url(self) -> None:
        listing = {"instagramUrl": "https://instagram.com/test"}
        self.assertTrue(_has_social_urls(listing))

    def test_listing_with_tiktok_url(self) -> None:
        listing = {"tiktokUrl": "https://tiktok.com/@test"}
        self.assertTrue(_has_social_urls(listing))

    def test_listing_with_all_social_urls(self) -> None:
        listing = {
            "facebookUrl": "https://facebook.com/test",
            "instagramUrl": "https://instagram.com/test",
            "tiktokUrl": "https://tiktok.com/@test",
        }
        self.assertTrue(_has_social_urls(listing))

    def test_listing_with_no_social_urls(self) -> None:
        listing = {"id": "123", "name": "Test"}
        self.assertFalse(_has_social_urls(listing))

    def test_listing_with_null_social_urls(self) -> None:
        listing = {"facebookUrl": None, "instagramUrl": None, "tiktokUrl": None}
        self.assertFalse(_has_social_urls(listing))

    def test_listing_with_empty_string_social_urls(self) -> None:
        listing = {"facebookUrl": "", "instagramUrl": "", "tiktokUrl": ""}
        self.assertFalse(_has_social_urls(listing))


class TestBuildEventsTask(unittest.TestCase):
    """Tests for the _build_events_task function."""

    def test_builds_task_with_all_fields(self) -> None:
        listing = {
            "id": "uuid-123",
            "name": "Test Business",
            "city": "SYDNEY",
            "categories": ["RESTAURANT"],
            "facebookUrl": "https://facebook.com/test",
            "instagramUrl": "https://instagram.com/test",
            "tiktokUrl": None,
        }
        task = _build_events_task(listing)

        self.assertEqual(task["id"], "uuid-123")
        self.assertEqual(task["listing_id"], "uuid-123")
        self.assertEqual(task["name"], "Test Business")
        self.assertEqual(task["city"], "SYDNEY")
        self.assertEqual(task["categories"], ["RESTAURANT"])
        self.assertEqual(task["facebook_url"], "https://facebook.com/test")
        self.assertEqual(task["instagram_url"], "https://instagram.com/test")
        self.assertIsNone(task["tiktok_url"])
        self.assertEqual(task["status"], "PENDING")
        self.assertIsNone(task["started_at"])
        self.assertIsNone(task["completed_at"])
        self.assertEqual(task["events_discovered"], 0)
        self.assertEqual(task["events_pushed"], 0)
        self.assertEqual(task["social_urls_scanned"], 0)
        self.assertEqual(task["follower_counts_updated"], 0)
        self.assertEqual(task["bookmarks_updated"], 0)
        self.assertEqual(task["errors"], [])

    def test_raises_on_missing_id(self) -> None:
        listing = {"name": "No ID Business"}
        with self.assertRaises(ValueError) as ctx:
            _build_events_task(listing)
        self.assertIn("missing required 'id'", str(ctx.exception))

    def test_defaults_for_missing_optional_fields(self) -> None:
        listing = {"id": "uuid-456"}
        task = _build_events_task(listing)

        self.assertEqual(task["name"], "")
        self.assertEqual(task["city"], "")
        self.assertEqual(task["categories"], [])
        self.assertIsNone(task["facebook_url"])
        self.assertIsNone(task["instagram_url"])
        self.assertIsNone(task["tiktok_url"])


class TestGenerateEventsTasks(unittest.TestCase):
    """Tests for the generate_events_tasks function."""

    def test_filters_listings_without_social_urls(self) -> None:
        listings = [
            {"id": "1", "name": "Has FB", "facebookUrl": "https://facebook.com/a"},
            {"id": "2", "name": "No Socials"},
            {"id": "3", "name": "Has IG", "instagramUrl": "https://instagram.com/b"},
            {"id": "4", "name": "Null Socials", "facebookUrl": None, "instagramUrl": None},
        ]
        tasks = generate_events_tasks(listings)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "1")
        self.assertEqual(tasks[1]["id"], "3")

    def test_empty_listings_returns_empty_tasks(self) -> None:
        tasks = generate_events_tasks([])
        self.assertEqual(tasks, [])

    def test_all_listings_without_socials_returns_empty(self) -> None:
        listings = [
            {"id": "1", "name": "No Socials A"},
            {"id": "2", "name": "No Socials B"},
        ]
        tasks = generate_events_tasks(listings)
        self.assertEqual(tasks, [])


class TestMetricConstants(unittest.TestCase):
    """Tests for metric constant consistency."""

    def test_allowed_metrics_matches_metric_fields(self) -> None:
        self.assertEqual(EVENTS_ALLOWED_METRICS, set(EVENTS_METRIC_FIELDS))

    def test_mutable_fields_contains_all_metrics(self) -> None:
        for metric in EVENTS_METRIC_FIELDS:
            self.assertIn(metric, EVENTS_MUTABLE_FIELDS)

    def test_mutable_fields_contains_lifecycle_fields(self) -> None:
        for field in ("status", "started_at", "completed_at", "errors"):
            self.assertIn(field, EVENTS_MUTABLE_FIELDS)


if __name__ == "__main__":
    unittest.main()
