# Fina Agent Memory

> Self-evolving shared memory for Fina discovery and enrichment agents.
> Agents read this file at session start and update it post-execution.
> Maximum budget: **500 lines**. Agents must aggressively prune stale entries.
> Supersession rule: new insights that contradict existing entries replace them.
> Format: concise bullet points (one line per insight). No prose paragraphs.

## Platform & Browser Insights
<!-- Reusable facts about platforms, anti-bot patterns, and browser behaviour -->
- Google Maps `evaluate_script` requires arrow function syntax `() => expr` (not bare expressions or statements with semicolons).
- Active page focus can change dynamically if other agent sessions are running in parallel; verify selection or re-select the target page context via select_page before executing scripts.
- Google Maps search for a brand name with no local pin may redirect/zoom to coordinates in the Philippines; verify the location or search for the specific street address to confirm.
- Google Maps search query for a suburb name shared across states (e.g. Epping in NSW and VIC) can return results from the wrong state; verify state/coordinates to filter out-of-bounds candidates.
- Google Maps search query with a single dominant result redirects directly to its detail panel, bypassing the search results list.

## Discovery Patterns
<!-- What works and what doesn't when searching for Filipino businesses -->
- `search_web` with `site:facebook.com` or `site:instagram.com` for niche suburb queries (e.g. "Filipino cafe in Wentworthville") returns aggregated summaries rather than direct profile URLs — most candidates come from Round 4 (Google Maps browser).
- The Good Filo (Ramsgate/Kogarah) is a Greek bakehouse and Lusinata (Hurstville) is a Portuguese patisserie; neither is Filipino-affiliated.
- Good Luck Bake House (Mount Druitt) is a Chinese bakery (serves cocktail buns, egg tarts, mango sago) and is not Filipino-affiliated.
- Good Luck Plaza Mount Druitt (Mount Druitt) is a Chinese-focused general Asian supermarket and is not Filipino-affiliated.
- ROOTY HILL BAKEHOUSE (Rooty Hill) is a standard Australian/Vietnamese hot bread bakery and is not Filipino-affiliated.
- Family Mart (SYD) (Hoxton Park) is a general convenience/grocery store and is not Filipino-affiliated.
- Mekeni Food (Blacktown) is an alternative name or duplicate listing for Pinoy Station (24 Main St, Blacktown).
- Mack77 Mart (Toongabbie) is a South Asian convenience store and is not Filipino-affiliated.
- LionLamb Cakes (Riverstone) is a home baker specializing in Filipino desserts; it belongs to SERVICES rather than SHOP.
- Rooty Hill Supermarket Butchery (Rooty Hill) is a Pakistani/Afghan grocery and halal butcher; it is not Filipino-affiliated.
- PCS Butchery / PCS Supermarket (Ingleburn) is a Nepali grocery/butcher and is not Filipino-affiliated.
- Kazi's Supermarket (Glenfield) is a Bangladeshi/Indian grocery and halal butcher; it is not Filipino-affiliated.
- Sagarmatha Butchery (Raby) is a Nepalese/South Asian butcher/deli and Prasadi Store (Raby) is an Indian/Nepalese grocery; neither is Filipino-affiliated.
- The Butcher's Pantry (Eagle Vale) is a standard specialty butcher shop and is not Filipino-affiliated.
- Jory's Quality Meats (Rooty Hill) is verified Filipino-affiliated, offering ready-to-BBQ Filipino specialty meats, pork skewers, chicken inasal, and house-made longganisa.
- Marlin Seafood Plumpton (Plumpton) is a general seafood retailer/fish & chip shop and is not Filipino-affiliated.
- Fresh Seafood Market and Tropical Taste Market (both Rooty Hill) are non-Filipino (seafood and Fiji Indian/island grocer respectively).

## Enrichment Patterns
<!-- Techniques and observations from the listing enrichment workflow -->

## Events Patterns
<!-- Event discovery insights: date parsing quirks, platform event formats, classification edge cases -->

