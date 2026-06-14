"""Shared task lifecycle functions for task-based state machines.

Provides generic, type-agnostic functions for loading, saving, and managing
task state transitions (PENDING → IN_PROGRESS → COMPLETED). Used by both
the web search and maps search task systems.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set


def load_tasks(tasks_path: str) -> List[Dict[str, Any]]:
    """Load the task list from a JSON file.

    Args:
        tasks_path: Absolute path to the tasks JSON file.

    Returns:
        A list of task dictionaries, or an empty list if the file
        is missing or contains invalid JSON.
    """
    if not os.path.exists(tasks_path):
        return []
    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, IOError):
        return []


def save_tasks(tasks_path: str, tasks: List[Dict[str, Any]]) -> None:
    """Save the task list to a JSON file atomically via write-then-rename.

    Writes to a temporary file first, then atomically replaces the target
    file using os.replace(). Creates parent directories if they do not exist.

    Args:
        tasks_path: Absolute path to the tasks JSON file.
        tasks: The list of task dictionaries to serialize.
    """
    os.makedirs(os.path.dirname(tasks_path) or ".", exist_ok=True)
    tmp_path = tasks_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, tasks_path)


def _is_stale_task(task: Dict[str, Any], cutoff: datetime) -> bool:
    """Check if an IN_PROGRESS task has exceeded the stale cutoff.

    Args:
        task: A task dictionary.
        cutoff: The UTC datetime threshold. Tasks started before this
            are considered stale.

    Returns:
        True if the task is IN_PROGRESS and started before the cutoff.
    """
    if task.get("status") != "IN_PROGRESS":
        return False
    started_at_str = task.get("started_at")
    if not started_at_str:
        return False
    return datetime.fromisoformat(started_at_str) < cutoff


def reclaim_stale_tasks(
    tasks: List[Dict[str, Any]],
    stale_timeout_minutes: int,
) -> List[str]:
    """Reset IN_PROGRESS tasks that have exceeded the stale timeout to PENDING.

    Scans the task list for IN_PROGRESS tasks whose started_at timestamp
    is older than now minus the stale_timeout_minutes threshold. Matching
    tasks are reset to PENDING with started_at cleared.

    Args:
        tasks: The list of task dictionaries (mutated in place).
        stale_timeout_minutes: The number of minutes after which an
            IN_PROGRESS task is considered stale.

    Returns:
        A list of task IDs that were reclaimed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
    reclaimed_ids: List[str] = []

    for task in tasks:
        if _is_stale_task(task, cutoff):
            task["status"] = "PENDING"
            task["started_at"] = None
            reclaimed_ids.append(task["id"])

    return reclaimed_ids


