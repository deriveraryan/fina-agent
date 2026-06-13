"""Centralized heuristic filtering rules to exclude false positives."""

import re
from typing import Any
from features.shared.observability import BackendObservability

# Comprehensive list of generic chains/false positives to exclude
BLOCKLIST_CHAINS = [
    # Supermarkets, Groceries & Retailers
    "Woolworths", "Coles", "Aldi", "IGA", "Foodworks", "Supabarn", 
    "Harris Farm Markets", "Drakes Supermarkets", "Spudshed", "Woolies",
    "Kmart", "Target", "Big W", "Myer", "David Jones", "Costco", "The Reject Shop", "Reject Shop",
    
    # Fast Food, Cafes & Restaurants
    "McDonald's", "McDonalds", "KFC", "Hungry Jack's", "Hungry Jacks", 
    "Subway", "Domino's", "Domino's Pizza", "Dominos", "Red Rooster", 
    "Oporto", "Pizza Hut", "Grill'd", "Grilld", "Zambrero", "Guzman y Gomez", 
    "GYG", "Nando's", "Nandos", "Schnitz", "Salsas Fresh Mex", "Gloria Jean's", 
    "Gloria Jeans", "The Coffee Club", "Muffin Break", "Boost Juice", 
    "Betty's Burgers", "Bettys Burgers", "Hog's Breath Cafe", "Hogs Breath Cafe", 
    "Oliver's Real Food", "Olivers Real Food", "Bakers Delight", "Brumby's", 
    "Brumbys", "Donut King", "Michel's Patisserie", "Starbucks", "Pie Face", 
    "Crust Pizza", "Crust", "Mad Mex", "Roll'd", "Rolld", "Soul Origin", 
    "Chicken Treat", "El Jannah", "Zarraffa's Coffee",
    
    # Pharmacies & Health/Beauty
    "Chemist Warehouse", "Priceline", "Priceline Pharmacy", "TerryWhite Chemmart", 
    "Amcal", "Just Cuts", "Hairhouse", "Laser Clinics Australia",
    
    # Hardware, Auto & Homeware
    "Bunnings", "Bunnings Warehouse", "Mitre 10", "Home Timber & Hardware", 
    "Total Tools", "Sydney Tools", "JB Hi-Fi", "JB HiFi", "Harvey Norman", 
    "The Good Guys", "Officeworks", "Supercheap Auto", "Repco", "Autobarn", 
    "BCF", "Anaconda", "Spotlight", "Kathmandu", "Adairs",
    "Robins Kitchen", "Bed Bath N' Table", "Bed Bath N Table", "Sheridan", 
    "IKEA", "Fantastic Furniture", "Amart Furniture", "Freedom", "Snooze", 
    "Forty Winks", "Pillow Talk", "Dusk", "TK Maxx",
    
    # Apparel, Shoes & Accessories
    "Rebel Sport", "Rebel", "Cotton On", "Cotton On Body", "Supré", "Supre", 
    "Factorie", "Jay Jays", "Just Jeans", "Dotti", "Portmans", "Jacqui E", 
    "Peter Alexander", "Country Road", "Witchery", "Mimco", "Seed Heritage", 
    "Sportsgirl", "Sussan", "Suzanne Grae", "Rivers", "Best & Less", 
    "Best and Less", "Connor", "Tarocash", "yd.", "Johnny Bigg", "Rockwear", 
    "Platypus Shoes", "Hype DC", "The Athlete's Foot", "Skechers", "Lovisa", 
    "Strandbags",
    
    # Petrol & Convenience
    "7-Eleven", "7 Eleven", "Ampol", "BP", "Shell", "Coles Express", 
    "Woolworths Metro", "EG Ampol", "EG Australia", "United Petroleum", 
    "Mobil", "Liberty Oil", "Caltex", "Puma Energy", "NightOwl", "EziMart",
    
    # Liquor Stores
    "Dan Murphy's", "Dan Murphys", "BWS", "Liquorland", "Vintage Cellars", 
    "First Choice Liquor", "First Choice Liquor Market", "Cellarbrations", 
    "The Bottle-O", "Bottle-O", "Thirsty Camel", "Liquor Stax", "Local Liquor",
    
    # Banking & Financial Services
    "Commonwealth Bank", "CBA", "Westpac", "ANZ", "National Australia Bank", 
    "NAB", "Bendigo Bank", "Suncorp", "Bank of Queensland", "BOQ", 
    "St George Bank", "Macquarie Bank",
    
    # Services, Gyms & Entertainment
    "Australia Post", "AusPost", "Anytime Fitness", "Jetts", "Plus Fitness", 
    "F45", "Snap Fitness", "Goodlife Health Clubs", "Fitness First", 
    "mycar", "mycar Tyre & Auto", "Bob Jane T-Marts", "Bob Jane", "JAX Tyres", 
    "Tyrepower", "Bridgestone Select", "Flight Centre", "Helloworld", 
    "Event Cinemas", "Hoyts", "Village Cinemas", "Timezone", "Petbarn", 
    "Petstock", "EB Games", "Zing Pop Culture", "Toyworld", "Dymocks", "QBD Books"
]

# Compile list sorted by length descending to match longer patterns first (e.g. Bunnings Warehouse before Bunnings)
BLOCKLIST_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in sorted(BLOCKLIST_CHAINS, key=len, reverse=True)) + r")\b",
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


def verify_filipino_affiliation(name: str, description: str = "", reviews: list = None) -> bool:
    """Verifies authentic Filipino affiliation by checking text context for linguistic and culinary signals.
    
    Uses robust tokenization, trailing plural/possessive suffix stripping, and categorized
    keyword matches to prevent substring collision errors (e.g. matching 'lami' in 'salami' or
    'tapa' in 'tapas').
    """
    if not name:
        return False
        
    # Standardize and combine all text fields to search
    text_parts = [name, description or ""]
    if reviews:
        for r in reviews:
            if isinstance(r, dict):
                text_parts.append(r.get("text", ""))
            elif isinstance(r, str):
                text_parts.append(r)
                
    full_text = " ".join(text_parts).lower()
    
    # Split text into word tokens (alphabetic only to handle hashtags, punctuation, etc.)
    words = re.findall(r'[a-z]+', full_text)
    
    # Keyword sets
    high_collision = {"lami", "tapa"}
    low_collision = {
        "masarap", "sarap", "salamat", "kabayan", "mabuhay", 
        "adobo", "sinigang", "lechon", "sisig", "pancit", "lumpia", 
        "halohalo", "caldereta", "bagnet", "tocino", "pandesal",
        "filipino", "pinoy", "manila", "lola", "bahay"
    }
    
    for word in words:
        # Check low-collision compound/suffix matches first (e.g. #BidaAngSarap or tapsilog)
        if "sarap" in word or "silog" in word or "halohalo" in word or "halo-halo" in word:
            return True
            
        # Clean possessives and plurals for standard words
        clean_word = word
        if clean_word.endswith("s"):
            if clean_word != "tapas":
                clean_word = clean_word[:-1]
                
        # Match against low-collision keywords
        if clean_word in low_collision:
            return True
            
        # Match against high-collision keywords (strict exact match only)
        if word in high_collision:
            return True
            
    return False

