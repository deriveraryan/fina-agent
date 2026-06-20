#!/usr/bin/env python3
"""CLI agent script to manage the events listing task state machine.

Provides actions to generate per-listing events tasks (for listings with
social URLs), retrieve the next pending task, mark tasks as completed
with metrics, and view aggregate progress.
"""
import os
import sys
import json
import argparse
import asyncio

# Enable FINA_AGENT_CLI_MODE to route logs to stderr, keeping stdout clean for JSON
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add parent directory to path to allow importing modules
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)

from features.shared.observability import BackendObservability
from features.scanning.events_tasks import (
    generate_events_tasks,
    EVENTS_MUTABLE_FIELDS,
    EVENTS_METRIC_FIELDS,
    EVENTS_ALLOWED_METRICS,
)
from features.scanning.task_lifecycle import (
    load_tasks,
    save_tasks,
    get_progress_summary,
    merge_existing_state,
    locked_next_task,
    locked_complete_task,
)


async def fetch_city_listings(city: str, trace_id: str | None = None) -> list[dict]:
    """Fetch all listings for a city from the database via ListAdminListings.

    Retrieves both VERIFIED and UNVERIFIED listings so events can be
    discovered from all active business pages.

    Args:
        city: Target city name (e.g. "Sydney").
        trace_id: Trace correlation ID for observability.

    Returns:
        A list of listing dictionaries.
    """
    BackendObservability.trace(
        f"Fetching all listings for city={city} via ListAdminListings",
        conversation_id=trace_id,
    )
    from features.shared.graphql_client import execute_graphql_operation
    result = await execute_graphql_operation(
        operation_name="ListAdminListings",
        variables={
            "city": city,
            "limit": 1000,
            "verificationStatuses": ["VERIFIED", "UNVERIFIED"],
        },
    )
    listings = result.get("data", {}).get("listings", [])
    BackendObservability.info(
        f"Retrieved {len(listings)} listings for {city}.",
        conversation_id=trace_id,
    )
    return listings


async def async_generate(args: argparse.Namespace, tasks_path: str) -> None:
    """Async handler for the generate action (requires DB fetch)."""
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
        f"Generating events tasks for city={args.city}"
        + (" (force merge)" if args.force else ""),
        conversation_id=args.trace_id,
    )

    listings = await fetch_city_listings(args.city, args.trace_id)
    new_tasks = generate_events_tasks(listings)
    merge_result = merge_existing_state(new_tasks, existing_tasks, EVENTS_MUTABLE_FIELDS)

    save_tasks(tasks_path, new_tasks)

    BackendObservability.info(
        f"Generated {len(new_tasks)} events tasks at {tasks_path} "
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


def main() -> None:
    """CLI script entrypoint."""
    parser = argparse.ArgumentParser(
        description="Manage the events listing task state machine."
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
        "--tasks-file",
        type=str,
        default=None,
        help="Path to the events tasks JSON file. Defaults to data/listing_events_tasks_{city}.json",
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
    parser.add_argument("--events-discovered", type=int, default=0, help="Number of events discovered.")
    parser.add_argument("--events-pushed", type=int, default=0, help="Number of events pushed to DB.")
    parser.add_argument("--social-urls-scanned", type=int, default=0, help="Number of social URLs scanned.")
    parser.add_argument("--follower-counts-updated", type=int, default=0, help="Number of follower counts updated.")
    parser.add_argument("--bookmarks-updated", type=int, default=0, help="Number of scan bookmarks updated.")

    args = parser.parse_args()

    # Determine tasks file path
    city_key = args.city.lower().strip().replace(" ", "_")
    if args.tasks_file:
        tasks_path = args.tasks_file
    else:
        tasks_path = f"data/listing_events_tasks_{city_key}.json"

    try:
        if args.action == "generate":
            asyncio.run(async_generate(args, tasks_path))

        elif args.action == "next":
            started_task, reclaimed_ids, _tasks = locked_next_task(
                tasks_path, args.stale_timeout_minutes
            )

            for rid in reclaimed_ids:
                BackendObservability.warning(
                    f"Reclaimed stale task {rid} (exceeded {args.stale_timeout_minutes}m timeout)",
                    conversation_id=args.trace_id,
                )

            if not _tasks:
                BackendObservability.warning(
                    f"No tasks found at {tasks_path}. Run --action generate first.",
                    conversation_id=args.trace_id,
                )
                print("null")
                return

            if started_task is None:
                BackendObservability.info(
                    "All tasks are completed or in progress.",
                    conversation_id=args.trace_id,
                )
                print("null")
                return

            BackendObservability.info(
                f"Started events task {started_task['id']}: {started_task['name']}",
                conversation_id=args.trace_id,
            )
            print(json.dumps(started_task, ensure_ascii=False))

        elif args.action == "complete":
            if not args.task_id:
                raise ValueError("--task-id is required for the complete action")

            metrics = {
                "events_discovered": args.events_discovered,
                "events_pushed": args.events_pushed,
                "social_urls_scanned": args.social_urls_scanned,
                "follower_counts_updated": args.follower_counts_updated,
                "bookmarks_updated": args.bookmarks_updated,
            }
            locked_complete_task(tasks_path, args.task_id, metrics, EVENTS_ALLOWED_METRICS)

            BackendObservability.info(
                f"Completed events task {args.task_id} with metrics: {metrics}",
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
                print(json.dumps(get_progress_summary([], EVENTS_METRIC_FIELDS, stale_timeout_minutes=args.stale_timeout_minutes)))
                return

            summary = get_progress_summary(tasks, EVENTS_METRIC_FIELDS, stale_timeout_minutes=args.stale_timeout_minutes)
            BackendObservability.info(
                f"Events progress for {args.city}: {summary}",
                conversation_id=args.trace_id,
            )
            print(json.dumps(summary))

    except Exception as e:
        BackendObservability.fatal(
            f"Failed during events tasks action={args.action}: {e}",
            exception=e,
            conversation_id=args.trace_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    main()
