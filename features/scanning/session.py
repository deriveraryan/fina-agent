"""Module to manage session caching and sequential search template rotation.

This module provides utility functions to load, increment/rotate, and save
search template indices for the Fina new listing web finder subagent.
"""

import json
import os
from typing import Dict, Any


def load_session_indices(session_path: str) -> Dict[str, Any]:
    """Load the session state file containing last used template indices.

    If the file does not exist or is invalid JSON, returns an empty dictionary.

    Args:
        session_path: The absolute path to the session JSON file.

    Returns:
        A dictionary containing the parsed session structure.
    """
    if not os.path.exists(session_path):
        return {}

    try:
        with open(session_path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return {}
            return json.loads(data)
    except (json.JSONDecodeError, IOError):
        # Gracefully fallback on corrupt files or read errors
        return {}


def save_session_indices(session_path: str, session_data: Dict[str, Any]) -> None:
    """Save the session data structure to the session state file.

    Creates parent directories if they do not exist.

    Args:
        session_path: The absolute path to the session JSON file.
        session_data: The session structure to serialize.
    """
    os.makedirs(os.path.dirname(session_path), exist_ok=True)
    with open(session_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False)


def get_and_rotate_template(
    city: str,
    category: str,
    categories_path: str,
    session_path: str,
) -> Dict[str, Any]:
    """Select the next search template sequentially for a city and category.

    Loads the available templates from categories.json, determines the next
    index based on the cached session state, writes the updated index back
    to the session cache, and returns the selected template details.

    Args:
        city: The name of the city (e.g. "Sydney").
        category: The canonical category (e.g. "RESTAURANT").
        categories_path: The path to data/categories.json.
        session_path: The path to .antigravity_saves/web_finder_session.json.

    Returns:
        A dictionary containing:
            - "index": The selected template index (int).
            - "template": The raw search template string (str).
            - "formatted_query": The template formatted with the city name (str).
            - "total": The total number of search templates for this category (int).

    Raises:
        ValueError: If categories_path does not exist, the category is invalid,
                    or no templates are defined.
    """
    if not os.path.exists(categories_path):
        raise ValueError(f"Categories file not found at {categories_path}")

    with open(categories_path, "r", encoding="utf-8") as f:
        categories_data = json.load(f)

    category_key = category.upper().strip()
    if category_key not in categories_data:
        raise ValueError(f"Category '{category_key}' is not defined in categories.json")

    category_cfg = categories_data[category_key]
    templates = category_cfg.get("searchTemplates", [])
    if not templates:
        raise ValueError(f"No searchTemplates defined for category '{category_key}'")

    city_key = city.lower().strip()
    session_data = load_session_indices(session_path)

    # Resolve last index
    last_indices = session_data.get("last_used_template_indices", {})
    city_indices = last_indices.get(city_key, {})
    last_index = city_indices.get(category_key, -1)

    # Determine new index with bounds protection
    if not isinstance(last_index, int) or last_index < 0 or last_index >= len(templates):
        new_index = 0
    else:
        new_index = (last_index + 1) % len(templates)

    # Update session data structure
    if "last_used_template_indices" not in session_data:
        session_data["last_used_template_indices"] = {}
    if city_key not in session_data["last_used_template_indices"]:
        session_data["last_used_template_indices"][city_key] = {}

    session_data["last_used_template_indices"][city_key][category_key] = new_index
    save_session_indices(session_path, session_data)

    template_str = templates[new_index]
    formatted_query = template_str.replace("{city}", city.strip())

    return {
        "index": new_index,
        "template": template_str,
        "formatted_query": formatted_query,
        "total": len(templates),
    }
