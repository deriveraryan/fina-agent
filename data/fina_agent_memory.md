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
- Multi-branch organizations or churches (e.g., Jesus Is Lord Church) often share a single national website or regional Facebook page; evaluate physical address and branch name rather than relying solely on URL matches to prevent incorrect duplicate detections.
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
- Sydney church searches containing "Filipino" can return Indonesian churches (e.g., Filadelfia Church / Gereja Indonesia, Ecclesia Mission) as false positives; verify Indonesian terminology ("Gereja") or leadership names to filter out.
- Bread of Life Christian Church (under "1503 Mission Network" in Sydney) is Taiwanese-affiliated (Zhongli branch origin) and is not Filipino-affiliated, despite sharing name similarities with Filipino charismatic groups.
- CCCS (Congregational Christian Church of Samoa) is Samoan-affiliated and is not Filipino-affiliated, serving the Samoan diaspora.
- New Life Sydney Christian Church (Rouse Hill/Toongabbie) is verified Filipino-affiliated, whereas New Life Christian Church (Woodcroft) is a Reformed/non-Filipino-affiliated church, despite their very similar names.
- Good Shepherd Catholic Church (Hoxton Park) is verified Filipino-affiliated, hosting the annual Feast of the Black Nazarene devotion since 1995.
- Holy Family Catholic Church (Ingleburn) is verified Filipino-affiliated, hosting a dedicated monthly Filipino Mass (4th Sunday at 4:30 pm) and Filipino choir.
- Bethel Bible Baptist Church (Ingleburn) is verified Filipino-affiliated, led by a Filipino pastor (Pastor Arellano) with a strong Filipino congregation.
- Pentecostal Christian Assembly (PCA Church) in Ingleburn is Malayalam-speaking and 4C Community Church (Ingleburn) is Chinese-affiliated; neither is Filipino-affiliated.
- Sydwest Asian Christian Church (Cabramatta) is Chinese-affiliated (Mandarin/Cantonese services) and Sydney House of Praise (Lansvale) is Samoan/Pacific Islander-affiliated; neither is Filipino-affiliated.
- General Australian churches listing the Philippines as an overseas missionary/charity destination (e.g. Emmanuel Christian Family Church or Plumpton Community Church) are not Filipino-affiliated unless they host dedicated local services or ministries for the Filipino community.
- Foursquare Gospel Minchinbury (Minchinbury) is the Google Maps label for FCF Life Centre (formerly Filipino Christian Fellowship) and is verified Filipino-affiliated.
- Mary Queen of the Family Parish / St Patrick's Catholic Church (Blacktown) is verified Filipino-affiliated, hosting a monthly Filipino Mass and celebrating the Sinulog festival.
- Our Lady of the Rosary Catholic Cathedral (Waitara/Hornsby) is verified Filipino-affiliated, hosting a monthly Filipino Mass on the 2nd Sunday of the month at 3:30 pm.
- Franciscan Shrine of the Holy Innocents (Kellyville) is part of the Our Lady of the Rosary Parish Kellyville and does not host a separate Filipino Mass; avoid creating it as a separate listing.
- Web search queries combining a local parish name with "Filipino" or "Tagalog" can return false-positive snippets from a different parish of the same dedication in another country (e.g., Walnut Creek, California, for St John Vianney); verify that contact details, domains (e.g., sjvianney.org vs stjohnvianneydoonside.org.au), and addresses belong to the Australian parish before confirming affiliation.






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
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered St. Ezekiel Moreno Convent, The Love of Jesus Christian Ministries, West Sydney Community Church, and Come To Jesus Church as verified Filipino-affiliated congregations.
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered Doonside Anglican Church (St. John's) as a verified Filipino-affiliated congregation (home base for Renew Filipino Ministries).
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered St John Vianney Parish as a verified Filipino-affiliated Catholic parish hosting Tagalog-English bilingual masses and Simbang Gabi.
- SYDNEY novel discovery: Seven Hills/Arndell Park CHURCH search discovered Church of the Living God as a verified Filipino-affiliated congregation.
- SYDNEY novel discovery: Mount Druitt CHURCH search discovered Iglesia ni Cristo Minchinbury, Sacred Heart Catholic Church (Mt Druitt South), and Holy Family Catholic Parish (Mt Druitt) as verified Filipino-affiliated congregations.
- SYDNEY novel discovery: Glenmore Park/Penrith CHURCH search discovered St Nicholas of Myra as a verified Filipino-affiliated Catholic parish hosting the monthly Filipino Mass and Our Lady of Peñafrancia devotions.
- SYDNEY novel discovery: Green Valley/Ashcroft CHURCH search discovered St. Elias Speleota’s Spanish Catholic Church (Ashcroft) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY: Search for Filipino Christian churches in Eastern Suburbs (e.g., Bondi Junction) yields zero local storefronts, expanding to CBD/Haymarket (e.g., Saint Peter Julian's Church) or Indonesian ministries.
- SYDNEY novel discovery: Eagle Vale CHURCH search discovered Mary Immaculate Catholic Church (Eagle Vale) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Toongabbie/Girraween CHURCH search discovered Jesus Our Banner Christian Church as a verified Filipino-affiliated congregation led by Pastors Omy and Jordan De Vera.
- SYDNEY novel discovery: Wentworthville CHURCH search discovered Our Lady of Mount Carmel Catholic Church (Wentworthville) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Guildford CHURCH search discovered Our Lady of the Rosary Parish Kellyville (Kellyville) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Fairfield Heights/Cabramatta CHURCH search discovered Sacred Heart Catholic Church, Cabramatta as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: North Sydney CHURCH search discovered Holy Spirit Catholic Church North Ryde (North Ryde) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Chatswood CHURCH search discovered St. Michael's Catholic Parish (Lane Cove) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Blacktown CHURCH search discovered Our Lady of Lourdes Catholic Church (Seven Hills) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass and Simbang Gabi devotions.
- SYDNEY novel discovery: Blacktown CHURCH search discovered St. Michael's Catholic Church (Blacktown) as a verified Filipino-affiliated parish hosting a monthly Filipino Chaplaincy Mass.
- SYDNEY novel discovery: Liverpool CHURCH search discovered All Saints Catholic Church, Liverpool as a verified Filipino-affiliated parish hosting a Filipino Community Mass on the 4th Sunday of the month.
- SYDNEY novel discovery: Campbelltown/Oran Park CHURCH search discovered St Mary MacKillop Catholic Parish (Oran Park) as a verified Filipino-affiliated congregation with a designated Filipino community group.
- SYDNEY novel discovery: Bankstown/Lakemba CHURCH search discovered Saint Therese Catholic Church (Lakemba) and St Joseph Catholic Church Belmore as verified Filipino-affiliated congregations hosting monthly Filipino Masses.
- SYDNEY novel discovery: Hurstville CHURCH search discovered St Mary Mackillop Parish (St Joseph's Church, Rockdale) as a verified Filipino-affiliated parish hosting a monthly Filipino Mass on the 3rd Sunday of the month.
- SYDNEY novel discovery: Croydon, Five Dock, Mortlake, Summer Hill, and Strathfield CHURCH searches discovered Holy Innocents' Parish, All Hallows, St. Patrick's Mortlake, St Patrick's Summer Hill, and St. Martha's Catholic Church (Strathfield) as verified Filipino-affiliated Catholic churches hosting monthly Filipino Masses (4th Sunday at 11:00 am).
- SYDNEY novel discovery: Bondi Junction CHURCH search discovered St Patrick's Catholic Church, Church Hill in Sydney CBD hosting a monthly Filipino Mass via Maps search radius expansion.
- SYDNEY novel discovery: Macquarie Park CHURCH search discovered St Michael's Catholic Church (West Ryde) as a verified Filipino-affiliated parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Manly CHURCH search discovered St Augustine's Church (Brookvale) hosting a monthly Tagalog Mass, mapped on Google Maps under the label 'St Xavier church - Sydney' at the college campus.
- SYDNEY: Searches for "Sutherland" church listings can return St Therese Parish (Mascot) as a false positive location match due to its address on "Sutherland Street" (which has a verified Filipino Mass), whereas St Patrick’s Catholic Church in the actual suburb of Sutherland has no Filipino affiliation.
- SYDNEY novel discovery: Epping/Carlingford CHURCH search discovered St Kevin's Catholic Church (Eastwood) as a verified Filipino-affiliated parish hosting Tagalog Masses on the 1st Sunday of the month at 4:00 PM and the 3rd Sunday of the month at 11:45 AM.
- SYDNEY novel discovery: Erskine Park CHURCH search discovered Our Lady of the Way Parish (Emu Plains) hosting a monthly Filipino Mass on the 3rd Sunday at 12:00 PM.






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
- The GraphQL `CreateListing` mutation variables do not accept a `suburb` key; passing it will trigger an `INVALID_ARGUMENT` execution error indicating `$suburb is not expected`.
- Separate parishes of the same dedication (e.g., Mary Immaculate Catholic Church in Bossley Park vs Eagle Vale) share identical names; append the suburb or location suffix to the listing name to prevent incorrect name-based duplicate collisions.


