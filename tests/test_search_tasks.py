"""Unit tests for features.scanning.search_tasks module.

Tests the task-based state machine for the web finder agent,
covering generation, state transitions, and progress aggregation.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime

from features.scanning.search_tasks import (
    generate_tasks,
    load_tasks,
    save_tasks,
    get_next_task,
    start_task,
    complete_task,
    get_progress_summary,
)


class TestGenerateTasks(unittest.TestCase):
    """Tests for the generate_tasks function."""

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


class TestLoadSaveTasks(unittest.TestCase):
    """Tests for load_tasks and save_tasks."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.tasks_path = os.path.join(self.tmpdir, "tasks.json")

    def test_save_and_load_roundtrip(self) -> None:
        """Tasks saved to disk should load back identically."""
        tasks = [{"id": "test__RESTAURANT__0__city", "status": "PENDING"}]
        save_tasks(self.tasks_path, tasks)
        loaded = load_tasks(self.tasks_path)
        self.assertEqual(loaded, tasks)

    def test_load_nonexistent_file_returns_empty(self) -> None:
        """Loading a missing file should return an empty list."""
        loaded = load_tasks(os.path.join(self.tmpdir, "nonexistent.json"))
        self.assertEqual(loaded, [])

    def test_load_corrupt_file_returns_empty(self) -> None:
        """Loading a corrupt JSON file should return an empty list."""
        with open(self.tasks_path, "w") as f:
            f.write("not valid json{{{")
        loaded = load_tasks(self.tasks_path)
        self.assertEqual(loaded, [])


class TestGetNextTask(unittest.TestCase):
    """Tests for get_next_task."""

    def test_returns_first_pending_task(self) -> None:
        """Should return the first task with PENDING status."""
        tasks = [
            {"id": "a", "status": "COMPLETED"},
            {"id": "b", "status": "PENDING"},
            {"id": "c", "status": "PENDING"},
        ]
        result = get_next_task(tasks)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "b")

    def test_returns_none_when_all_completed(self) -> None:
        """Should return None when no PENDING tasks remain."""
        tasks = [
            {"id": "a", "status": "COMPLETED"},
            {"id": "b", "status": "COMPLETED"},
        ]
        result = get_next_task(tasks)
        self.assertIsNone(result)

    def test_returns_none_for_empty_list(self) -> None:
        """Should return None for an empty task list."""
        result = get_next_task([])
        self.assertIsNone(result)

    def test_skips_in_progress_tasks(self) -> None:
        """Should skip IN_PROGRESS tasks and return the next PENDING."""
        tasks = [
            {"id": "a", "status": "IN_PROGRESS"},
            {"id": "b", "status": "PENDING"},
        ]
        result = get_next_task(tasks)
        self.assertEqual(result["id"], "b")


class TestStartTask(unittest.TestCase):
    """Tests for start_task."""

    def test_transitions_to_in_progress(self) -> None:
        """Should set the task status to IN_PROGRESS."""
        tasks = [{"id": "a", "status": "PENDING", "started_at": None}]
        updated = start_task(tasks, "a")
        self.assertEqual(updated[0]["status"], "IN_PROGRESS")

    def test_sets_started_at_timestamp(self) -> None:
        """Should record an ISO 8601 started_at timestamp."""
        tasks = [{"id": "a", "status": "PENDING", "started_at": None}]
        updated = start_task(tasks, "a")
        self.assertIsNotNone(updated[0]["started_at"])
        # Verify it parses as a valid datetime
        datetime.fromisoformat(updated[0]["started_at"])

    def test_raises_for_unknown_task_id(self) -> None:
        """Should raise ValueError for a task ID that doesn't exist."""
        tasks = [{"id": "a", "status": "PENDING", "started_at": None}]
        with self.assertRaises(ValueError):
            start_task(tasks, "nonexistent")

    def test_raises_for_non_pending_task(self) -> None:
        """Should raise ValueError if the task is not in PENDING status."""
        tasks = [{"id": "a", "status": "COMPLETED", "started_at": None}]
        with self.assertRaises(ValueError):
            start_task(tasks, "a")


