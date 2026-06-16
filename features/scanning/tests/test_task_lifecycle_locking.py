"""Tests for concurrent task lifecycle locking primitives.

Verifies that locked_next_task and locked_complete_task provide
mutual exclusion when multiple processes access the same task file.
"""

import json
import multiprocessing
import os
import tempfile
import unittest

from features.scanning.task_lifecycle import (
    load_tasks,
    save_tasks,
    task_file_lock,
    locked_next_task,
    locked_complete_task,
    start_task,
    get_next_task,
)


def _worker_claim_task(tasks_path: str, result_queue: multiprocessing.Queue) -> None:
    """Worker function that claims a task and reports which task it got."""
    task, _reclaimed, _tasks = locked_next_task(tasks_path)
    task_id = task["id"] if task else None
    result_queue.put(task_id)


class TestTaskFileLock(unittest.TestCase):
    """Tests for the task_file_lock context manager."""

    def test_lock_creates_lock_file(self) -> None:
        """Lock file is created next to the tasks file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            save_tasks(tasks_path, [{"id": "t1", "status": "PENDING"}])

            with task_file_lock(tasks_path):
                lock_path = tasks_path + ".lock"
                self.assertTrue(os.path.exists(lock_path))

    def test_lock_is_reentrant_safe(self) -> None:
        """Two sequential lock acquisitions don't deadlock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            save_tasks(tasks_path, [{"id": "t1", "status": "PENDING"}])

            with task_file_lock(tasks_path):
                pass
            with task_file_lock(tasks_path):
                pass


class TestLockedNextTask(unittest.TestCase):
    """Tests for locked_next_task."""

    def test_single_agent_claims_task(self) -> None:
        """A single call returns the first PENDING task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            tasks = [
                {"id": "t1", "status": "PENDING", "formatted_query": "q1", "started_at": None},
                {"id": "t2", "status": "PENDING", "formatted_query": "q2", "started_at": None},
            ]
            save_tasks(tasks_path, tasks)

            task, reclaimed, all_tasks = locked_next_task(tasks_path)
            self.assertIsNotNone(task)
            self.assertEqual(task["id"], "t1")
            self.assertEqual(task["status"], "IN_PROGRESS")
            self.assertEqual(reclaimed, [])

    def test_returns_none_when_all_complete(self) -> None:
        """Returns None when no PENDING tasks remain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            tasks = [
                {"id": "t1", "status": "COMPLETED", "started_at": None, "completed_at": "2026-01-01"},
            ]
            save_tasks(tasks_path, tasks)

            task, _, _ = locked_next_task(tasks_path)
            self.assertIsNone(task)

    def test_returns_none_when_file_missing(self) -> None:
        """Returns None when the tasks file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "nonexistent.json")
            task, _, tasks = locked_next_task(tasks_path)
            self.assertIsNone(task)
            self.assertEqual(tasks, [])

    def test_concurrent_agents_get_unique_tasks(self) -> None:
        """3 concurrent processes each claim a different task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            tasks = [
                {"id": f"t{i}", "status": "PENDING", "formatted_query": f"q{i}", "started_at": None}
                for i in range(5)
            ]
            save_tasks(tasks_path, tasks)

            result_queue = multiprocessing.Queue()
            workers = []
            for _ in range(3):
                p = multiprocessing.Process(
                    target=_worker_claim_task,
                    args=(tasks_path, result_queue),
                )
                workers.append(p)

            for p in workers:
                p.start()
            for p in workers:
                p.join(timeout=10)

            claimed_ids = set()
            while not result_queue.empty():
                claimed_ids.add(result_queue.get())

            # All 3 processes should have claimed a task
            self.assertEqual(len(claimed_ids), 3, f"Expected 3 unique tasks, got: {claimed_ids}")
            # None of them should be None
            self.assertNotIn(None, claimed_ids)
            # All should be different
            self.assertTrue(claimed_ids.issubset({"t0", "t1", "t2", "t3", "t4"}))

            # Verify the file state reflects 3 IN_PROGRESS tasks
            final_tasks = load_tasks(tasks_path)
            in_progress = [t for t in final_tasks if t["status"] == "IN_PROGRESS"]
            self.assertEqual(len(in_progress), 3)


class TestLockedCompleteTask(unittest.TestCase):
    """Tests for locked_complete_task."""

    def test_completes_task_with_metrics(self) -> None:
        """Task transitions to COMPLETED with metrics persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            tasks = [
                {"id": "t1", "status": "IN_PROGRESS", "started_at": "2026-01-01T00:00:00+00:00"},
            ]
            save_tasks(tasks_path, tasks)

            metrics = {"listings_created": 5, "pages_searched": 3}
            locked_complete_task(
                tasks_path, "t1", metrics, {"listings_created", "pages_searched"}
            )

            final = load_tasks(tasks_path)
            self.assertEqual(final[0]["status"], "COMPLETED")
            self.assertEqual(final[0]["listings_created"], 5)
            self.assertEqual(final[0]["pages_searched"], 3)

    def test_raises_on_missing_file(self) -> None:
        """Raises ValueError when the task file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "nonexistent.json")
            with self.assertRaises(ValueError):
                locked_complete_task(tasks_path, "t1", {}, set())

    def test_raises_on_wrong_status(self) -> None:
        """Raises ValueError when trying to complete a PENDING task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks_path = os.path.join(tmpdir, "tasks.json")
            tasks = [{"id": "t1", "status": "PENDING", "started_at": None}]
            save_tasks(tasks_path, tasks)

            with self.assertRaises(ValueError):
                locked_complete_task(tasks_path, "t1", {}, set())


if __name__ == "__main__":
    unittest.main()
