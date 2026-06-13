"""Module to manage deterministic tracking and programmatic report generation.

Provides utility functions to initialize tracking sessions, log search actions,
record candidate evaluations, and format final markdown status reports.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


def load_tracker_data(tracker_path: str) -> Dict[str, Any]:
    """Load the current tracking state from a JSON file.

    Args:
        tracker_path: Absolute path to the tracker JSON file.

    Returns:
        A dictionary containing the tracker state.
    """
    if not os.path.exists(tracker_path):
        return {}
    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return {}
            return json.loads(data)
    except (json.JSONDecodeError, IOError):
        return {}


def save_tracker_data(tracker_path: str, data: Dict[str, Any]) -> None:
    """Save the tracker state to a JSON file.

    Args:
        tracker_path: Absolute path to the tracker JSON file.
        data: The tracker data dictionary.
    """
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    with open(tracker_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def init_tracker(
    city: str,
    category: str,
    template_index: int,
    template_string: str,
    formatted_query: str,
    trace_id: str,
    tracker_path: str,
) -> None:
    """Initialize a tracking session state file.

    Args:
        city: Target city name (e.g. "Sydney").
        category: Canonical category (e.g. "RESTAURANT").
        template_index: Selected search template index.
        template_string: Raw template string.
        formatted_query: Formatted search template query.
        trace_id: Trace correlation ID.
        tracker_path: Path to write the JSON session file to.
    """
    execution_date = datetime.now().strftime("%Y-%m-%d %I:%M %p AEST")
    state: Dict[str, Any] = {
        "city": city,
        "category": category,
        "search_template_index": template_index,
        "search_template_string": template_string,
        "formatted_query": formatted_query,
        "execution_date": execution_date,
        "trace_id": trace_id,
        "searches": [],
        "candidates": [],
        "errors": [],
    }
    save_tracker_data(tracker_path, state)


def add_search(
    query: str,
    platform: str,
    pages_read: int,
    tracker_path: str,
    suburbs_path: str = "data/top_suburbs_per_city.json",
) -> None:
    """Record a web search action and pages read count.

    Automatically detects if a suburb from the city's suburb list is part of the query.

    Args:
        query: The search term or query string executed.
        platform: Platform type (Facebook, Instagram, General Web, etc.).
        pages_read: Number of result pages read or inspected during this search.
        tracker_path: Path to the tracker JSON file.
        suburbs_path: Path to the top_suburbs_per_city.json file.
    """
    data = load_tracker_data(tracker_path)
    if not data:
        raise ValueError(f"Tracker state not initialized or missing at {tracker_path}")

    city = data.get("city", "")
    matched_suburb = None

    if city and os.path.exists(suburbs_path):
        try:
            with open(suburbs_path, "r", encoding="utf-8") as sf:
                suburbs_map = json.load(sf)
            city_key = city.lower().strip()
            city_suburbs = suburbs_map.get(city_key, [])
            query_lower = query.lower()
            # Match case-insensitively, prioritize matching longer names first if any overlap
            for suburb in sorted(city_suburbs, key=len, reverse=True):
                if suburb.lower() in query_lower:
                    matched_suburb = suburb
                    break
        except Exception:
            pass

    search_record = {
        "query": query,
        "platform": platform,
        "pages_read": pages_read,
        "suburb": matched_suburb,
    }
    data.setdefault("searches", []).append(search_record)
    save_tracker_data(tracker_path, data)


def add_candidate(
    name: str,
    url: str,
    platform: str,
    status: str,
    reason: str,
    db_id: Optional[str] = None,
    address: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    category: Optional[str] = None,
    tracker_path: str = "",
) -> None:
    """Record a page or candidate listing evaluation.

    Args:
        name: Name of candidate listing.
        url: Profile URL or website.
        platform: Social/Web platform.
        status: Evaluation status (CREATED, DUPLICATE, REJECTED, ERROR).
        reason: Justification or status notes.
        db_id: Database listing UUID if created.
        address: Extracted address of the place.
        description: Description of the business.
        tags: Comma-separated tag list.
        category: Listing category.
        tracker_path: Path to the tracker JSON file.
    """
    data = load_tracker_data(tracker_path)
    if not data:
        raise ValueError(f"Tracker state not initialized or missing at {tracker_path}")

    normalized_status = status.upper().strip()
    if normalized_status not in ("CREATED", "DUPLICATE", "REJECTED", "ERROR"):
        raise ValueError(f"Invalid candidate status: '{status}'. Must be CREATED, DUPLICATE, REJECTED, or ERROR.")

    candidate_record = {
        "name": name,
        "url": url,
        "platform": platform,
        "status": normalized_status,
        "reason": reason,
        "db_id": db_id,
        "address": address,
        "description": description,
        "tags": tags,
        "category": category,
    }
    data.setdefault("candidates", []).append(candidate_record)
    save_tracker_data(tracker_path, data)


def add_error(error_message: str, tracker_path: str) -> None:
    """Log an operational error or warning message during the run.

    Args:
        error_message: Error or warning description.
        tracker_path: Path to the tracker JSON file.
    """
    data = load_tracker_data(tracker_path)
    if not data:
        raise ValueError(f"Tracker state not initialized or missing at {tracker_path}")

    data.setdefault("errors", []).append(error_message)
    save_tracker_data(tracker_path, data)


def generate_report(
    tracker_path: str,
    template_path: str,
    logs_dir: str,
    suburbs_path: str = "data/top_suburbs_per_city.json",
) -> str:
    """Compile the final markdown report from the tracker session data.

    Reads the template, calculates aggregates, structures table elements,
    and writes the report into the daily logs folder.

    Args:
        tracker_path: Path to the tracker JSON file.
        template_path: Path to REPORT_TEMPLATE.md.
        logs_dir: Output root logs folder.
        suburbs_path: Path to the top_suburbs_per_city.json file.

    Returns:
        The absolute path to the generated markdown report file.
    """
    data = load_tracker_data(tracker_path)
    if not data:
        raise ValueError(f"Tracker state not initialized or missing at {tracker_path}")

    if not os.path.exists(template_path):
        raise ValueError(f"Report template not found at {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    searches: List[Dict[str, Any]] = data.get("searches", [])
    candidates: List[Dict[str, Any]] = data.get("candidates", [])
    errors: List[str] = data.get("errors", [])

    # Calculate metrics
    web_searches_made = len(searches)
    total_pages_read = sum(s.get("pages_read", 0) for s in searches)
    total_candidates = len(candidates)
    listings_created = sum(1 for c in candidates if c.get("status") == "CREATED")
    candidates_rejected = sum(1 for c in candidates if c.get("status") in ("REJECTED", "DUPLICATE"))
    errors_count = len(errors)

    # Suburbs metrics
    unique_suburbs = sorted(list(set(
        s.get("suburb") for s in searches if s.get("suburb")
    )))
    search_suburbs_str = ", ".join(unique_suburbs) if unique_suburbs else "None"
    total_suburbs_searched = len(unique_suburbs)

    # Derive unique platforms searched
    unique_platforms = sorted(list(
        set(s.get("platform", "") for s in searches) |
        set(c.get("platform", "") for c in candidates)
    ))
    unique_platforms = [p for p in unique_platforms if p]
    platforms_str = ", ".join(unique_platforms) if unique_platforms else "Facebook, Instagram, General Web"

    # Group and sort Created Listings
    created_listings = [c for c in candidates if c.get("status") == "CREATED"]
    grouped_created: Dict[str, List[Dict[str, Any]]] = {}
    for listing in created_listings:
        cat = (listing.get("category") or data.get("category") or "UNKNOWN").upper().strip()
        grouped_created.setdefault(cat, []).append(listing)

    platform_priority = {"Facebook": 0, "Instagram": 1, "General Web": 2}

    def sort_key(listing: Dict[str, Any]) -> Any:
        plat = listing.get("platform") or ""
        name = listing.get("name") or ""
        return (platform_priority.get(plat, 99), name.lower())

    created_md_blocks = []
    for cat in sorted(grouped_created.keys()):
        created_md_blocks.append(f"#### {cat}\n")
        sorted_listings = sorted(grouped_created[cat], key=sort_key)
        for idx, listing in enumerate(sorted_listings, 1):
            plat = listing.get("platform") or "Web"
            name = listing.get("name") or "Unnamed"
            addr = listing.get("address") or "Online-only — city center coordinates"
            desc = listing.get("description") or "No description provided."
            url = listing.get("url") or ""
            db_id = listing.get("db_id") or "null"
            tags = listing.get("tags") or "google-search"
            cat_label = listing.get("category") or cat

            block = (
                f"{idx}. **{name}** ({plat})\n"
                f"   - Category: {cat_label}\n"
                f"   - Address: {addr}\n"
                f"   - Description: {desc}\n"
                f"   - Social URL: {url}\n"
                f"   - DB ID: `{db_id}`\n"
                f"   - Tags: {tags}"
            )
            created_md_blocks.append(block)

    created_listings_md = "\n\n".join(created_md_blocks) if created_md_blocks else "None created."

    # Build Skipped / Rejected Candidates table
    rejected_candidates = [c for c in candidates if c.get("status") in ("REJECTED", "DUPLICATE")]
    rejected_rows = [
        "| Candidate Name | Platform | Reason |",
        "| :--- | :--- | :--- |"
    ]
    for c in rejected_candidates:
        name = c.get("name") or "Unnamed"
        plat = c.get("platform") or "Web"
        reason = c.get("reason") or "No reason provided"
        rejected_rows.append(f"| {name} | {plat} | {reason} |")

    if len(rejected_candidates) == 0:
        rejected_rows.append("| None | None | No candidates skipped or rejected |")

    rejected_table_md = "\n".join(rejected_rows)

    # Build Search Log Details table
    log_rows = [
        "| Search Query | Platform | Pages Read | Location / Suburb |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for s in searches:
        query_val = s.get("query") or "None"
        plat_val = s.get("platform") or "Web"
        pages_val = s.get("pages_read") or 0
        suburb_val = s.get("suburb") or "None"
        log_rows.append(f"| {query_val} | {plat_val} | {pages_val} | {suburb_val} |")

    if not searches:
        log_rows.append("| None | None | 0 | None |")

    search_log_details_md = "\n".join(log_rows)

    # Build Errors & Warnings list
    if errors:
        errors_md = "\n".join(f"- {err}" for err in errors)
    else:
        errors_md = "- None encountered."

    # Perform replacements
    replacements = {
        "{CITY}": data.get("city", ""),
        "{PLATFORMS}": platforms_str,
        "{INDEX}": str(data.get("search_template_index", 0)),
        "{TEMPLATE_STRING}": data.get("search_template_string", ""),
        "{FORMATTED_QUERY}": data.get("formatted_query", ""),
        "{EXECUTION_DATE}": data.get("execution_date", ""),
        "{TRACE_ID}": data.get("trace_id", ""),
        "{SEARCH_SUBURBS}": search_suburbs_str,
        "{WEB_SEARCHES_MADE}": str(web_searches_made),
        "{TOTAL_PAGES_READ}": str(total_pages_read),
        "{CANDIDATES_EVALUATED}": str(total_candidates),
        "{LISTINGS_CREATED}": str(listings_created),
        "{CANDIDATES_REJECTED}": str(candidates_rejected),
        "{TOTAL_SUBURBS_SEARCHED}": str(total_suburbs_searched),
        "{ERRORS_ENCOUNTERED}": str(errors_count),
        "{CREATED_LISTINGS}": created_listings_md,
        "{REJECTED_TABLE}": rejected_table_md,
        "{SEARCH_LOG_DETAILS}": search_log_details_md,
        "{ERRORS_LIST}": errors_md,
    }

    report_content = template_content
    for placeholder, val in replacements.items():
        report_content = report_content.replace(placeholder, val)

    now = datetime.now()
    yyyymmdd = now.strftime("%Y%m%d")
    hhmm = now.strftime("%H%M")
    city_normalized = data.get("city", "").replace(" ", "_")
    category_normalized = data.get("category", "").upper().strip()

    output_dir = os.path.join(logs_dir, yyyymmdd)
    os.makedirs(output_dir, exist_ok=True)

    report_filename = f"fina_new_listing_web_finder_report_{city_normalized}_{category_normalized}_{yyyymmdd}_{hhmm}.md"
    report_path = os.path.join(output_dir, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    # Clean up temporary session JSON on successful report generation
    try:
        if os.path.exists(tracker_path):
            os.remove(tracker_path)
    except OSError:
        pass

    return report_path