class TestCompleteTask(unittest.TestCase):
    """Tests for complete_task."""

    def test_transitions_to_completed(self) -> None:
        """Should set the task status to COMPLETED."""
        tasks = [{"id": "a", "status": "IN_PROGRESS", "completed_at": None,
                  "listings_created": 0, "pages_searched": 0,
                  "candidates_evaluated": 0, "candidates_rejected": 0,
                  "candidates_duplicate": 0, "errors": []}]
        metrics = {"listings_created": 3, "pages_searched": 5}
        updated = complete_task(tasks, "a", metrics)
        self.assertEqual(updated[0]["status"], "COMPLETED")

    def test_merges_metrics(self) -> None:
        """Should merge the provided metrics into the task."""
        tasks = [{"id": "a", "status": "IN_PROGRESS", "completed_at": None,
                  "listings_created": 0, "pages_searched": 0,
                  "candidates_evaluated": 0, "candidates_rejected": 0,
                  "candidates_duplicate": 0, "errors": []}]
        metrics = {
            "listings_created": 3,
            "pages_searched": 5,
            "candidates_evaluated": 10,
            "candidates_rejected": 2,
            "candidates_duplicate": 4,
        }
        updated = complete_task(tasks, "a", metrics)
        self.assertEqual(updated[0]["listings_created"], 3)
        self.assertEqual(updated[0]["pages_searched"], 5)
        self.assertEqual(updated[0]["candidates_evaluated"], 10)

    def test_sets_completed_at_timestamp(self) -> None:
        """Should record an ISO 8601 completed_at timestamp."""
        tasks = [{"id": "a", "status": "IN_PROGRESS", "completed_at": None,
                  "listings_created": 0, "pages_searched": 0,
                  "candidates_evaluated": 0, "candidates_rejected": 0,
                  "candidates_duplicate": 0, "errors": []}]
        updated = complete_task(tasks, "a", {})
        self.assertIsNotNone(updated[0]["completed_at"])
        datetime.fromisoformat(updated[0]["completed_at"])

    def test_raises_for_non_in_progress_task(self) -> None:
        """Should raise ValueError if the task is not IN_PROGRESS."""
        tasks = [{"id": "a", "status": "PENDING", "completed_at": None,
                  "listings_created": 0, "pages_searched": 0,
                  "candidates_evaluated": 0, "candidates_rejected": 0,
                  "candidates_duplicate": 0, "errors": []}]
        with self.assertRaises(ValueError):
            complete_task(tasks, "a", {})


class TestGetProgressSummary(unittest.TestCase):
    """Tests for get_progress_summary."""

    def test_aggregates_correctly(self) -> None:
        """Should compute correct totals across all tasks."""
        tasks = [
            {"status": "COMPLETED", "listings_created": 3, "pages_searched": 5,
             "candidates_evaluated": 8, "candidates_rejected": 1, "candidates_duplicate": 2, "errors": []},
            {"status": "COMPLETED", "listings_created": 2, "pages_searched": 3,
             "candidates_evaluated": 4, "candidates_rejected": 0, "candidates_duplicate": 1, "errors": ["err"]},
            {"status": "PENDING", "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0, "candidates_duplicate": 0, "errors": []},
            {"status": "IN_PROGRESS", "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0, "candidates_duplicate": 0, "errors": []},
        ]
        summary = get_progress_summary(tasks)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["in_progress"], 1)
        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["total_listings_created"], 5)
        self.assertEqual(summary["total_pages_searched"], 8)
        self.assertEqual(summary["total_candidates_evaluated"], 12)
        self.assertEqual(summary["total_errors"], 1)

    def test_empty_tasks_returns_zeros(self) -> None:
        """Should return all zeros for an empty task list."""
        summary = get_progress_summary([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["total_listings_created"], 0)


if __name__ == "__main__":
    unittest.main()
