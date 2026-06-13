#!/usr/bin/env python3
"""CLI agent script to manage web finder session search template rotation."""
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
from features.scanning.session import get_and_rotate_template


def main() -> None:
    """CLI script entrypoint."""
    parser = argparse.ArgumentParser(
        description="Retrieve the next sequential search template from categories.json and rotate the session index."
    )
    parser.add_argument("--city", type=str, required=True, help="Target city (e.g. Sydney).")
    parser.add_argument("--category", type=str, required=True, help="Canonical category (e.g. RESTAURANT).")
    parser.add_argument("--trace-id", type=str, default=None, help="Trace correlation ID.")
    parser.add_argument(
        "--categories-file",
        type=str,
        default="data/categories.json",
        help="Path to categories.json file.",
    )
    parser.add_argument(
        "--session-file",
        type=str,
        default=".antigravity_saves/web_finder_session.json",
        help="Path to session json file.",
    )

    args = parser.parse_args()

    BackendObservability.info(
        f"Retrieving and rotating web finder template for city={args.city}, category={args.category}",
        conversation_id=args.trace_id,
    )

    try:
        result = get_and_rotate_template(
            city=args.city,
            category=args.category,
            categories_path=args.categories_file,
            session_path=args.session_file,
        )

        BackendObservability.info(
            f"Successfully rotated template. Index: {result['index']}, Query: '{result['formatted_query']}'",
            conversation_id=args.trace_id,
        )

        # Print JSON output directly to stdout for LLM consumption
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        BackendObservability.fatal(
            f"Failed to rotate template session: {e}",
            exception=e,
            conversation_id=args.trace_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
