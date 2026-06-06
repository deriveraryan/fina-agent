import unittest
from features.scanning.heuristics import should_exclude_listing

class TestHeuristics(unittest.TestCase):
    def test_should_exclude_major_chains(self):
        chains = [
            "Coles Supermarket",
            "Woolworths Metro",
            "woolies",
            "McDonald's Sydney",
            "Mcdonalds",
            "KFC",
            "Hungry Jack's",
            "Bunnings Warehouse",
            "Target Centre",
            "Kmart",
            "Aldi",
            "IGA",
            "Subway"
        ]
        for name in chains:
            self.assertTrue(
                should_exclude_listing({"name": name}),
                f"Failed to exclude known chain: {name}"
            )
            
    def test_should_allow_authentic_places(self):
        authentic = [
            "Mabuhay Market",
            "Sydney Filipino Society",
            "Lolo and Lola",
            "Manila Cafe",
            "St Mary's Church", # Make sure St Mary's isn't blocked by 'Kmart' logic etc
            "Pinoy Grocer"
        ]
        for name in authentic:
            self.assertFalse(
                should_exclude_listing({"name": name}),
                f"Incorrectly excluded authentic place: {name}"
            )

    def test_empty_or_invalid_names(self):
        self.assertFalse(should_exclude_listing({}))
        self.assertFalse(should_exclude_listing({"name": ""}))
        self.assertFalse(should_exclude_listing({"name": None}))
