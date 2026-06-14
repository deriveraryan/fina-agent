"""Unit tests for features.scanning.task_lifecycle module.

Tests the generic task lifecycle functions: load/save, state transitions
(PENDING → IN_PROGRESS → COMPLETED), stale task reclamation, merge logic,
and progress aggregation.
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from features.scanning.task_lifecycle import (
    load_tasks,
    save_tasks,
    get_next_task,
    start_task,
    complete_task,
    get_progress_summary,
    reclaim_stale_tasks,
    merge_existing_state,
)


# Test-scoped constants matching web search defaults for lifecycle tests
_TEST_ALLOWED_METRICS = {
    "listings_created", "pages_searched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate",
}

_TEST_METRIC_FIELDS = (
    "listings_created", "pages_searched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate",
)

_TEST_MUTABLE_FIELDS = (
    "status", "started_at", "completed_at",
    "listings_created", "pages_searched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate", "errors",
)


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


class TestLoadSaveTasks(unittest.TestCase):
    """Tests for load_tasks and save_tasks."""

    def setUp(self) -> None:
        """Create a temporary directory for task files."""
        self.tmpdir = tempfile.mkdtemp()
        self.tasks_path = os.path.join(self.tmpdir, "tasks.json")

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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
    """Tests for complete_task with parameterized allowed_metrics."""

    def _make_task(self) -> dict:
        """Create a standard IN_PROGRESS task for completion tests."""
        return {
            "id": "a", "status": "IN_PROGRESS", "completed_at": None,
            "listings_created": 0, "pages_searched": 0,
            "candidates_evaluated": 0, "candidates_rejected": 0,
            "candidates_duplicate": 0, "errors": [],
        }

    def test_transitions_to_completed(self) -> None:
        """Should set the task status to COMPLETED."""
        tasks = [self._make_task()]
        metrics = {"listings_created": 3, "pages_searched": 5}
        updated = complete_task(tasks, "a", metrics, _TEST_ALLOWED_METRICS)
        self.assertEqual(updated[0]["status"], "COMPLETED")

    def test_merges_metrics(self) -> None:
        """Should merge the provided metrics into the task."""
        tasks = [self._make_task()]
        metrics = {
            "listings_created": 3,
            "pages_searched": 5,
            "candidates_evaluated": 10,
            "candidates_rejected": 2,
            "candidates_duplicate": 4,
        }
        updated = complete_task(tasks, "a", metrics, _TEST_ALLOWED_METRICS)
        self.assertEqual(updated[0]["listings_created"], 3)
        self.assertEqual(updated[0]["pages_searched"], 5)
        self.assertEqual(updated[0]["candidates_evaluated"], 10)

    def test_sets_completed_at_timestamp(self) -> None:
        """Should record an ISO 8601 completed_at timestamp."""
        tasks = [self._make_task()]
        updated = complete_task(tasks, "a", {}, _TEST_ALLOWED_METRICS)
        self.assertIsNotNone(updated[0]["completed_at"])
        datetime.fromisoformat(updated[0]["completed_at"])

    def test_raises_for_non_in_progress_task(self) -> None:
        """Should raise ValueError if the task is not IN_PROGRESS."""
        tasks = [{
            "id": "a", "status": "PENDING", "completed_at": None,
            "listings_created": 0, "pages_searched": 0,
            "candidates_evaluated": 0, "candidates_rejected": 0,
            "candidates_duplicate": 0, "errors": [],
        }]
        with self.assertRaises(ValueError):
            complete_task(tasks, "a", {}, _TEST_ALLOWED_METRICS)

    def test_ignores_unknown_metric_keys(self) -> None:
        """Metrics not in allowed_metrics should be silently dropped."""
        tasks = [self._make_task()]
        metrics = {"listings_created": 3, "bogus_metric": 99}
        updated = complete_task(tasks, "a", metrics, _TEST_ALLOWED_METRICS)
        self.assertNotIn("bogus_metric", updated[0])
        self.assertEqual(updated[0]["listings_created"], 3)

    def test_maps_specific_metric_set(self) -> None:
        """Maps metrics (places_fetched) should merge; web metrics (pages_searched) should be dropped."""
        _MAP_ALLOWED = {
            "listings_created", "places_fetched",
            "candidates_evaluated", "candidates_rejected",
            "candidates_duplicate",
        }
        task = {
            "id": "a", "status": "IN_PROGRESS", "completed_at": None,
            "listings_created": 0, "places_fetched": 0,
            "candidates_evaluated": 0, "candidates_rejected": 0,
            "candidates_duplicate": 0, "errors": [],
        }
        metrics = {"listings_created": 2, "places_fetched": 15, "pages_searched": 99}
        updated = complete_task([task], "a", metrics, _MAP_ALLOWED)
        self.assertEqual(updated[0]["places_fetched"], 15)
        self.assertEqual(updated[0]["listings_created"], 2)
        # pages_searched is not in MAP_ALLOWED, so should NOT be merged
        self.assertEqual(updated[0].get("pages_searched", "NOT_SET"), "NOT_SET")


class TestGetProgressSummary(unittest.TestCase):
    """Tests for get_progress_summary with parameterized metric_fields."""

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
        summary = get_progress_summary(tasks, _TEST_METRIC_FIELDS)
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
        summary = get_progress_summary([], _TEST_METRIC_FIELDS)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["total_listings_created"], 0)


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
        summary = get_progress_summary(tasks, _TEST_METRIC_FIELDS, stale_timeout_minutes=60)
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
        summary = get_progress_summary(tasks, _TEST_METRIC_FIELDS)
        self.assertNotIn("stale", summary)


class TestMergeExistingState(unittest.TestCase):
    """Tests for the merge_existing_state function with parameterized mutable_fields."""

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
        result = merge_existing_state(new_tasks, existing_tasks, _TEST_MUTABLE_FIELDS)
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
        result = merge_existing_state(new_tasks, existing_tasks, _TEST_MUTABLE_FIELDS)
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
        result = merge_existing_state(new_tasks, existing_tasks, _TEST_MUTABLE_FIELDS)
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
        result = merge_existing_state(new_tasks, [], _TEST_MUTABLE_FIELDS)
        self.assertEqual(result["new_count"], 2)
        self.assertEqual(result["merged_count"], 0)
        self.assertEqual(result["removed_count"], 0)

    def test_preserves_in_progress_state(self) -> None:
        """IN_PROGRESS task state should be preserved during force regeneration."""
        new_tasks = [
            {"id": "a", "status": "PENDING", "started_at": None,
             "completed_at": None, "listings_created": 0, "pages_searched": 0,
             "candidates_evaluated": 0, "candidates_rejected": 0,
             "candidates_duplicate": 0, "errors": []},
        ]
        existing_tasks = [
            {"id": "a", "status": "IN_PROGRESS",
             "started_at": "2026-06-01T10:00:00+00:00",
             "completed_at": None, "listings_created": 1, "pages_searched": 2,
             "candidates_evaluated": 5, "candidates_rejected": 1,
             "candidates_duplicate": 0, "errors": []},
        ]
        result = merge_existing_state(new_tasks, existing_tasks, _TEST_MUTABLE_FIELDS)
        self.assertEqual(result["merged_count"], 1)
        self.assertEqual(new_tasks[0]["status"], "IN_PROGRESS")
        self.assertEqual(new_tasks[0]["started_at"], "2026-06-01T10:00:00+00:00")
        self.assertEqual(new_tasks[0]["listings_created"], 1)


if __name__ == "__main__":
    unittest.main()
