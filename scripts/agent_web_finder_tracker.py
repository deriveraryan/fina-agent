#!/usr/bin/env python3
"""CLI agent script to manage deterministic web finder tracking and report generation."""
import os
import sys
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
from features.scanning.tracker import (
    init_tracker,
    add_search,
    add_candidate,
    add_error,
    generate_report,
)


def main() -> None:
    """CLI script entrypoint."""
    parser = argparse.ArgumentParser(
        description="Deterministic tracking helper for Fina new listing web finder subagent."
    )
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=["init", "add-search", "add-candidate", "add-error", "generate-report"],
        help="Action to perform.",
    )
    parser.add_argument("--trace-id", type=str, required=True, help="Trace correlation ID.")
    parser.add_argument(
        "--tracker-file",
        type=str,
        default=None,
        help="Path to the tracker JSON file. Defaults to .antigravity_saves/web_finder_tracker_{trace_id}.json",
    )
    parser.add_argument(
        "--suburbs-file",
        type=str,
        default="data/top_suburbs_per_city.json",
        help="Path to the top suburbs JSON file.",
    )

    # Arguments for action="init"
    parser.add_argument("--city", type=str, help="Target city (e.g. Sydney).")
    parser.add_argument("--category", type=str, help="Canonical category (e.g. RESTAURANT).")
    parser.add_argument("--template-index", type=int, help="Selected template index.")
    parser.add_argument("--template-string", type=str, help="Raw search template string.")
    parser.add_argument("--formatted-query", type=str, help="Formatted search template query.")

    # Arguments for action="add-search"
    parser.add_argument("--query", type=str, help="Search query string.")
    parser.add_argument(
        "--platform",
        type=str,
        help="Platform searched (e.g. Facebook, Instagram, General Web).",
    )
    parser.add_argument("--pages-read", type=int, default=1, help="Number of pages read.")

    # Arguments for action="add-candidate"
    parser.add_argument("--name", type=str, help="Candidate business name.")
    parser.add_argument("--url", type=str, help="Candidate page or website URL.")
    parser.add_argument(
        "--status",
        type=str,
        choices=["CREATED", "DUPLICATE", "REJECTED", "ERROR"],
        help="Evaluation status.",
    )
    parser.add_argument("--reason", type=str, help="Reason/justification for evaluation status.")
    parser.add_argument("--db-id", type=str, default=None, help="Database listing UUID if created.")
    parser.add_argument("--address", type=str, default=None, help="Extracted address.")
    parser.add_argument("--description", type=str, default=None, help="Description.")
    parser.add_argument("--tags", type=str, default=None, help="Comma-separated tags.")
    parser.add_argument("--category-val", type=str, default=None, help="Category value.")

    # Arguments for action="add-error"
    parser.add_argument("--error", type=str, help="Operational error description.")

    # Arguments for action="generate-report"
    parser.add_argument(
        "--template-file",
        type=str,
        default=".agents/skills/fina_new_listing_web_finder/REPORT_TEMPLATE.md",
        help="Path to REPORT_TEMPLATE.md file.",
    )
    parser.add_argument(
        "--logs-dir",
        type=str,
        default="logs",
        help="Path to logs output folder.",
    )

    args = parser.parse_args()

    # Determine tracker path
    if args.tracker_file:
        tracker_path = args.tracker_file
    else:
        tracker_path = f".antigravity_saves/web_finder_tracker_{args.trace_id}.json"

    try:
        if args.action == "init":
            if not args.city or not args.category or args.template_index is None or not args.template_string or not args.formatted_query:
                raise ValueError("init action requires: --city, --category, --template-index, --template-string, --formatted-query")
            BackendObservability.info(
                f"Initializing tracker for trace-id={args.trace_id} at {tracker_path}",
                conversation_id=args.trace_id,
            )
            init_tracker(
                city=args.city,
                category=args.category,
                template_index=args.template_index,
                template_string=args.template_string,
                formatted_query=args.formatted_query,
                trace_id=args.trace_id,
                tracker_path=tracker_path,
            )
            print(f'{{"initialized": true, "tracker_file": "{tracker_path}"}}')

        elif args.action == "add-search":
            if not args.query or not args.platform:
                raise ValueError("add-search action requires: --query, --platform")
            BackendObservability.info(
                f"Logging web search platform={args.platform} pages_read={args.pages_read} for trace-id={args.trace_id}",
                conversation_id=args.trace_id,
            )
            add_search(
                query=args.query,
                platform=args.platform,
                pages_read=args.pages_read,
                tracker_path=tracker_path,
                suburbs_path=args.suburbs_file,
            )
            print('{"added_search": true}')

        elif args.action == "add-candidate":
            if not args.name or not args.url or not args.platform or not args.status or not args.reason:
                raise ValueError("add-candidate action requires: --name, --url, --platform, --status, --reason")
            BackendObservability.info(
                f"Logging candidate '{args.name}' status={args.status} for trace-id={args.trace_id}",
                conversation_id=args.trace_id,
            )
            add_candidate(
                name=args.name,
                url=args.url,
                platform=args.platform,
                status=args.status,
                reason=args.reason,
                db_id=args.db_id,
                address=args.address,
                description=args.description,
                tags=args.tags,
                category=args.category_val,
                tracker_path=tracker_path,
            )
            print('{"added_candidate": true}')

        elif args.action == "add-error":
            if not args.error:
                raise ValueError("add-error action requires: --error")
            BackendObservability.warning(
                f"Logging run error for trace-id={args.trace_id}: {args.error}",
                conversation_id=args.trace_id,
            )
            add_error(
                error_message=args.error,
                tracker_path=tracker_path,
            )
            print('{"added_error": true}')

        elif args.action == "generate-report":
            BackendObservability.info(
                f"Compiling final markdown report from {tracker_path} for trace-id={args.trace_id}",
                conversation_id=args.trace_id,
            )
            report_path = generate_report(
                tracker_path=tracker_path,
                template_path=args.template_file,
                logs_dir=args.logs_dir,
                suburbs_path=args.suburbs_file,
            )
            BackendObservability.info(
                f"Successfully compiled report at {report_path}",
                conversation_id=args.trace_id,
            )
            print(f'{{"report_generated": true, "report_file": "{report_path}"}}')

    except Exception as e:
        BackendObservability.fatal(
            f"Failed during tracker action={args.action}: {e}",
            exception=e,
            conversation_id=args.trace_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
