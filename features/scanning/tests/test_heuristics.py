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
            "Subway",
            # New blocklist categories
            "Ray White Parramatta",
            "LJ Hooker Melbourne",
            "Chatime Chatswood",
            "Gong Cha Sydney",
            "Telstra Store",
            "Specsavers Westfield",
            "San Churro",
            "Taco Bell Penrith",
            "Harris Scarfe",
            "Bottlemart",
            "Crunch Fitness",
            "Fernwood Fitness",
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
        self.assertTrue(verify_filipino_affiliation("Pinoy Grill N Chill"))
        self.assertTrue(verify_filipino_affiliation("My Lola's Table"))  # Exact token 'lola' matches high-collision
        
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
    
    def test_new_compound_phrases(self):
        """Compound phrases added for modern Fil-Aus dining and cultural concepts."""
        self.assertTrue(verify_filipino_affiliation("Kamayan Feast", description="Boodle fight style dining"))
        self.assertTrue(verify_filipino_affiliation("Nanay's Kitchen", description="Authentic turo-turo eatery"))
        self.assertTrue(verify_filipino_affiliation("Kare-Kare House"))
        self.assertTrue(verify_filipino_affiliation("Best Turo Turo in Sydney"))
        self.assertTrue(verify_filipino_affiliation("Kare Kare and Sinigang"))
    
    def test_new_low_collision_keywords(self):
        """Diaspora logistics, dining, and cultural terms unique to Filipino context."""
        self.assertTrue(verify_filipino_affiliation("Balikbayan Box Express"))  # Cargo/logistics
        self.assertTrue(verify_filipino_affiliation("Padala Remittance Centre"))  # Money transfer
        self.assertTrue(verify_filipino_affiliation("Pasalubong Corner"))  # Gift/import shop
        self.assertTrue(verify_filipino_affiliation("Kamayan Kitchen"))  # Feast dining
        self.assertTrue(verify_filipino_affiliation("Dinuguan ni Nanay"))  # Pork blood stew
        self.assertTrue(verify_filipino_affiliation("Chicken Inasal House"))  # Bacolod grilled chicken
        self.assertTrue(verify_filipino_affiliation("Calamansi Cafe"))  # Philippine lime
        self.assertTrue(verify_filipino_affiliation("Fresh Bangus Market"))  # Milkfish
        self.assertTrue(verify_filipino_affiliation("Ate's Carinderia"))  # Filipino eatery
        self.assertTrue(verify_filipino_affiliation("Bayanihan Community Centre"))  # Community spirit
        self.assertTrue(verify_filipino_affiliation("Sinangag Express"))  # Garlic rice
        self.assertTrue(verify_filipino_affiliation("Bagoong Club"))  # Fermented paste
    
    def test_new_high_collision_keywords(self):
        """High-collision terms match only as exact tokens (no suffix stripping)."""
        self.assertTrue(verify_filipino_affiliation("Ube Cheesecake Co"))  # Exact 'ube' token
        self.assertTrue(verify_filipino_affiliation("Longganisa Factory"))  # Exact 'longganisa' token
        self.assertTrue(verify_filipino_affiliation("Chicharon ni Mang Juan"))  # Exact 'chicharon' token
        self.assertTrue(verify_filipino_affiliation("Ensaymada House"))  # Exact 'ensaymada' token

    def test_false_positives_rejection(self):
        # Tapas/salami substring collision
        self.assertFalse(verify_filipino_affiliation("Bar Una Más", description="Spanish tapas beach bar", reviews=[{"text": "Great Spanish tapas and sangria."}]))
        self.assertFalse(verify_filipino_affiliation("La Disfida Haberfield", reviews=[{"text": "Great pizza, got the mushroom and salami."}]))
        self.assertFalse(verify_filipino_affiliation("Cove Bar Grill", reviews=[{"text": "The chicken was a bit dry."}]))
        self.assertFalse(verify_filipino_affiliation("Kipling's Garage Bar", description="Inventive tapas plates and craft beer."))
        
        # General non-Filipino terms
        self.assertFalse(verify_filipino_affiliation("Lululemon Athletica"))
        self.assertFalse(verify_filipino_affiliation("Laminate Flooring Co"))
        
        # Lola as a common non-Filipino cafe name (now high-collision, plurals won't match)
        self.assertFalse(verify_filipino_affiliation("Lolas Bistro"))  # Token 'lolas' ≠ exact 'lola'
        
        # Ube substring safety (should NOT match embedded occurrences)
        self.assertFalse(verify_filipino_affiliation("Uber Eats Delivery"))  # Token 'uber' ≠ 'ube'
        self.assertFalse(verify_filipino_affiliation("Cube Design Studio"))  # Token 'cube' ≠ 'ube'
        self.assertFalse(verify_filipino_affiliation("Tube Station Bar"))  # Token 'tube' ≠ 'ube'

