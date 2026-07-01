"""CLI script for post-hoc listing deduplication.

Actions:
  scan    — Informational scan: detects candidate duplicates, prints to stdout.
  plan    — Generates dedup plan file at data/dedup_plan_{city}.json.
  verdict — Records agent verdict for a specific group in the plan file.
  execute — Processes confirmed duplicate groups (merge + delete).
  summary — Prints stats from the plan file.
"""

import os
import sys
import json
import fcntl
import argparse
import asyncio
from datetime import datetime, timezone
from typing import Any

# Enable FINA_AGENT_CLI_MODE to route logs to stderr
os.environ["FINA_AGENT_CLI_MODE"] = "1"

# Add project root to python path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)

from features.shared.observability import BackendObservability
from features.scanning.dedup_blocking import (
    generate_candidate_groups,
    compute_merge_fields,
)


def _plan_path_for_city(city: str) -> str:
    """Returns the canonical plan file path for a city."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", f"dedup_plan_{city}.json")
    )


def _lock_path(plan_path: str) -> str:
    """Returns the lock file path for a plan file."""
    return plan_path + ".lock"


def generate_plan(
    city: str,
    listings: list[dict[str, Any]],
    plan_path: str,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Generates a dedup plan file from a list of listings.

    Runs the deterministic blocking engine and writes candidate groups
    to a structured JSON plan file with verdicts set to null.

    Args:
        city: The city being scanned.
        listings: Full listing dicts fetched from the database.
        plan_path: Path to write the plan file.
        trace_id: Trace correlation ID.

    Returns:
        The generated plan dict.
    """
    # Warn if existing plan has verdicts
    if os.path.exists(plan_path):
        try:
            with open(plan_path) as f:
                existing = json.load(f)
            has_verdicts = any(
                g.get("verdict") is not None
                for g in existing.get("groups", [])
            )
            if has_verdicts:
                BackendObservability.warning(
                    f"Existing plan at {plan_path} has verdicts that will be overwritten.",
                    conversation_id=trace_id,
                )
        except (json.JSONDecodeError, KeyError):
            pass

    BackendObservability.info(
        f"Generating dedup plan for {city} with {len(listings)} listings.",
        conversation_id=trace_id,
    )

    groups = generate_candidate_groups(listings)

    plan = {
        "city": city,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "traceId": trace_id,
        "groups": groups,
        "stats": {
            "totalListingsScanned": len(listings),
            "totalGroups": len(groups),
            "totalCandidateListings": sum(
                len(g["candidates"]) for g in groups
            ),
        },
    }

    os.makedirs(os.path.dirname(plan_path) or ".", exist_ok=True)
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2, default=str)

    BackendObservability.info(
        f"Plan generated: {len(groups)} candidate groups, "
        f"{plan['stats']['totalCandidateListings']} candidate listings.",
        conversation_id=trace_id,
    )

    return plan


def record_verdict(
    plan_path: str,
    group_id: int,
    verdict: str,
    survivor_id: str | None,
    reasoning: str,
    trace_id: str | None = None,
) -> None:
    """Records an agent verdict for a specific group in the plan file.

    Uses file locking for atomic updates.

    Args:
        plan_path: Path to the plan file.
        group_id: The group ID to update.
        verdict: CONFIRMED_DUPLICATE or FALSE_POSITIVE.
        survivor_id: UUID of the survivor listing (required for CONFIRMED_DUPLICATE).
        reasoning: Agent's reasoning for the verdict.
        trace_id: Trace correlation ID.

    Raises:
        ValueError: If group_id not found or invalid verdict.
        FileNotFoundError: If plan file does not exist.
    """
    if verdict not in ("CONFIRMED_DUPLICATE", "FALSE_POSITIVE"):
        raise ValueError(f"Invalid verdict: {verdict}. Must be CONFIRMED_DUPLICATE or FALSE_POSITIVE.")

    lock_path = _lock_path(plan_path)
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        with open(plan_path) as f:
            plan = json.load(f)

        target_group = None
        for group in plan["groups"]:
            if group["groupId"] == group_id:
                target_group = group
                break

        if target_group is None:
            raise ValueError(f"Group ID {group_id} not found in plan.")

        target_group["verdict"] = verdict
        target_group["reasoning"] = reasoning

        if verdict == "CONFIRMED_DUPLICATE":
            if not survivor_id:
                raise ValueError("survivor_id is required for CONFIRMED_DUPLICATE verdict.")

            # Validate survivor_id is in the group
            candidate_ids = {c["id"] for c in target_group["candidates"]}
            if survivor_id not in candidate_ids:
                raise ValueError(
                    f"Survivor ID {survivor_id} is not in the candidate group. "
                    f"Valid IDs: {candidate_ids}"
                )

            target_group["survivorId"] = survivor_id
            target_group["duplicateIds"] = [
                c["id"] for c in target_group["candidates"]
                if c["id"] != survivor_id
            ]

            # Recompute merge fields based on the chosen survivor
            survivor_data = next(
                c for c in target_group["candidates"] if c["id"] == survivor_id
            )
            aggregate_merge: dict[str, Any] = {}
            for dup_id in target_group["duplicateIds"]:
                dup_data = next(
                    c for c in target_group["candidates"] if c["id"] == dup_id
                )
                dup_merge = compute_merge_fields(survivor_data, dup_data)
                for k, v in dup_merge.items():
                    if k not in aggregate_merge:
                        aggregate_merge[k] = v
            target_group["mergeFields"] = aggregate_merge
        else:
            target_group["survivorId"] = None
            target_group["duplicateIds"] = []
            target_group["mergeFields"] = {}

        with open(plan_path, "w") as f:
            json.dump(plan, f, indent=2, default=str)

        BackendObservability.info(
            f"Verdict recorded for group {group_id}: {verdict}",
            conversation_id=trace_id,
        )

    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fd.close()