## City Intelligence
<!-- City-specific operational knowledge: aggregate geographic patterns, novel discoveries, high-yield zones -->
- SYDNEY CAFE/SHOP: All 60 suburbs for CAFE and SHOP categories are fully saturated at the city-level task tier. Filipino food/retail businesses are heavily concentrated in Western Sydney (Blacktown, Rooty Hill, Doonside, Mount Druitt, Fairfield, Parramatta corridor) with secondary clusters in South-West (Campbelltown, Ingleburn, Liverpool).
- SYDNEY Eastern/Northern coastal suburbs (Bondi Junction, Manly, Cronulla, North Sydney, Macquarie Park, Sydney Olympic Park) have zero local Filipino storefronts — Maps results always expand to Western Sydney duplicates.
- SYDNEY novel discovery: Auburn SHOP search discovered Supersave Convenience Store in nearby Berala.
- SYDNEY novel discovery: Blacktown CAFE search yielded 2 new operational listings; SHOP search discovered Karnehan Blacktown (Filipino butcher shop).
- SYDNEY novel discovery: Hurstville SHOP search created Lovely Variety Store as an online-only Filipino shop.
- SYDNEY novel discovery: Bondi Junction SHOP fish market search discovered Mabuhey App (online Filipino grocery, located in Haymarket) via Maps search radius expansion.
- SYDNEY novel discovery: Castle Hill CAFE search discovered Hanmades Bakehouse Windsor in surrounding western suburbs.
- SYDNEY novel discovery: PanaDarna (Filipino bakery) is located inside The Kamayan in Rooty Hill — a hidden-within-another-business pattern.
- SYDNEY novel discovery: Prestons SHOP search discovered Tapsi Supermarket, a new operational Filipino grocery store.
- SYDNEY: Kapamilya Asian Groceries (Campbelltown) has cancelled its ABN as of 2025 — confirmed permanently closed.
- SYDNEY: Halal butcheries in Western Sydney (Guildford, Fairfield Heights, Mount Druitt, Quakers Hill) consistently yield non-Filipino results — dominated by Middle Eastern/Pakistani/Afghan halal butchers.
- SYDNEY: Fish market searches across all suburbs consistently yield only non-Filipino seafood stores and duplicates from other suburbs — this search template has near-zero yield for new Filipino listings.

## Known Pitfalls
<!-- Failure modes, validation errors, and how to avoid them -->
- City Casing Case-Sensitivity: Firebase SQL Connect queries are case-sensitive (e.g. `city: { eq: "SYDNEY" }`). Any listings created or restored with capitalized or lowercase city names (e.g., `Sydney` or `sydney`) will be hidden from client browse/search results. Ad-hoc scripts and ingestion agents must always normalize city values to uppercase (as defined in the frontend's City enum).
- Listing ID Drift: Re-creating listings from backup generates new database UUIDs. Any external files or trackers referencing the old listing IDs will become obsolete and must be regenerated or updated.
- The existing city listings cache JSON file is written as a single line, making simple grep query matches prone to truncation or failure; always use the dedicated duplicate check script.
- The `agent_check_duplicate.py` script will skip name-based duplicate matches if any URL is passed to `--url` but the cached listing has no social URLs (all null); omit `--url` or use specific parameters (e.g. `--facebook-url`) to enable name-matching and merge detection.
- The GraphQL UpdateListingData mutation expects tags as a comma-separated String, not a list, whereas CreateListing automatically normalizes a list of tags.
- The name normalization function does not replace curly apostrophes (') with straight apostrophes ('), meaning duplicate checks (e.g. for Tita's Cakes vs Tita's Cakes) will fail unless inputs are normalized first.
- The Google Maps detail panel may render operating hours with day names and times on separate lines, causing `parse_maps_opening_hours` to return `None`; clean the text to 'Day: Hours' format before parsing.
- The GraphQL CreateListing and UpdateListingData mutations expect `operatingHours` as a serialized JSON String, not a JSON object/map; passing a raw dictionary will trigger a GraphQL INVALID_ARGUMENT execution error.
- The GraphQL CreateListing mutation requires a non-empty `description` string; omitting it or setting it to null will trigger an `INVALID_ARGUMENT: $description (String) is missing` execution error.
- The `agent_check_duplicate.py` name matching is highly sensitive to naming variations; Google Maps results containing descriptive suffixes (e.g., "The Bangketa Grocer - Filipino shop" vs "The Bangketa Grocer") will fail to match, so you should check with the base/shortened name if duplicate checks fail.
