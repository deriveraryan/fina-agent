"""Centralized heuristic filtering rules to exclude false positives."""

import re
from typing import Any
from features.shared.observability import BackendObservability

# Known generic chains or false positives to exclude
BLOCKLIST_REGEX = re.compile(
    r"\b(coles|woolworths|woolies|aldi|iga|kmart|target|bunnings|mcdonalds|mcdonald's|kfc|hungry jack's|hungry jacks|domino's|dominos|subway|7-eleven|seven eleven|officeworks|big w)\b",
    re.IGNORECASE
)

def should_exclude_listing(listing_data: dict[str, Any]) -> bool:
    """Evaluates if a listing should be excluded based on heuristic blocklists.
    
    Checks the listing's name against a predefined set of major chain names and 
    irrelevant keywords. Returns True if the listing should be excluded.
    """
    name = listing_data.get("name", "")
    
    if not name or not isinstance(name, str):
        return False
        
    if BLOCKLIST_REGEX.search(name):
        BackendObservability.info(f"Heuristics excluded listing: '{name}' matches blocklist.")
        return True
        
    return False
