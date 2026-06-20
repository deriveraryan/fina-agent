"""Module to manage the task-based search state machine for the maps search agent.

Generates all map search task permutations for a city (categories × templates × locations),
defaulting to city-level only. Supports category-level ``cityOnly`` and per-template
``cityOnlySearchTemplateIndices``. Provides maps-specific metric constants and task building.
Lifecycle functions (load, save, start, complete, etc.) are imported from task_lifecycle.
"""

import json
import os
from typing import Any, Dict, List, Set, Sequence


# Maps-specific metric and state field definitions
MAP_SEARCH_ALLOWED_METRICS: Set[str] = {
    "listings_created", "places_fetched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate",
}

MAP_SEARCH_METRIC_FIELDS: Sequence[str] = (
    "listings_created", "places_fetched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate",
)

MAP_SEARCH_MUTABLE_FIELDS: Sequence[str] = (
    "status", "started_at", "completed_at",
    "listings_created", "places_fetched",
    "candidates_evaluated", "candidates_rejected",
    "candidates_duplicate", "errors",
)


def generate_tasks(
    city: str,
    categories_path: str,
    suburbs_path: str,
    include_suburbs: bool = False,
) -> List[Dict[str, Any]]:
    """Generate all map search task permutations for a city.

    Creates one task per (category × template × location) combination.
    By default, only city-level tasks are generated. Suburb-level tasks
    are included when include_suburbs is True.

    Ordering: categories in file order → template index ascending →
    city-level first, then suburbs in list order (when included).

    Args:
        city: Target city name (e.g. "Sydney").
        categories_path: Path to data/categories.json.
        suburbs_path: Path to data/top_suburbs_per_city.json.
        include_suburbs: When True, generates suburb-level tasks in addition
            to city-level tasks. Defaults to False (city-only).

    Returns:
        A list of task dictionaries, each with tracking metadata.

    Raises:
        ValueError: If the city is not defined in the suburbs file,
                    or the categories file is missing/invalid.
    """
    if not os.path.exists(categories_path):
        raise ValueError(f"Categories file not found at {categories_path}")
    if not os.path.exists(suburbs_path):
        raise ValueError(f"Suburbs file not found at {suburbs_path}")

    with open(categories_path, "r", encoding="utf-8") as f:
        categories_data: Dict[str, Any] = json.load(f)

    with open(suburbs_path, "r", encoding="utf-8") as f:
        suburbs_data: Dict[str, List[str]] = json.load(f)

    city_key = city.lower().strip()
    if city_key not in suburbs_data:
        raise ValueError(
            f"City '{city}' is not defined in {suburbs_path}. "
            f"Valid cities: {list(suburbs_data.keys())}"
        )

    city_display = city.strip()
    suburbs = suburbs_data[city_key] if include_suburbs else []

    tasks: List[Dict[str, Any]] = []

    for category_key, category_cfg in categories_data.items():
        templates = category_cfg.get("searchTemplates", [])
        if not templates:
            continue
        city_only = category_cfg.get("cityOnly", False)
        city_only_template_indices: Set[int] = set(
            category_cfg.get("cityOnlySearchTemplateIndices", [])
        )

        # Validate template indices are within bounds
        max_index = len(templates) - 1
        invalid = [i for i in city_only_template_indices if i > max_index]
        if invalid:
            raise ValueError(
                f"Category '{category_key}': cityOnlySearchTemplateIndices "
                f"{invalid} exceed searchTemplates length ({len(templates)})"
            )

        for template_index, template_str in enumerate(templates):
            # City-level task (always generated)
            tasks.append(_build_task(
                city_key=city_key,
                city_display=city_display,
                category=category_key,
                template_index=template_index,
                template=template_str,
                location=city_display,
                location_type="city",
            ))

            if city_only or template_index in city_only_template_indices:
                continue

            # Suburb tasks (only when include_suburbs is True)
            for suburb in suburbs:
                tasks.append(_build_task(
                    city_key=city_key,
                    city_display=city_display,
                    category=category_key,
                    template_index=template_index,
                    template=template_str,
                    location=suburb,
                    location_type="suburb",
                ))

    return tasks


def _build_task(
    city_key: str,
    city_display: str,
    category: str,
    template_index: int,
    template: str,
    location: str,
    location_type: str,
) -> Dict[str, Any]:
    """Build a single maps search task dictionary with all required fields.

    For city-level tasks, the query is formatted as the template with {city}
    replaced by the city name. For suburb tasks, the query is formatted as
    the raw template text (without {city} substitution) + ' in {suburb}, {city}'.

    Args:
        city_key: Lowercased city identifier for the task ID.
        city_display: Display-cased city name.
        category: Canonical category key (e.g. "RESTAURANT").
        template_index: Index of the template in searchTemplates array.
        template: Raw template string (e.g. "Filipino restaurant in {city}").
        location: The location name (city display name or suburb name).
        location_type: Either "city" or "suburb".

    Returns:
        A task dictionary with all tracking fields initialized.
    """
    location_id = location.lower().strip().replace(" ", "_")
    task_id = f"{city_key}__{category}__{template_index}__{location_id}"

    if location_type == "city":
        formatted_query = template.replace("{city}", city_display)
    else:
        base_query = template.replace(" in {city}", "").replace("{city}", "").strip()
        formatted_query = f"{base_query} in {location}, {city_display}"

    return {
        "id": task_id,
        "city": city_display,
        "location": location,
        "location_type": location_type,
        "category": category,
        "template_index": template_index,
        "template": template,
        "formatted_query": formatted_query,
        "status": "PENDING",
        "started_at": None,
        "completed_at": None,
        "listings_created": 0,
        "places_fetched": 0,
        "candidates_evaluated": 0,
        "candidates_rejected": 0,
        "candidates_duplicate": 0,
        "errors": [],
    }