async def execute_plan(
    plan_path: str,
    trace_id: str | None = None,
) -> dict[str, int]:
    """Executes all CONFIRMED_DUPLICATE groups in the plan file.

    For each confirmed group:
      1. Merges non-null fields from duplicates into the survivor via UpdateListingData
      2. Deletes each duplicate via DeleteListing
      3. Marks the group as EXECUTED with a timestamp

    Skips groups without a verdict, with FALSE_POSITIVE verdict, or already executed.

    Returns:
        Stats dict with groups_executed, listings_merged, listings_deleted.
    """
    from features.shared.graphql_client import execute_graphql_operation

    with open(plan_path) as f:
        plan = json.load(f)

    stats = {
        "groups_executed": 0,
        "listings_merged": 0,
        "listings_deleted": 0,
    }

    for group in plan["groups"]:
        # Skip non-actionable groups
        if group.get("verdict") != "CONFIRMED_DUPLICATE":
            continue
        if group.get("executedAt") is not None:
            BackendObservability.trace(
                f"Skipping already-executed group {group['groupId']}.",
                conversation_id=trace_id,
            )
            continue

        survivor_id = group["survivorId"]
        duplicate_ids = group["duplicateIds"]
        merge_fields = group.get("mergeFields", {})

        BackendObservability.info(
            f"Executing group {group['groupId']}: "
            f"survivor={survivor_id}, duplicates={duplicate_ids}",
            conversation_id=trace_id,
        )

        # Step 1: Merge fields into survivor
        if merge_fields:
            merge_payload = {"id": survivor_id, **merge_fields}
            try:
                await execute_graphql_operation(
                    operation_name="UpdateListingData",
                    variables=merge_payload,
                )
                stats["listings_merged"] += 1
                BackendObservability.info(
                    f"Merged {len(merge_fields)} fields into survivor {survivor_id}.",
                    conversation_id=trace_id,
                )
            except Exception as exc:
                BackendObservability.error(
                    f"Failed to merge into survivor {survivor_id}: {exc}",
                    conversation_id=trace_id,
                )
                continue

        # Step 2: Delete duplicates
        all_deletes_succeeded = True
        for dup_id in duplicate_ids:
            try:
                await execute_graphql_operation(
                    operation_name="DeleteListing",
                    variables={"id": dup_id},
                )
                stats["listings_deleted"] += 1
                BackendObservability.info(
                    f"Deleted duplicate listing {dup_id}.",
                    conversation_id=trace_id,
                )
            except Exception as exc:
                all_deletes_succeeded = False
                BackendObservability.error(
                    f"Failed to delete duplicate {dup_id}: {exc}",
                    conversation_id=trace_id,
                )

        # Only mark group as executed when all deletes succeeded
        if all_deletes_succeeded:
            group["executedAt"] = datetime.now(timezone.utc).isoformat()
            stats["groups_executed"] += 1
        else:
            BackendObservability.warning(
                f"Group {group['groupId']} had partial delete failures. "
                f"Not marking as executed to allow retry.",
                conversation_id=trace_id,
            )

    # Save updated plan
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2, default=str)

    BackendObservability.info(
        f"Execution complete: {stats['groups_executed']} groups, "
        f"{stats['listings_merged']} merges, {stats['listings_deleted']} deletes.",
        conversation_id=trace_id,
    )

    return stats


