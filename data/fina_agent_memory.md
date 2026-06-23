# Fina Agent Memory

> Self-evolving shared memory for Fina discovery and enrichment agents.
> Agents read this file at session start and update it post-execution.
> Maximum budget: **200 lines**. Agents must aggressively prune stale entries.
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
<!-- City-specific operational knowledge (e.g., suburb coverage saturation, high-yield categories) -->
- SYDNEY/Toongabbie: CAFE category fully saturated (17/20 evaluated Maps results duplicated, 3/20 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Toongabbie: SHOP category fully saturated (7/10 evaluated Maps results duplicated, 3/10 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Eagle Vale: CAFE category yields no local storefronts; Google Maps results are duplicates from neighboring suburbs (Campbelltown, Ingleburn) and are already captured (10/10 duplicates).
- SYDNEY/Eagle Vale: SHOP category fully saturated (all 36 evaluated candidates are duplicates in neighboring Campbelltown, Ingleburn, etc., with 0 new listings).
- SYDNEY/Bossley Park: CAFE category fully saturated (16/18 evaluated Maps results duplicated, 2/18 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Bossley Park: SHOP category fully saturated (17/18 evaluated Maps results duplicated, 1/18 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Auburn: CAFE category fully saturated (15/18 evaluated results duplicated, 3/18 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Auburn: SHOP category search near Auburn discovered Supersave Convenience Store in Berala, while other candidates in Auburn proper are general Asian grocers or duplicates.
- SYDNEY/Lidcombe: CAFE category fully saturated (7/11 evaluated results duplicated, 4/11 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Lidcombe: SHOP category fully saturated (all evaluated candidates are duplicates in other suburbs, or non-Filipino general/Nepalese grocers like Shunli, Family Mart, and Kinmel Bazaar; 0 new listings).
- SYDNEY/Seven Hills: CAFE category fully saturated (26/26 evaluated Maps results duplicated/rejected, 0 new listings). All nearby Filipino bakeries already captured.
- SYDNEY/Seven Hills: SHOP category fully saturated (23/23 evaluated Maps results duplicated/rejected, 0 new listings). Local candidates JT Supermarket (Nepali) and Hills Mega Mart (Sri Lankan) were rejected as non-Filipino.
- SYDNEY/Wentworthville: CAFE category fully saturated (12/12 Maps results duplicated, 0 new listings). All nearby Filipino cafes already captured.
- SYDNEY/Wentworthville: SHOP category fully saturated (20/20 evaluated Maps results duplicated/rejected, 0 new listings). All nearby Filipino shops already captured.
- SYDNEY/Guildford: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes already captured.
- SYDNEY/Guildford: SHOP category fully saturated (20/26 evaluated results duplicated, 6 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Guildford: SHOP category search for Filipino butchers yielded 6 rejected non-Filipino halal/Middle Eastern butchers (e.g., Zaidan's, Guildford West, Guildford Meat Market, Guildford Family Meats, Sydney Quality Meats, Tony Francis Meats) and 0 new listings.
- SYDNEY/Granville: CAFE category fully saturated (11/11 evaluated Maps results duplicated/merged/rejected, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Granville: SHOP category is fully saturated (Kasalo/Pinoy Stop are duplicates, Moonlight Groceries was rejected) and fish market search yielded 10 duplicates and 8 rejected non-Filipino stores.
- SYDNEY/Epping: CAFE category fully saturated (11/12 evaluated Maps results duplicated, 1/12 rejected, 0 new listings). Google Maps results expand to far suburbs (Rooty Hill, Ingleburn, Doonside, Rockdale, Granville, Kings Park) and are already captured.
- SYDNEY/Epping: SHOP category fully saturated (all nearby results are duplicates in other suburbs, and local options like One Supermart and LOVE SUPERMARKET are general Asian grocers and were rejected).
- SYDNEY/Fairfield Heights: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes already captured.
- SYDNEY/Fairfield Heights: SHOP category is fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby options already captured.
- SYDNEY/Fairfield Heights: SHOP category search for Filipino butchers yielded 10 duplicates in neighboring suburbs and 8 rejected non-Filipino/general grocery/butchers (e.g. Theo's Cecinas, Bahsa Halal, Win Phat, Ling's, Rooty Hill, Asian Food, JT Supermarket, 88 Austa), with 0 new listings.
- SYDNEY/Fairfield: CAFE category fully saturated (18/18 evaluated Maps results duplicated/rejected, 0 new listings). All nearby options already captured.
- SYDNEY/Fairfield: SHOP category fully saturated (30/35 evaluated Maps results duplicated, 5/35 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Oakhurst: CAFE category fully saturated (18/18 evaluated Maps results duplicated/rejected, 0 new listings). All nearby Filipino bakeries/cafes already captured.
- SYDNEY/Bonnyrigg: CAFE category fully saturated (19/20 evaluated Maps results duplicated, 1/20 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Bonnyrigg: SHOP category fully saturated (19/25 evaluated results duplicated, 6/25 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Chatswood: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes already captured.
- SYDNEY/Chatswood: SHOP category fully saturated (Manila Sari-Sari Store merged, other options are duplicates/closed).
- SYDNEY/Chatswood: SHOP category search for Filipino fish markets yielded only general/non-Filipino fishmongers (e.g. Astakos, Golden Ocean) and duplicates from other suburbs; 0 new listings.
- SYDNEY/Parramatta: CAFE category fully saturated (18/18 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Parramatta: SHOP category is saturated (Chowking and Mama's Mart permanently closed, other evaluated results are duplicates).
- SYDNEY/Parramatta: SHOP category search for Filipino fish markets yielded 16 duplicates in neighboring suburbs and 14 rejected non-Filipino grocers/fishmongers, with 0 new listings.
- SYDNEY/Blacktown: CAFE category fully saturated (6/6 evaluated Maps results duplicated/merged/closed, 2 new operational listings created). All nearby Filipino cafes/bakeries captured.
- SYDNEY/Blacktown: SHOP category is fully saturated (1 new operational butcher shop listing created for Karnehan Blacktown, other candidates are duplicates or non-Filipino grocers like Tong Li/Asian Food Market).
- SYDNEY/Blacktown: SHOP category search for Filipino fish markets yielded only duplicates in neighboring suburbs and rejected non-Filipino seafood markets (Brothers, Lims, King, Asian Food Market), with 0 new listings.
- SYDNEY/Penrith: CAFE category fully saturated (10/10 evaluated results duplicated/merged/skipped, 0 new listings). All nearby Filipino cafes/bakeries captured.
- SYDNEY/Penrith: SHOP category fully saturated (all evaluated Maps results are duplicates, merged/updated, or rejected/non-Filipino; Maps results expand to neighboring western and southern suburbs).
- SYDNEY/Penrith: SHOP category search for Filipino fish markets yielded only duplicates (Bangketa Grocer, Lola Remy's, Phil-Asian, Super Pinoy) and rejected non-Filipino seafood markets (Barry's, Costi's, St Marys, Atlantic), with 0 new listings.
- SYDNEY/Campbelltown: CAFE category fully saturated (17/17 evaluated Maps results duplicated/merged/skipped, 0 new listings). All nearby Filipino cafes/bakeries captured.
- SYDNEY/Campbelltown: SHOP category is fully saturated (all candidates are duplicates or closed; Kapamilya Asian Groceries has cancelled its ABN as of 2025).
- SYDNEY/Bankstown: CAFE category fully saturated (20/20 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Bankstown: SHOP category is fully saturated/inactive (M.C. Paborito in Yagoona is permanently closed, other evaluated results are duplicates, or non-Filipino general Asian grocers like Tong Li and Best Value).
- SYDNEY/Bankstown: SHOP category search for Filipino fish markets yielded only duplicates in other suburbs and rejected non-Filipino seafood markets (The Seafood King, Nha Trang, Saigon Place, Dai Duong, Kim Tien, Costi Bros, Best Value), with 0 new listings.
- SYDNEY/Liverpool: CAFE category yields no local listings; Google Maps results are from nearby suburbs (Rooty Hill, Ingleburn, Doonside, Mount Druitt) and are already captured.
- SYDNEY/Liverpool: SHOP category is fully saturated (all candidates are duplicates/merged, including Fil-Mart and MRT Pilipino Foods).
- SYDNEY/Liverpool: SHOP category search for Filipino fish markets yielded only duplicates (Fil-Mart, MRT Pilipino Foods) and rejected non-Filipino seafood markets (Casula Fish Market, Yoros Seafood Liverpool, Thuan Phong, Vian), with 0 new listings.
- SYDNEY/North Sydney: CAFE category yields no local bakeshops; Google Maps results expand to far suburbs (Rooty Hill, Ingleburn, Blacktown, Castle Hill) and are mostly duplicates.
- SYDNEY/North Sydney: SHOP category yields no local storefronts; Google Maps results expand to other suburbs (Mascot, Ashfield, Chatswood, West Ryde, Cabramatta) and are already captured (10/10 duplicates).
- SYDNEY/Hurstville: CAFE category fully saturated (all nearby results are duplicates, non-Filipino, or other categories like SHOP/SERVICES).
- SYDNEY/Hurstville: SHOP category is fully saturated (Lovely Variety Store created as online-only shop, Pinoy Grocer is already captured).
- SYDNEY/Hurstville: SHOP category search for Filipino fish markets yielded only duplicates in neighboring suburbs and rejected non-Filipino seafood markets (Mable, Tosca, Fish Feast), with 0 new listings.
- SYDNEY/Hornsby: CAFE category fully saturated (14/14 evaluated Maps results duplicated, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Hornsby: SHOP category is fully saturated (Suki Kart is already captured/duplicate).
- SYDNEY/Ryde: CAFE category fully saturated (13/16 evaluated Maps results duplicated, 3 rejected/non-Filipino, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Ryde: SHOP category fully saturated (Manila Mart West Ryde is already captured/duplicate, other results are non-Filipino general Asian grocers like Tong Li and Happigo in Top Ryde City).
- SYDNEY/Ryde: SHOP category search for Filipino fish markets yielded only general/non-Filipino fishmongers (e.g. Peter Roan, Costi, Viet Hoa) and duplicates from other suburbs; 0 new listings.
- SYDNEY/Burwood: CAFE category fully saturated (all nearby results are duplicates, non-Filipino, or other categories).
- SYDNEY/Bondi Junction: CAFE category fully saturated (9/9 evaluated results are duplicates, merged/updated, or non-Filipino, 0 new listings).
- SYDNEY/Bondi Junction: SHOP category search for Filipino fish markets yielded 9 duplicates, 9 rejected non-Filipino seafood stores, and 1 new online grocery listing (Mabuhey App, located in Haymarket) discovered via Maps search radius expansion.
- SYDNEY/Bondi Junction: SHOP category is otherwise fully saturated (all other candidates are duplicates, permanently closed like Bondi Asian Mart, or non-Filipino like Summit Asian Supermarket).
- SYDNEY/Macquarie Park: CAFE category yields no local listings; Google Maps results are from other suburbs (Rooty Hill, Rockdale, Doonside, etc.) and are already captured.
- SYDNEY/Macquarie Park: SHOP category yields no local Filipino grocers; Google Maps results expand to other suburbs (West Ryde, Hornsby, Chatswood, Mascot, etc.) and are mostly duplicates, while local result Kedai Runcit Sikit-sikit is Malaysian-affiliated and was rejected.
- SYDNEY/Castle Hill: CAFE category maps search covers surrounding western suburbs (Doonside, Rooty Hill, Windsor) with high duplicate rates, but successfully discovered Hanmades Bakehouse Windsor.
- SYDNEY/Castle Hill: SHOP category is fully saturated (all candidates are duplicates or non-Filipino like 77 Mart, and no new listings were discovered).
- SYDNEY/Manly: CAFE category yields no local bakeshops; Google Maps results expand to far-flung suburbs (Dee Why, Mount Druitt, Rooty Hill, Granville, Ingleburn) and are already captured/merged.
- SYDNEY/Manly: SHOP category yields no local storefronts; Google Maps results expand to other suburbs and are duplicates or rejected.
- SYDNEY/Manly: SHOP category search for Filipino fish markets yielded only general/non-Filipino seafood stores (e.g. Fish in the Family, Faros Seafood, Manly Seafoods) and duplicates from other suburbs; 0 new listings.
- SYDNEY/Cronulla: CAFE category yields no local bakeshops; Google Maps results are duplicates from other suburbs or non-Filipino patisseries, or home bakers like Sweet Josie (Acacia Gardens) that belong to SERVICES.
- SYDNEY/Cronulla: SHOP category is fully saturated (all 12 evaluated Maps candidates are duplicates, and Kabayan Market operates online/markets rather than a physical Cronulla storefront; 0 new listings).
- SYDNEY/Cronulla: SHOP category search for Filipino fish markets yielded only general/non-Filipino seafood stores (Notaras, Caringbah, Astakos, Poseidon) and duplicates from other suburbs; 0 new listings.
- SYDNEY/Sydney Olympic Park: CAFE category yields no local bakeshops; Google Maps results are duplicates from other suburbs (Granville, Wentworth Point, etc.) or non-Filipino eateries.
- SYDNEY/Sydney Olympic Park: SHOP category yields no local storefronts; Google Maps results are duplicates from other suburbs (West Ryde, Ashfield, Cabramatta, Mascot) and are already captured (10/10 duplicates).
- SYDNEY/Plumpton: CAFE category fully saturated (12/18 evaluated Maps results duplicated, 2 rejected, 0 new listings). All nearby Filipino cafes/bakeries already captured.
- SYDNEY/Plumpton: SHOP category fully saturated (16/17 evaluated Maps results duplicated, 1/17 rejected, 0 new listings; nearby options in Rooty Hill, Doonside, Mount Druitt, St Marys are already captured).
- SYDNEY/Rooty Hill: CAFE category mostly saturated, but Prestons search successfully discovered PanaDarna (located inside The Kamayan).
- SYDNEY/Prestons: CAFE category has no local storefronts; Google Maps results are from nearby suburbs, but successfully discovered PanaDarna in Rooty Hill.
- SYDNEY/Doonside: CAFE category fully saturated (15/15 evaluated results duplicated, 0 new listings). All nearby Filipino bakeries/cafes already captured.
- SYDNEY/Doonside: SHOP category fully saturated (all candidates are duplicates, including Pinoy Stop, Kutis Pinay Au, and Oi Manila Food Hall).
- SYDNEY/Woodcroft: CAFE category fully saturated (10/10 evaluated results duplicated, 0 new listings). No local bakeries exist; all nearby options in Rooty Hill, Doonside, Blacktown, and Eastern Creek are already captured.
- SYDNEY/Woodcroft: SHOP category fully saturated (all nearby evaluated Maps results are duplicates in neighboring suburbs, or non-Filipino like Palms Pacific and Tong Li).
- SYDNEY/St Clair: CAFE category fully saturated (17/18 evaluated Maps results duplicated, 1 rejected/non-Filipino, 0 new listings). Nearby options in Rooty Hill, Doonside, Mount Druitt, and Eastern Creek are already captured.
- SYDNEY/St Clair: SHOP category is fully saturated (all nearby candidates are duplicates, non-Filipino general Asian grocers like Good Luck Plaza, or wholesale distributors like SBC Foods).
- SYDNEY/St Marys: CAFE category fully saturated (16/16 evaluated Maps results duplicated, 0 new listings). All nearby Filipino bakeries/cafes already captured.
- SYDNEY/St Marys: SHOP category fully saturated (10/10 evaluated results duplicated, 0 new listings). All local storefronts (Phil-Asian, El Pinoy, Sto Nino, SBC Foods, Super Pinoy) already captured.
- SYDNEY/St Marys: SHOP category search for Filipino fish markets yielded 10 duplicates and 9 rejected non-Filipino seafood stores/general grocers (e.g., St Marys Fish Market, Hong Meat), with 0 new listings.
- SYDNEY/Erskine Park: CAFE category fully saturated (18/18 evaluated Maps results duplicated, 0 new listings). All nearby Filipino bakeries/cafes already captured.
- SYDNEY/Erskine Park: SHOP category is fully saturated (all candidates are duplicates in nearby suburbs, including Phil-Asian Supermarket, Super Pinoy, Suki Kart, Lola Remy's, and Pabico).
- SYDNEY/Casula: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; nearby options in Ingleburn, Warwick Farm, and Campbelltown are already captured.
- SYDNEY/Hoxton Park: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; nearby options in Ingleburn, Rooty Hill, Rockdale, Campbelltown, and Kings Park are already captured.
- SYDNEY/Hoxton Park: SHOP category fully saturated; fish market and grocery search yielded only duplicates (MRT, Pinoy Stop, MerKado, Pasalubong) and rejected seafood stores.
- SYDNEY/Green Valley: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; nearby options in Doonside, Rooty Hill, Rockdale, Eastern Creek, Cabramatta, and Ingleburn are already captured.
- SYDNEY/Green Valley: SHOP category fully saturated (9/10 evaluated Maps results duplicated, 1/10 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Ingleburn: CAFE category fully saturated (6/6 results duplicated/merged, 0 new listings). All local options are already captured/updated.
- SYDNEY/Ingleburn: SHOP category is fully saturated (evaluated results: Pinoy Stop, Masagana Mini Mart, Casa Filipina are duplicates; fish market search yielded only duplicates and Nepalese-affiliated Nanglo Grocery was rejected).
- SYDNEY/Macquarie Fields: CAFE category yields no local bakeshops; Google Maps results are duplicates from neighboring Ingleburn (BakeFresh, Casa Filipina) or other categories (Mummy Inday's Catering).
- SYDNEY/Macquarie Fields: SHOP category fully saturated (18/18 evaluated results duplicated, 0 new listings). Nearby options in Ingleburn, Campbelltown, Cabramatta, and Ashfield are already captured.
- SYDNEY/Merrylands: CAFE category fully saturated (27/27 evaluated results are duplicates, non-Filipino like Mina Bakery, or other categories, 0 new listings).
- SYDNEY/Merrylands: SHOP category fully saturated (butcher search yielded 3 duplicates, 6 rejected; fish market search yielded 28 duplicates, 3 rejected; 0 new listings).
- SYDNEY/Minto: CAFE category yields no local bakeshops; Google Maps results are duplicates from neighboring suburbs (Ingleburn, Campbelltown) or far-flung ones (Rooty Hill, Rockdale), or are non-Filipino (Peace Bakery, Doughlicious Bakery).
- SYDNEY/Minto: SHOP category fully saturated (Oriental Grocer, Essential Supermarket, and Minto Fish Market were rejected as non-Filipino; fish market search yielded 5 duplicates in neighboring suburbs, with 0 new listings).
- SYDNEY/Emerton: CAFE category fully saturated (24/24 evaluated Maps results duplicated/rejected, 0 new listings). All nearby options already captured.
- SYDNEY/Emerton: SHOP category is fully saturated (42/48 evaluated Maps results duplicated, 6/48 rejected, 0 new listings; all nearby options in Mount Druitt, Rooty Hill, St Marys, and Blacktown are already captured).
- SYDNEY/Marsden Park: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby options already captured.
- SYDNEY/Quakers Hill: CAFE category fully saturated (16/18 evaluated Maps results duplicated, 2 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Quakers Hill: SHOP category fully saturated (25/27 evaluated Maps results duplicated, 2/27 rejected/non-Filipino, 0 new listings).
- SYDNEY/Mount Druitt: CAFE category fully saturated (8/8 evaluated results are duplicates, and TFC is closed; all nearby Filipino cafes/bakeries are already captured).
- SYDNEY/Mount Druitt: SHOP category fully saturated (15/18 evaluated results duplicated, 3/18 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Mount Druitt: SHOP category search for Filipino butchers yielded 7 duplicates and 12 rejected non-Filipino halal butcheries/shops (e.g. Dunya, Nazar, Aashyana, Paak, Merjan Brothers), with 0 new listings.
- SYDNEY/Colyton: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; all nearby options in Mount Druitt, Rooty Hill, and Doonside are already captured.
- SYDNEY/Colyton: SHOP category fully saturated (43/47 evaluated Maps results duplicated, 4/47 rejected as Wollongong/non-Filipino, 0 new listings).
- SYDNEY/Glenmore Park: CAFE category fully saturated (18/18 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; nearby options in Penrith, Jordan Springs, Rooty Hill, and Doonside are already captured.
- SYDNEY/Glenmore Park: SHOP category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino grocery shops exist; all candidates are duplicates in neighboring suburbs (Penrith, Jordan Springs, St Marys).
- SYDNEY/Kingswood: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). No local Filipino bakeries exist; nearby options in Penrith, Jordan Springs, Rooty Hill, Doonside, and Eastern Creek are already captured.
- SYDNEY/Kingswood: SHOP category fully saturated (10/11 evaluated Maps results duplicated, 1/11 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Jordan Springs: CAFE category fully saturated (15/16 evaluated Maps results duplicated, 1/16 rejected/non-Filipino, 0 new listings). No local Filipino bakeries exist; nearby options in Penrith, Rooty Hill, Doonside, and Eastern Creek are already captured.
- SYDNEY/Jordan Springs: SHOP category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby options already captured.
- SYDNEY/West Hoxton: CAFE category fully saturated (10/10 evaluated Maps results duplicated, 0 new listings). All nearby Filipino bakeries already captured.
- SYDNEY/West Hoxton: SHOP category fully saturated (17/20 evaluated Maps results duplicated, 3/20 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Edmondson Park: CAFE category fully saturated (25/27 evaluated Maps results duplicated, 2/27 rejected/non-Filipino, 0 new listings). No local Filipino bakeries exist; all nearby options already captured.
- SYDNEY/Edmondson Park: SHOP category fully saturated (28/28 evaluated Maps results duplicated/rejected, 0 new listings). Local option Ambey's Big Apple is Indian-focused and was rejected; other candidates are duplicates in neighboring suburbs.
- SYDNEY/Moorebank: CAFE category yields no local listings; Google Maps results are Lebanese, French, or Vietnamese bakeries, or duplicates from nearby suburbs (Ingleburn, Cabramatta, Glenfield) which are already captured.
- SYDNEY/Moorebank: SHOP category is fully saturated (all 33 evaluated candidates are duplicates or rejected, 0 new listings).
- SYDNEY/Glenfield: CAFE category fully saturated (10/11 evaluated Maps results duplicated, 1/11 rejected/non-Filipino, 0 new listings).
- SYDNEY/Glenfield: SHOP category fully saturated (17/18 evaluated Maps results duplicated, 1/18 rejected/non-Filipino, 0 new listings).
- SYDNEY/Raby: CAFE category fully saturated (17/18 evaluated Maps results duplicated, 1/18 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Raby: SHOP category fully saturated (23/23 evaluated Maps results duplicated, 0 new listings). All nearby options already captured.
- SYDNEY/Rooty Hill: SHOP category is fully saturated (fish market search yielded 13 duplicates, and 4 rejected non-Filipino shops including Tropical Taste Market).
- SYDNEY/Casula: SHOP category is fully saturated (17/22 evaluated Maps results duplicated/merged, 5/22 rejected, 0 new listings).
- SYDNEY/Prestons: SHOP category is not fully saturated; search discovered Tapsi Supermarket, a new operational Filipino grocery store.
- SYDNEY/Prestons: SHOP category search for Filipino butchers yielded only duplicates from other suburbs or restaurants rather than local butchers.
- SYDNEY/Marsden Park: SHOP category fully saturated (10/10 evaluated results duplicated, 0 new listings). All nearby options already captured.
- SYDNEY/Oakhurst: SHOP category is fully saturated (all nearby candidates are duplicates in Doonside, Rooty Hill, St Marys, etc., and Palms Pacific Supermarket was rejected; 0 new listings).
- SYDNEY/Burwood: SHOP category fully saturated (15/20 evaluated Maps results duplicated, 5/20 rejected/non-Filipino, 0 new listings). All nearby options already captured.
- SYDNEY/Quakers Hill: SHOP category search for Filipino butchers yielded 10 duplicates in neighboring suburbs and 10 rejected non-Filipino grocers/halal butchers, with 0 new listings.
- SYDNEY/Penrith: Trin's Asian Mart in Westfield Penrith was rejected as a Chinese-focused general Asian supermarket (Liqun Chinese Supermarket).
- SYDNEY/Prestons: SHOP category search for Filipino fish markets yielded 12 duplicates and 14 rejected non-Filipino seafood stores, with 0 new listings.
- SYDNEY/Burwood: SHOP category search for Filipino fish markets yielded 10 duplicates in neighboring suburbs and 10 rejected non-Filipino grocers/fishmongers, with 0 new listings.
- SYDNEY/Erskine Park: SHOP category search for Filipino fish markets yielded only duplicates in other suburbs and rejected non-Filipino seafood markets (e.g. Lims Fresh Seafood, Faros Seafood, Seafood Factory Outlet); 0 new listings.

## Known Pitfalls
<!-- Failure modes, validation errors, and how to avoid them -->
- City Casing Case-Sensitivity: Firebase SQL Connect queries are case-sensitive (e.g. `city: { eq: "SYDNEY" }`). Any listings created or restored with capitalized or lowercase city names (e.g., `Sydney` or `sydney`) will be hidden from client browse/search results. Ad-hoc scripts and ingestion agents must always normalize city values to uppercase (as defined in the frontend's City enum).
- Listing ID Drift: Re-creating listings from backup generates new database UUIDs. Any external files or trackers referencing the old listing IDs will become obsolete and must be regenerated or updated.
- The existing city listings cache JSON file is written as a single line, making simple grep query matches prone to truncation or failure; always use the dedicated duplicate check script.
- The `agent_check_duplicate.py` script will skip name-based duplicate matches if any URL is passed to `--url` but the cached listing has no social URLs (all null); omit `--url` or use specific parameters (e.g. `--facebook-url`) to enable name-matching and merge detection.
- The GraphQL UpdateListingData mutation expects tags as a comma-separated String, not a list, whereas CreateListing automatically normalizes a list of tags.
- The name normalization function does not replace curly apostrophes (’) with straight apostrophes ('), meaning duplicate checks (e.g. for Tita’s Cakes vs Tita's Cakes) will fail unless inputs are normalized first.
- The Google Maps detail panel may render operating hours with day names and times on separate lines, causing `parse_maps_opening_hours` to return `None`; clean the text to 'Day: Hours' format before parsing.
- The GraphQL CreateListing and UpdateListingData mutations expect `operatingHours` as a serialized JSON String, not a JSON object/map; passing a raw dictionary will trigger a GraphQL INVALID_ARGUMENT execution error.
- The GraphQL CreateListing mutation requires a non-empty `description` string; omitting it or setting it to null will trigger an `INVALID_ARGUMENT: $description (String) is missing` execution error.
- The `agent_check_duplicate.py` name matching is highly sensitive to naming variations; Google Maps results containing descriptive suffixes (e.g., "The Bangketa Grocer - Filipino shop" vs "The Bangketa Grocer") will fail to match, so you should check with the base/shortened name if duplicate checks fail.

