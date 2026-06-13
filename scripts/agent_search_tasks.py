#!/usr/bin/env python3
"""CLI agent script to manage the web finder search task state machine.

Provides actions to generate task permutations, retrieve the next pending task,
mark tasks as completed with metrics, and view aggregate progress.
"""
import os
import sys
import json
import argparse

# Enable FINA_AGENT_MODE to route logs to stderr, keeping stdout clean for JSON
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add parent directory to path to allow importing modules
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.observability import BackendObservability
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


def main() -> None:
    """CLI script entrypoint."""
    parser = argparse.ArgumentParser(
        description="Manage the web finder search task state machine."
    )
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=["generate", "next", "complete", "summary"],
        help="Action to perform.",
    )
    parser.add_argument("--city", type=str, required=True, help="Target city (e.g. Sydney).")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    parser.add_argument(
        "--categories-file",
        type=str,
        default="data/categories.json",
        help="Path to categories.json file.",
    )
    parser.add_argument(
        "--suburbs-file",
        type=str,
        default="data/top_suburbs_per_city.json",
        help="Path to top_suburbs_per_city.json file.",
    )
    parser.add_argument(
        "--tasks-file",
        type=str,
        default=None,
        help="Path to the search tasks JSON file. Defaults to data/listing_web_search_tasks_{city}.json",
    )
    parser.add_argument(
        "--stale-timeout-minutes",
        type=int,
        default=60,
        help="Minutes after which an IN_PROGRESS task is considered stale and reclaimed (default: 60).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force regeneration of tasks, merging existing state into the new file.",
    )

    # Arguments for action="complete"
    parser.add_argument("--task-id", type=str, help="Task ID to complete.")
    parser.add_argument("--listings-created", type=int, default=0, help="Number of new listings created.")
    parser.add_argument("--pages-searched", type=int, default=0, help="Number of search result pages scanned.")
    parser.add_argument("--candidates-evaluated", type=int, default=0, help="Number of candidates evaluated.")
    parser.add_argument("--candidates-rejected", type=int, default=0, help="Number of candidates rejected.")
    parser.add_argument("--candidates-duplicate", type=int, default=0, help="Number of duplicate candidates found.")

    args = parser.parse_args()

    # Determine tasks file path
    city_key = args.city.lower().strip().replace(" ", "_")
    if args.tasks_file:
        tasks_path = args.tasks_file
    else:
        tasks_path = f"data/listing_web_search_tasks_{city_key}.json"

    try:
        if args.action == "generate":
            existing_tasks = load_tasks(tasks_path)

            if existing_tasks and not args.force:
                BackendObservability.info(
                    f"Tasks file already exists at {tasks_path} with {len(existing_tasks)} tasks. "
                    f"Use --force to regenerate with state merge.",
                    conversation_id=args.trace_id,
                )
                print(json.dumps({
                    "generated": False,
                    "reason": "file_exists",
                    "total_tasks": len(existing_tasks),
                    "file": tasks_path,
                }))
                return

            BackendObservability.info(
                f"Generating search tasks for city={args.city}"
                + (" (force merge)" if args.force else ""),
                conversation_id=args.trace_id,
            )
            new_tasks = generate_tasks(
                city=args.city,
                categories_path=args.categories_file,
                suburbs_path=args.suburbs_file,
            )
            merge_result = merge_existing_state(new_tasks, existing_tasks)

            # Atomic file replacement via temp file
            tmp_path = tasks_path + ".tmp"
            save_tasks(tmp_path, new_tasks)
            os.replace(tmp_path, tasks_path)

            BackendObservability.info(
                f"Generated {len(new_tasks)} tasks at {tasks_path} "
                f"(merged={merge_result['merged_count']}, "
                f"new={merge_result['new_count']}, "
                f"removed={merge_result['removed_count']})",
                conversation_id=args.trace_id,
            )
            print(json.dumps({
                "generated": True,
                "total_tasks": len(new_tasks),
                "merged_count": merge_result["merged_count"],
                "new_count": merge_result["new_count"],
                "removed_count": merge_result["removed_count"],
                "file": tasks_path,
            }))

        elif args.action == "next":
            tasks = load_tasks(tasks_path)
            if not tasks:
                BackendObservability.warning(
                    f"No tasks found at {tasks_path}. Run --action generate first.",
                    conversation_id=args.trace_id,
                )
                print("null")
                return

            reclaimed_ids = reclaim_stale_tasks(tasks, args.stale_timeout_minutes)
            for rid in reclaimed_ids:
                BackendObservability.warning(
                    f"Reclaimed stale task {rid} (exceeded {args.stale_timeout_minutes}m timeout)",
                    conversation_id=args.trace_id,
                )

            next_task = get_next_task(tasks)
            if next_task is None:
                BackendObservability.info(
                    "All tasks are completed or in progress.",
                    conversation_id=args.trace_id,
                )
                print("null")
                return

            task_id = next_task["id"]
            start_task(tasks, task_id)
            save_tasks(tasks_path, tasks)

            BackendObservability.info(
                f"Started task {task_id}: {next_task['formatted_query']}",
                conversation_id=args.trace_id,
            )
            # Re-read the task after mutation to get updated fields
            for t in tasks:
                if t["id"] == task_id:
                    print(json.dumps(t, ensure_ascii=False))
                    break

        elif args.action == "complete":
            if not args.task_id:
                raise ValueError("--task-id is required for the complete action")

            tasks = load_tasks(tasks_path)
            if not tasks:
                raise ValueError(f"No tasks found at {tasks_path}")

            metrics = {
                "listings_created": args.listings_created,
                "pages_searched": args.pages_searched,
                "candidates_evaluated": args.candidates_evaluated,
                "candidates_rejected": args.candidates_rejected,
                "candidates_duplicate": args.candidates_duplicate,
            }
            complete_task(tasks, args.task_id, metrics)
            save_tasks(tasks_path, tasks)

            BackendObservability.info(
                f"Completed task {args.task_id} with metrics: {metrics}",
                conversation_id=args.trace_id,
            )
            print(json.dumps({
                "completed": True,
                "task_id": args.task_id,
                "metrics": metrics,
            }))

        elif args.action == "summary":
            tasks = load_tasks(tasks_path)
            if not tasks:
                BackendObservability.warning(
                    f"No tasks found at {tasks_path}.",
                    conversation_id=args.trace_id,
                )
                print(json.dumps(get_progress_summary([], stale_timeout_minutes=args.stale_timeout_minutes)))
                return

            summary = get_progress_summary(tasks, stale_timeout_minutes=args.stale_timeout_minutes)
            BackendObservability.info(
                f"Progress summary for {args.city}: {summary}",
                conversation_id=args.trace_id,
            )
            print(json.dumps(summary))

    except Exception as e:
        BackendObservability.fatal(
            f"Failed during search tasks action={args.action}: {e}",
            exception=e,
            conversation_id=args.trace_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
