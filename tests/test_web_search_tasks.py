"""Unit tests for features.scanning.web_search_tasks module.

Tests web-search-specific task generation including category ordering,
suburb expansion, cityOnly flag handling, and query formatting.
"""

import json
import os
import tempfile
import unittest

from features.scanning.web_search_tasks import generate_tasks


class TestGenerateTasks(unittest.TestCase):
    """Tests for the web search generate_tasks function."""

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

    def test_generates_correct_task_count(self) -> None:
        """Sydney has 2 suburbs + city-level = 3 locations.
        RESTAURANT has 2 templates, CAFE has 1.
        Expected: (2 templates * 3 locations) + (1 template * 3 locations) = 9 tasks.
        """
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 9)

    def test_city_level_tasks_come_first_per_template(self) -> None:
        """For each category+template, the city-level task should precede suburb tasks."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        # First task should be RESTAURANT template 0 at city level
        self.assertEqual(tasks[0]["category"], "RESTAURANT")
        self.assertEqual(tasks[0]["template_index"], 0)
        self.assertEqual(tasks[0]["location_type"], "city")
        self.assertEqual(tasks[0]["location"], "Sydney")

    def test_suburb_tasks_follow_city_level(self) -> None:
        """Suburb tasks follow the city-level task within the same template."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        # Tasks 1 and 2 should be RESTAURANT template 0 suburbs
        self.assertEqual(tasks[1]["location_type"], "suburb")
        self.assertEqual(tasks[1]["location"], "Parramatta")
        self.assertEqual(tasks[2]["location_type"], "suburb")
        self.assertEqual(tasks[2]["location"], "Blacktown")

    def test_category_ordering_follows_categories_json(self) -> None:
        """RESTAURANT tasks should all appear before CAFE tasks."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        restaurant_indices = [i for i, t in enumerate(tasks) if t["category"] == "RESTAURANT"]
        cafe_indices = [i for i, t in enumerate(tasks) if t["category"] == "CAFE"]
        self.assertTrue(max(restaurant_indices) < min(cafe_indices))

    def test_all_tasks_start_as_pending(self) -> None:
        """Every generated task should have status PENDING."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        for task in tasks:
            self.assertEqual(task["status"], "PENDING")

    def test_task_id_format(self) -> None:
        """Task IDs should follow the pattern: city__CATEGORY__index__location."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(tasks[0]["id"], "sydney__RESTAURANT__0__sydney")
        self.assertEqual(tasks[1]["id"], "sydney__RESTAURANT__0__parramatta")

    def test_formatted_query_for_city(self) -> None:
        """City-level tasks should format query with just the city name."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(tasks[0]["formatted_query"], "Filipino restaurant in Sydney")

    def test_formatted_query_for_suburb(self) -> None:
        """Suburb tasks should format query as '{template} in {suburb}, {city}'."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(
            tasks[1]["formatted_query"],
            "Filipino restaurant in Parramatta, Sydney",
        )

    def test_city_with_no_suburbs(self) -> None:
        """A city with empty suburbs list should produce only city-level tasks."""
        tasks = generate_tasks("Melbourne", self.categories_path, self.suburbs_path)
        # 2 templates for RESTAURANT + 1 for CAFE = 3 city-level tasks
        self.assertEqual(len(tasks), 3)
        for task in tasks:
            self.assertEqual(task["location_type"], "city")

    def test_invalid_city_raises_error(self) -> None:
        """A city not in the suburbs file should raise ValueError."""
        with self.assertRaises(ValueError):
            generate_tasks("BogusCity", self.categories_path, self.suburbs_path)

    def test_task_has_all_required_fields(self) -> None:
        """Each task should contain all required tracking fields."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        required_fields = {
            "id", "city", "location", "location_type", "category",
            "template_index", "template", "formatted_query", "status",
            "started_at", "completed_at", "listings_created",
            "pages_searched", "candidates_evaluated",
            "candidates_rejected", "candidates_duplicate", "errors",
        }
        for task in tasks:
            self.assertEqual(set(task.keys()), required_fields)

    def test_metric_fields_initialized_to_zero(self) -> None:
        """Numeric metric fields should initialize to 0, errors to empty list."""
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        for task in tasks:
            self.assertEqual(task["listings_created"], 0)
            self.assertEqual(task["pages_searched"], 0)
            self.assertEqual(task["candidates_evaluated"], 0)
            self.assertEqual(task["candidates_rejected"], 0)
            self.assertEqual(task["candidates_duplicate"], 0)
            self.assertEqual(task["errors"], [])
            self.assertIsNone(task["started_at"])
            self.assertIsNone(task["completed_at"])


class TestCityOnlyCategory(unittest.TestCase):
    """Tests for the cityOnly flag in web search generate_tasks."""

    def setUp(self) -> None:
        """Create temp files with a cityOnly category and a normal one."""
        self.tmpdir = tempfile.mkdtemp()
        self.categories_path = os.path.join(self.tmpdir, "categories.json")
        self.suburbs_path = os.path.join(self.tmpdir, "suburbs.json")

        self.suburbs_data = {"sydney": ["Parramatta", "Blacktown"]}
        with open(self.suburbs_path, "w") as f:
            json.dump(self.suburbs_data, f)

    def _write_categories(self, data: dict) -> None:
        """Write category data to the temp categories file."""
        with open(self.categories_path, "w") as f:
            json.dump(data, f)

    def test_city_only_category_skips_suburbs(self) -> None:
        """A category with cityOnly: true should produce only city-level tasks."""
        self._write_categories({
            "GOVERNMENT": {
                "cityOnly": True,
                "searchTemplates": ["Philippine consulate in {city}"],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["location_type"], "city")

    def test_city_only_does_not_affect_other_categories(self) -> None:
        """A normal category alongside a cityOnly category should still produce suburb tasks."""
        self._write_categories({
            "GOVERNMENT": {
                "cityOnly": True,
                "searchTemplates": ["Philippine consulate in {city}"],
            },
            "RESTAURANT": {
                "searchTemplates": ["Filipino restaurant in {city}"],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        gov_tasks = [t for t in tasks if t["category"] == "GOVERNMENT"]
        rest_tasks = [t for t in tasks if t["category"] == "RESTAURANT"]
        self.assertEqual(len(gov_tasks), 1)  # city-only
        self.assertEqual(len(rest_tasks), 3)  # city + 2 suburbs

    def test_city_only_false_explicit(self) -> None:
        """cityOnly: false should behave identically to absent (produces suburb tasks)."""
        self._write_categories({
            "RESTAURANT": {
                "cityOnly": False,
                "searchTemplates": ["Filipino restaurant in {city}"],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 3)  # city + 2 suburbs

    def test_mixed_categories_with_city_only(self) -> None:
        """Correct total with a mix of cityOnly and regular categories."""
        self._write_categories({
            "GOVERNMENT": {
                "cityOnly": True,
                "searchTemplates": ["Template A in {city}", "Template B in {city}"],
            },
            "CAFE": {
                "searchTemplates": ["Filipino cafe in {city}"],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        # GOVERNMENT: 2 templates × 1 city-only = 2
        # CAFE: 1 template × 3 locations = 3
        self.assertEqual(len(tasks), 5)


if __name__ == "__main__":
    unittest.main()