def get_next_task(
    tasks: List[Dict[str, Any]],
    stale_timeout_minutes: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Return the first task with PENDING status, or None if all are done.

    When stale_timeout_minutes is provided, IN_PROGRESS tasks that have
    exceeded the timeout are first reset to PENDING before scanning.
    Since stale tasks appear earlier in the list than untouched PENDING
    tasks, they are returned first.

    Args:
        tasks: The list of task dictionaries.
        stale_timeout_minutes: Optional timeout in minutes. When provided,
            stale IN_PROGRESS tasks are automatically reclaimed.

    Returns:
        The first PENDING task dictionary, or None.
    """
    if stale_timeout_minutes is not None:
        reclaim_stale_tasks(tasks, stale_timeout_minutes)

    for task in tasks:
        if task.get("status") == "PENDING":
            return task
    return None


def start_task(
    tasks: List[Dict[str, Any]],
    task_id: str,
) -> List[Dict[str, Any]]:
    """Transition a task from PENDING to IN_PROGRESS.

    Args:
        tasks: The list of task dictionaries (mutated in place).
        task_id: The ID of the task to start.

    Returns:
        The updated list of task dictionaries.

    Raises:
        ValueError: If the task ID is not found or the task is not PENDING.
    """
    for task in tasks:
        if task["id"] == task_id:
            if task["status"] != "PENDING":
                raise ValueError(
                    f"Cannot start task '{task_id}': status is '{task['status']}', expected 'PENDING'"
                )
            task["status"] = "IN_PROGRESS"
            task["started_at"] = datetime.now(timezone.utc).isoformat()
            return tasks

    raise ValueError(f"Task '{task_id}' not found in task list")


def complete_task(
    tasks: List[Dict[str, Any]],
    task_id: str,
    metrics: Dict[str, Any],
    allowed_metrics: Set[str],
) -> List[Dict[str, Any]]:
    """Transition a task from IN_PROGRESS to COMPLETED with metrics.

    Args:
        tasks: The list of task dictionaries (mutated in place).
        task_id: The ID of the task to complete.
        metrics: A dictionary of metric values to merge into the task.
        allowed_metrics: Set of metric field names that are valid for
            this task type (e.g. web search vs maps search).

    Returns:
        The updated list of task dictionaries.

    Raises:
        ValueError: If the task ID is not found or the task is not IN_PROGRESS.
    """
    for task in tasks:
        if task["id"] == task_id:
            if task["status"] != "IN_PROGRESS":
                raise ValueError(
                    f"Cannot complete task '{task_id}': status is '{task['status']}', expected 'IN_PROGRESS'"
                )
            task["status"] = "COMPLETED"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()

            for key, value in metrics.items():
                if key in allowed_metrics:
                    task[key] = value

            return tasks

    raise ValueError(f"Task '{task_id}' not found in task list")


def merge_existing_state(
    new_tasks: List[Dict[str, Any]],
    existing_tasks: List[Dict[str, Any]],
    mutable_fields: Sequence[str],
) -> Dict[str, int]:
    """Merge mutable state from existing tasks into new tasks by ID match.

    For each task in new_tasks, if a matching task ID exists in existing_tasks,
    all mutable state fields (status, timestamps, metrics, errors) are copied
    from the existing task into the new task.

    Args:
        new_tasks: The freshly generated task list (mutated in place).
        existing_tasks: The previously persisted task list.
        mutable_fields: Sequence of field names to copy from existing
            to new tasks on ID match.

    Returns:
        A dictionary with merge statistics:
        - merged_count: Tasks with state preserved from existing.
        - new_count: Tasks with no existing match (fresh PENDING).
        - removed_count: Existing tasks not present in the new list.
    """
    existing_lookup: Dict[str, Dict[str, Any]] = {
        task["id"]: task for task in existing_tasks
    }

    merged_count = 0

    for task in new_tasks:
        existing_task = existing_lookup.get(task["id"])
        if existing_task is not None:
            for field in mutable_fields:
                if field in existing_task:
                    task[field] = existing_task[field]
            merged_count += 1

    new_count = len(new_tasks) - merged_count
    removed_count = len(existing_tasks) - merged_count

    return {
        "merged_count": merged_count,
        "new_count": new_count,
        "removed_count": removed_count,
    }


def get_progress_summary(
    tasks: List[Dict[str, Any]],
    metric_fields: Sequence[str],
    stale_timeout_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute aggregate progress statistics across all tasks.

    Args:
        tasks: The list of task dictionaries.
        metric_fields: Sequence of metric field names to aggregate
            (e.g. ["listings_created", "pages_searched"]).
        stale_timeout_minutes: Optional timeout in minutes. When provided,
            IN_PROGRESS tasks exceeding the timeout are counted as 'stale'
            in the output.

    Returns:
        A dictionary with aggregate counts and totals.
    """
    total = len(tasks)
    pending = sum(1 for t in tasks if t.get("status") == "PENDING")
    in_progress = sum(1 for t in tasks if t.get("status") == "IN_PROGRESS")
    completed = sum(1 for t in tasks if t.get("status") == "COMPLETED")

    total_errors = sum(len(t.get("errors", [])) for t in tasks)

    summary: Dict[str, Any] = {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
        "total_errors": total_errors,
    }

    for field in metric_fields:
        summary_key = f"total_{field}"
        summary[summary_key] = sum(t.get(field, 0) for t in tasks)

    if stale_timeout_minutes is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_timeout_minutes)
        stale = sum(1 for t in tasks if _is_stale_task(t, cutoff))
        summary["stale"] = stale

    return summary