def get_summary(plan_path: str) -> dict[str, int]:
    """Returns summary stats from a plan file.

    Returns:
        Dict with total_groups, pending_verdicts, confirmed_duplicates,
        false_positives, executed, listings_to_delete.
    """
    with open(plan_path) as f:
        plan = json.load(f)

    groups = plan.get("groups", [])
    summary = {
        "total_groups": len(groups),
        "pending_verdicts": sum(1 for g in groups if g.get("verdict") is None),
        "confirmed_duplicates": sum(
            1 for g in groups if g.get("verdict") == "CONFIRMED_DUPLICATE"
        ),
        "false_positives": sum(
            1 for g in groups if g.get("verdict") == "FALSE_POSITIVE"
        ),
        "executed": sum(
            1 for g in groups if g.get("executedAt") is not None
        ),
        "listings_to_delete": sum(
            len(g.get("duplicateIds", []))
            for g in groups
            if g.get("verdict") == "CONFIRMED_DUPLICATE"
            and g.get("executedAt") is None
        ),
        "total_listings_scanned": plan.get("stats", {}).get("totalListingsScanned", 0),
    }
    return summary


async def _fetch_all_city_listings(city: str, trace_id: str | None = None) -> list[dict[str, Any]]:
    """Fetches all listings for a city including FLAGGED status."""
    from features.shared.graphql_client import execute_graphql_operation

    BackendObservability.trace(
        f"Fetching all listings for {city} (all statuses).",
        conversation_id=trace_id,
    )
    result = await execute_graphql_operation(
        operation_name="ListAdminListings",
        variables={
            "city": city,
            "limit": 2000,
            "verificationStatuses": ["VERIFIED", "UNVERIFIED", "FLAGGED"],
        },
    )
    listings = (result or {}).get("data", {}).get("listings", [])
    BackendObservability.info(
        f"Retrieved {len(listings)} listings for {city}.",
        conversation_id=trace_id,
    )
    return listings


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-hoc listing deduplication scanner."
    )
    parser.add_argument(
        "--action",
        choices=["scan", "plan", "verdict", "execute", "summary"],
        required=True,
    )
    parser.add_argument("--city", type=str, required=True, help="City to process.")
    parser.add_argument("--group-id", type=int, default=None, help="Group ID for verdict action.")
    parser.add_argument(
        "--verdict",
        choices=["CONFIRMED_DUPLICATE", "FALSE_POSITIVE"],
        default=None,
        help="Verdict for the group.",
    )
    parser.add_argument("--survivor-id", type=str, default=None, help="Survivor listing UUID.")
    parser.add_argument("--reasoning", type=str, default=None, help="Reasoning for the verdict.")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    args = parser.parse_args()

    city = args.city.upper()
    plan_path = _plan_path_for_city(city)

    BackendObservability.info(
        f"Starting agent_dedup_scan.py: action={args.action}, city={city}",
        conversation_id=args.trace_id,
    )

    if args.action == "scan":
        listings = await _fetch_all_city_listings(city, args.trace_id)
        groups = generate_candidate_groups(listings)
        output = {
            "city": city,
            "totalListings": len(listings),
            "candidateGroups": len(groups),
            "groups": groups,
        }
        sys.stdout.write(json.dumps(output, indent=2, default=str))

    elif args.action == "plan":
        listings = await _fetch_all_city_listings(city, args.trace_id)
        plan = generate_plan(city, listings, plan_path, args.trace_id)
        sys.stdout.write(json.dumps(plan, indent=2, default=str))

    elif args.action == "verdict":
        if args.group_id is None or args.verdict is None:
            BackendObservability.fatal(
                "Validation Error: --group-id and --verdict are required for verdict action.",
                conversation_id=args.trace_id,
            )
            sys.exit(1)
        try:
            record_verdict(
                plan_path=plan_path,
                group_id=args.group_id,
                verdict=args.verdict,
                survivor_id=args.survivor_id,
                reasoning=args.reasoning or "",
                trace_id=args.trace_id,
            )
            BackendObservability.info(
                f"Verdict recorded for group {args.group_id}: {args.verdict}",
                conversation_id=args.trace_id,
            )
        except (ValueError, FileNotFoundError) as exc:
            BackendObservability.error(str(exc), conversation_id=args.trace_id)
            sys.exit(1)

    elif args.action == "execute":
        if not os.path.exists(plan_path):
            BackendObservability.fatal(
                f"Plan file not found: {plan_path}. Run --action plan first.",
                conversation_id=args.trace_id,
            )
            sys.exit(1)
        stats = await execute_plan(plan_path, args.trace_id)
        sys.stdout.write(json.dumps(stats, indent=2))

    elif args.action == "summary":
        if not os.path.exists(plan_path):
            BackendObservability.fatal(
                f"Plan file not found: {plan_path}. Run --action plan first.",
                conversation_id=args.trace_id,
            )
            sys.exit(1)
        summary = get_summary(plan_path)
        sys.stdout.write(json.dumps(summary, indent=2))


if __name__ == "__main__":
    from features.shared.env_loader import load_env_file
    load_env_file()
    asyncio.run(main())
