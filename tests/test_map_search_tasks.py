"""Unit tests for features.scanning.map_search_tasks module.

Tests maps-specific task generation including city-only default behavior,
include_suburbs expansion, places_fetched metric field, and cityOnly
category interaction with the include_suburbs flag.
"""

import json
import os
import tempfile
import unittest

from features.scanning.map_search_tasks import generate_tasks


class TestGenerateMapSearchTasks(unittest.TestCase):
    """Tests for the map search generate_tasks function."""

    def setUp(self) -> None:
        """Create temporary category and suburb files for testing."""
        self.tmpdir = tempfile.mkdtemp()
        self.categories_path = os.path.join(self.tmpdir, "categories.json")
        self.suburbs_path = os.path.join(self.tmpdir, "suburbs.json")

        self.categories_data = {
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": [
                    "Filipino restaurant in {city}",
                    "Filipino food truck in {city}",
                ],
            },
            "CAFE": {
                "displayName": "Cafés",
                "searchTemplates": [
                    "Filipino cafe in {city}",
                ],
            },
        }
        self.suburbs_data = {
            "sydney": ["Parramatta", "Blacktown"],
            "melbourne": [],
        }

        with open(self.categories_path, "w") as f:
            json.dump(self.categories_data, f)
        with open(self.suburbs_path, "w") as f:
            json.dump(self.suburbs_data, f)

    def test_city_only_default(self) -> None:
        """Sydney with 2 templates RESTAURANT + 1 template CAFE = 3 city-level tasks.

        By default include_suburbs=False, so only city-level tasks are generated.
        """
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 3)
        for task in tasks:
            self.assertEqual(task["location_type"], "city")

    def test_include_suburbs(self) -> None:
        """With include_suburbs=True: (2 templates * 3 locations) + (1 * 3) = 9 tasks."""
        tasks = generate_tasks(
            "Sydney", self.categories_path, self.suburbs_path, include_suburbs=True,
        )
        self.assertEqual(len(tasks), 9)

    def test_places_fetched_metric(self) -> None:
        """Tasks should have places_fetched field initialized to 0, NOT pages_searched."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        for task in tasks:
            self.assertIn("places_fetched", task)
            self.assertEqual(task["places_fetched"], 0)
            self.assertNotIn("pages_searched", task)

    def test_task_id_format(self) -> None:
        """Task IDs should follow the pattern: city__CATEGORY__index__location."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(tasks[0]["id"], "sydney__RESTAURANT__0__sydney")
        self.assertEqual(tasks[1]["id"], "sydney__RESTAURANT__1__sydney")

    def test_formatted_query_city(self) -> None:
        """City-level tasks should format query with just the city name."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(tasks[0]["formatted_query"], "Filipino restaurant in Sydney")

    def test_formatted_query_suburb(self) -> None:
        """Suburb-level query should use '{base} in {suburb}, {city}' format."""
        tasks = generate_tasks(
            "Sydney", self.categories_path, self.suburbs_path, include_suburbs=True,
        )
        # With include_suburbs, task index 1 is the first suburb task
        suburb_tasks = [t for t in tasks if t["location_type"] == "suburb"]
        self.assertTrue(len(suburb_tasks) > 0)
        first_suburb = suburb_tasks[0]
        self.assertEqual(
            first_suburb["formatted_query"],
            "Filipino restaurant in Parramatta, Sydney",
        )

    def test_city_only_category_ignores_include_suburbs(self) -> None:
        """GOVERNMENT with cityOnly=true still produces only city-level tasks even with include_suburbs=True."""
        categories_data = {
            "GOVERNMENT": {
                "cityOnly": True,
                "searchTemplates": ["Philippine consulate in {city}"],
            },
            "RESTAURANT": {
                "searchTemplates": ["Filipino restaurant in {city}"],
            },
        }
        with open(self.categories_path, "w") as f:
            json.dump(categories_data, f)

        tasks = generate_tasks(
            "Sydney", self.categories_path, self.suburbs_path, include_suburbs=True,
        )
        gov_tasks = [t for t in tasks if t["category"] == "GOVERNMENT"]
        rest_tasks = [t for t in tasks if t["category"] == "RESTAURANT"]
        # GOVERNMENT: 1 template × 1 city-only = 1
        self.assertEqual(len(gov_tasks), 1)
        self.assertEqual(gov_tasks[0]["location_type"], "city")
        # RESTAURANT: 1 template × 3 locations = 3
        self.assertEqual(len(rest_tasks), 3)

    def test_all_tasks_start_as_pending(self) -> None:
        """All tasks should start with PENDING status."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        for task in tasks:
            self.assertEqual(task["status"], "PENDING")

    def test_invalid_city_raises_error(self) -> None:
        """A city not in the suburbs file should raise ValueError."""
        with self.assertRaises(ValueError):
            generate_tasks("BogusCity", self.categories_path, self.suburbs_path)

    def test_metric_fields_initialized_to_zero(self) -> None:
        """Numeric metric fields should initialize to 0, errors to empty list."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        for task in tasks:
            self.assertEqual(task["listings_created"], 0)
            self.assertEqual(task["places_fetched"], 0)
            self.assertEqual(task["candidates_evaluated"], 0)
            self.assertEqual(task["candidates_rejected"], 0)
            self.assertEqual(task["candidates_duplicate"], 0)
            self.assertEqual(task["errors"], [])
            self.assertIsNone(task["started_at"])
            self.assertIsNone(task["completed_at"])

    def test_task_has_all_required_fields(self) -> None:
        """Each task should contain all required tracking fields with places_fetched."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        required_fields = {
            "id", "city", "location", "location_type", "category",
            "template_index", "template", "formatted_query", "status",
            "started_at", "completed_at", "listings_created",
            "places_fetched", "candidates_evaluated",
            "candidates_rejected", "candidates_duplicate", "errors",
        }
        for task in tasks:
            self.assertEqual(set(task.keys()), required_fields)


if __name__ == "__main__":
    unittest.main()
