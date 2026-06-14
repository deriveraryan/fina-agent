import unittest
from features.scanning.heuristics import should_exclude_listing, verify_filipino_affiliation

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


class TestFilipinoAffiliation(unittest.TestCase):
    def test_authentic_filipino_keywords(self):
        # Name-based checks
        self.assertTrue(verify_filipino_affiliation("Manila Sunset Diner"))
        self.assertTrue(verify_filipino_affiliation("Lolas Island Shop"))
        self.assertTrue(verify_filipino_affiliation("Pinoy Grill N Chill"))
        self.assertTrue(verify_filipino_affiliation("My Lola's Table"))
        
        # Culinary signals
        self.assertTrue(verify_filipino_affiliation("Kanto Bagnet"))
        self.assertTrue(verify_filipino_affiliation("Cucina de Manila", reviews=[{"text": "amazing tapsilog!"}]))
        self.assertTrue(verify_filipino_affiliation("Test Place", reviews=[{"text": "The longsilog was delicious"}]))
        self.assertTrue(verify_filipino_affiliation("Burger Point", reviews=[{"text": "Get their ube shake and pancit #BidaAngSarap!"}]))
        
        # Linguistic signals
        self.assertTrue(verify_filipino_affiliation("Filo Place", reviews=[{"text": "masarap and authentic"}]))
        self.assertTrue(verify_filipino_affiliation("Cafe", reviews=[{"text": "salamat po, will come again"}]))
        self.assertTrue(verify_filipino_affiliation("Tagalog Groceries"))
        self.assertTrue(verify_filipino_affiliation("Halo-Halo Desserts"))
        self.assertTrue(verify_filipino_affiliation("Sari-Sari Store"))
        self.assertTrue(verify_filipino_affiliation("Lola's Cafe", reviews=[{"text": "They serve halo halo and sari sari items"}]))

    def test_false_positives_rejection(self):
        # Tapas/salami substring collision
        self.assertFalse(verify_filipino_affiliation("Bar Una Más", description="Spanish tapas beach bar", reviews=[{"text": "Great Spanish tapas and sangria."}]))
        self.assertFalse(verify_filipino_affiliation("La Disfida Haberfield", reviews=[{"text": "Great pizza, got the mushroom and salami."}]))
        self.assertFalse(verify_filipino_affiliation("Cove Bar Grill", reviews=[{"text": "The chicken was a bit dry."}]))
        self.assertFalse(verify_filipino_affiliation("Kipling's Garage Bar", description="Inventive tapas plates and craft beer."))
        
        # General non-Filipino terms
        self.assertFalse(verify_filipino_affiliation("Lululemon Athletica"))
        self.assertFalse(verify_filipino_affiliation("Laminate Flooring Co"))

