"""Unit tests for features.scanning.search_tasks module.

Tests the task-based state machine for the web finder agent,
covering generation, state transitions, and progress aggregation.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from features.scanning.search_tasks import (
    generate_tasks,
    load_tasks,
    save_tasks,
    get_next_task,
    start_task,
    complete_task,
    get_progress_summary,
    reclaim_stale_tasks,
    merge_existing_state,
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


def _make_in_progress_task(task_id: str, minutes_ago: int) -> dict:
    """Helper to create an IN_PROGRESS task started N minutes ago."""
    started = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "id": task_id,
        "status": "IN_PROGRESS",
        "started_at": started.isoformat(),
        "completed_at": None,
        "listings_created": 0,
        "pages_searched": 0,
        "candidates_evaluated": 0,
        "candidates_rejected": 0,
        "candidates_duplicate": 0,
        "errors": [],
    }


class TestReclaimStaleTasks(unittest.TestCase):
    """Tests for the reclaim_stale_tasks function."""

    def test_reclaims_task_exceeding_timeout(self) -> None:
        """A task started >60m ago should be reset to PENDING."""
        tasks = [_make_in_progress_task("a", minutes_ago=90)]
        reclaimed_ids = reclaim_stale_tasks(tasks, stale_timeout_minutes=60)
        self.assertEqual(reclaimed_ids, ["a"])
        self.assertEqual(tasks[0]["status"], "PENDING")

    def test_does_not_reclaim_fresh_in_progress(self) -> None:
        """A task started <60m ago should stay IN_PROGRESS."""
        tasks = [_make_in_progress_task("a", minutes_ago=30)]
        reclaimed_ids = reclaim_stale_tasks(tasks, stale_timeout_minutes=60)
        self.assertEqual(reclaimed_ids, [])
        self.assertEqual(tasks[0]["status"], "IN_PROGRESS")

    def test_returns_reclaimed_task_ids(self) -> None:
        """Should return IDs of all reclaimed tasks."""
        tasks = [
            _make_in_progress_task("a", minutes_ago=120),
            _make_in_progress_task("b", minutes_ago=90),
            _make_in_progress_task("c", minutes_ago=10),
        ]
        reclaimed_ids = reclaim_stale_tasks(tasks, stale_timeout_minutes=60)
        self.assertEqual(sorted(reclaimed_ids), ["a", "b"])

    def test_clears_started_at_on_reclaim(self) -> None:
        """started_at should be set to None after reclaim."""
        tasks = [_make_in_progress_task("a", minutes_ago=90)]
        reclaim_stale_tasks(tasks, stale_timeout_minutes=60)
        self.assertIsNone(tasks[0]["started_at"])

    def test_does_not_touch_completed_or_pending(self) -> None:
        """COMPLETED and PENDING tasks should remain unchanged."""
        tasks = [
            {"id": "a", "status": "COMPLETED", "started_at": "2024-01-01T00:00:00+00:00"},
            {"id": "b", "status": "PENDING", "started_at": None},
        ]
        reclaimed_ids = reclaim_stale_tasks(tasks, stale_timeout_minutes=60)
        self.assertEqual(reclaimed_ids, [])
        self.assertEqual(tasks[0]["status"], "COMPLETED")
        self.assertEqual(tasks[1]["status"], "PENDING")


class TestGetNextTaskWithStaleReclaim(unittest.TestCase):
    """Tests for get_next_task with stale_timeout_minutes parameter."""

    def test_returns_stale_task_before_pending(self) -> None:
        """Stale task (earlier in list) should be reclaimed and returned first."""
        tasks = [
            _make_in_progress_task("stale", minutes_ago=120),
            {"id": "pending", "status": "PENDING"},
        ]
        result = get_next_task(tasks, stale_timeout_minutes=60)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "stale")
        # Verify the stale task was reset to PENDING
        self.assertEqual(tasks[0]["status"], "PENDING")

    def test_returns_pending_when_no_stale(self) -> None:
        """When no stale tasks exist, returns the first PENDING task."""
        tasks = [
            _make_in_progress_task("fresh", minutes_ago=10),
            {"id": "pending", "status": "PENDING"},
        ]
        result = get_next_task(tasks, stale_timeout_minutes=60)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "pending")
        # Fresh IN_PROGRESS should not be touched
        self.assertEqual(tasks[0]["status"], "IN_PROGRESS")

    def test_backward_compatible_without_timeout(self) -> None:
        """get_next_task(tasks) without timeout should behave identically to current."""
        tasks = [
            _make_in_progress_task("stale", minutes_ago=120),
            {"id": "pending", "status": "PENDING"},
        ]
        result = get_next_task(tasks)
        # Without timeout, stale task is NOT reclaimed; returns pending
        self.assertEqual(result["id"], "pending")
        self.assertEqual(tasks[0]["status"], "IN_PROGRESS")


class TestGetProgressSummaryWithStale(unittest.TestCase):
    """Tests for get_progress_summary with stale_timeout_minutes parameter."""

    def test_counts_stale_tasks(self) -> None:
        """Summary should include a 'stale' count for expired IN_PROGRESS tasks."""
        started_long_ago = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
        started_recently = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        tasks = [
            {"status": "IN_PROGRESS", "started_at": started_long_ago,
             "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
            {"status": "IN_PROGRESS", "started_at": started_recently,
             "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
            {"status": "PENDING", "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        summary = get_progress_summary(tasks, stale_timeout_minutes=60)
        self.assertEqual(summary["stale"], 1)
        self.assertEqual(summary["in_progress"], 2)

    def test_no_stale_without_timeout(self) -> None:
        """Without timeout parameter, 'stale' should not be in the summary."""
        tasks = [
            {"status": "IN_PROGRESS", "started_at": "2024-01-01T00:00:00+00:00",
             "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        summary = get_progress_summary(tasks)
        self.assertNotIn("stale", summary)


class TestCityOnlyCategory(unittest.TestCase):
    """Tests for the cityOnly flag in generate_tasks."""

    def setUp(self) -> None:
        """Create temp files with a cityOnly category and a normal one."""
        self.tmpdir = tempfile.mkdtemp()
        self.categories_path = os.path.join(self.tmpdir, "categories.json")
        self.suburbs_path = os.path.join(self.tmpdir, "suburbs.json")

        self.suburbs_data = {"sydney": ["Parramatta", "Blacktown"]}
        with open(self.suburbs_path, "w") as f:
            json.dump(self.suburbs_data, f)

    def _write_categories(self, data: dict) -> None:
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


class TestMergeExistingState(unittest.TestCase):
    """Tests for the merge_existing_state function."""

    def test_merges_completed_state(self) -> None:
        """COMPLETED task state fields should be preserved."""
        new_tasks = [
            {"id": "a", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        existing_tasks = [
            {"id": "a", "status": "COMPLETED", "started_at": "2026-01-01T00:00:00+00:00",
             "completed_at": "2026-01-01T01:00:00+00:00", "listings_created": 5,
             "pages_searched": 3, "candidates_evaluated": 10,
             "candidates_rejected": 2, "candidates_duplicate": 3, "errors": ["err1"]},
        ]
        result = merge_existing_state(new_tasks, existing_tasks)
        self.assertEqual(result["merged_count"], 1)
        self.assertEqual(result["new_count"], 0)
        self.assertEqual(new_tasks[0]["status"], "COMPLETED")
        self.assertEqual(new_tasks[0]["listings_created"], 5)
        self.assertEqual(new_tasks[0]["errors"], ["err1"])

    def test_new_tasks_stay_pending(self) -> None:
        """Tasks not in existing list should remain PENDING."""
        new_tasks = [
            {"id": "new_task", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        existing_tasks = [
            {"id": "old_task", "status": "COMPLETED", "started_at": "2026-01-01T00:00:00+00:00",
             "completed_at": "2026-01-01T01:00:00+00:00", "listings_created": 5,
             "pages_searched": 3, "candidates_evaluated": 10,
             "candidates_rejected": 2, "candidates_duplicate": 3, "errors": []},
        ]
        result = merge_existing_state(new_tasks, existing_tasks)
        self.assertEqual(result["new_count"], 1)
        self.assertEqual(result["merged_count"], 0)
        self.assertEqual(new_tasks[0]["status"], "PENDING")

    def test_removed_tasks_counted(self) -> None:
        """Old tasks not in new list should be counted as removed."""
        new_tasks = [
            {"id": "a", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        existing_tasks = [
            {"id": "a", "status": "COMPLETED", "started_at": "2026-01-01T00:00:00+00:00",
             "completed_at": "2026-01-01T01:00:00+00:00", "listings_created": 5,
             "pages_searched": 3, "candidates_evaluated": 10,
             "candidates_rejected": 2, "candidates_duplicate": 3, "errors": []},
            {"id": "removed_task", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        result = merge_existing_state(new_tasks, existing_tasks)
        self.assertEqual(result["removed_count"], 1)

    def test_empty_existing_returns_all_new(self) -> None:
        """Empty existing list means all tasks are new."""
        new_tasks = [
            {"id": "a", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
            {"id": "b", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        result = merge_existing_state(new_tasks, [])
        self.assertEqual(result["new_count"], 2)
        self.assertEqual(result["merged_count"], 0)
        self.assertEqual(result["removed_count"], 0)


if __name__ == "__main__":
    unittest.main()
