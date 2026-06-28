# Fina Agent Memory

> Self-evolving shared memory for Fina discovery and enrichment agents.
> Agents read this file at session start and update it post-execution.
> Maximum budget: **500 lines**. Agents must aggressively prune stale entries.
> Supersession rule: new insights that contradict existing entries replace them.
> Format: concise bullet points (one line per insight). No prose paragraphs.

## Platform & Browser Insights
<!-- Reusable facts about platforms, anti-bot patterns, and browser behaviour -->
- Google Maps `evaluate_script` requires arrow function syntax `() => expr` (not bare expressions or statements with semicolons).
- The Chrome DevTools `evaluate_script` MCP tool expects the JavaScript payload in the parameter named `function` (not `script`).
- Active page focus can change dynamically if other agent sessions are running in parallel; verify selection or re-select the target page context via select_page before executing scripts.
- Google Maps search for a brand name with no local pin may redirect/zoom to coordinates in the Philippines; verify the location or search for the specific street address to confirm.
- Google Maps search query for a suburb name shared across states (e.g. Epping in NSW and VIC) can return results from the wrong state; verify state/coordinates to filter out-of-bounds candidates.
- Google Maps search query with a single dominant result redirects directly to its detail panel, bypassing the search results list, even if that result is geographically far from the queried suburb.
- Navigating directly to a Google Maps place URL (e.g. /maps/place/...) in the browser can redirect to a blank location panel (e.g. /maps/place//@...); search for the venue name directly on Google Maps to load details reliably.
- Google Maps operating hours for days with multiple slots (e.g. Sunday Masses) are wrapped in <ul>/<li> elements, requiring concatenating list item texts with commas before passing to the parser.
- Google Maps staticmap center URL parameter can return cached coordinates from a previous session; verify coordinates via web search or rely on the push script geocoder.
- In Google Maps browser scraping, search result cards in the left sidebar can be reliably identified and clicked using the `a.hfpxzc` CSS selector.
- In Google Maps browser scraping, direct calls to `element.click()` on `a.hfpxzc` might fail to open the detail panel; scroll the card into view and dispatch `mousedown`, `mouseup`, and `click` events sequentially to trigger the navigation.
- Linktree Profile Pages: Social media profile URLs are often embedded in interactive icon buttons or JSON script blocks (such as schema.org ld+json script blocks or NEXT_DATA) rather than standard href links. Extract Facebook, Instagram, TikTok, Discord, and Email links by querying the script block for the sameAs array or socialLinks.
- Candidate websites using Cloudflare security verification or Turnstile challenges (e.g. pinoybasketballaustralia.com.au) will block browser automation; fallback to already loaded homepage content or other social media profiles to extract contact information.
- The Google Maps search input ID can be dynamic or change (e.g., searchboxinput to ucc-1); use document.querySelector('input[name="q"]') as a robust fallback selector to focus and clear the input before typing.
- In Google Maps browser scraping, operating hours can be reliably extracted day-by-day by querying buttons with an aria-label containing "Copy open hours" and removing the copy suffix.
- Navigating the primary browser page away from a Google Maps search results view (e.g., to verify a candidate's website or social media profile) resets the loaded results list, requiring re-running the scroll container logic to rebuild the candidate queue upon returning.
- In Google Maps detail panel, the phone number button's data-item-id attribute contains the phone number itself (e.g. phone:tel:0430373884); use the prefix selector button[data-item-id^="phone:tel:"] to locate and extract it.
- Business websites can contain social media buttons (e.g. Facebook, Instagram) in the header or footer with empty/placeholder `href` attributes (""); verify profile existence via search if links are blank.
- When a business found via web search does not have a dedicated Google Maps listing under its name, search Google Maps for its physical street address to resolve coordinates.
- In Google Maps details panel, if the "Copy open hours" button is absent or contains incomplete hours, the weekly hours table can be extracted by querying the first `table` element and mapping cell values of each `tr` row to standard day abbreviations.
- When extracting Google Maps opening hours from the weekly table element, join the row text values using newlines (\n) instead of commas to ensure the day parser correctly splits and identifies the day name prefixes without leading separators.



## Discovery Patterns
<!-- What works and what doesn't when searching for Filipino businesses -->
- Suburb-level searches for Filipino student associations consistently yield zero local suburb-specific results, as student organizations in Sydney are strictly university-based (e.g. USYD, UNSW, UTS, Macquarie, WSU).
- Independent websites are critical for discovering official social media profiles of businesses that use numeric profile IDs (e.g., profile.php?id=...) which do not rank well in standard search engine queries.
- `search_web` with `site:facebook.com` or `site:instagram.com` for niche suburb queries (e.g. "Filipino cafe in Wentworthville") returns aggregated summaries rather than direct profile URLs — most candidates come from Round 4 (Google Maps browser).
- Multi-branch organizations or churches (e.g., Jesus Is Lord Church) often share a single national website or regional Facebook page; evaluate physical address and branch name rather than relying solely on URL matches to prevent incorrect duplicate detections.
- The Good Filo (Ramsgate/Kogarah) is a Greek bakehouse and Lusinata (Hurstville) is a Portuguese patisserie; neither is Filipino-affiliated.
- Kate Foods (Seven Hills) is a Sri Lankan and Indian grocery store and is not Filipino-affiliated, despite partnering with InterHub Logistics.
- Leoliusports Swim Centre (Hurstville) is a swimming and fencing school run by Leo Liu; it is not Filipino-affiliated.
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
- Searches containing "Filipino" can return Sanfilippo Children's Foundation as a false positive due to the substring similarity ("filippo" / "filipino"); Sanfilippo is a genetic disease charity and is not Filipino-affiliated.
- Sydney church searches containing "Filipino" can return Indonesian churches (e.g., Filadelfia Church / Gereja Indonesia, Ecclesia Mission) as false positives; verify Indonesian terminology ("Gereja") or leadership names to filter out.
- Bread of Life Christian Church (under "1503 Mission Network" in Sydney) is Taiwanese-affiliated (Zhongli branch origin) and is not Filipino-affiliated, despite sharing name similarities with Filipino charismatic groups.
- CCCS (Congregational Christian Church of Samoa) is Samoan-affiliated and is not Filipino-affiliated, serving the Samoan diaspora.
- Sydney church searches near Western Sydney suburbs can return Maronite, Chaldean, Coptic, Slovenian, and Melkite Greek Catholic churches (e.g., Saint John the Beloved Maronite, St Joseph Chaldean, St Anthony & St Paul Coptic, St Raphael's Slovenian, Saint Elias Melkite) as false positives; these serve non-Filipino diaspora communities.
- New Life Sydney Christian Church (Rouse Hill/Toongabbie) is verified Filipino-affiliated, whereas New Life Christian Church (Woodcroft) is a Reformed/non-Filipino-affiliated church, despite their very similar names.
- Good Shepherd Catholic Church (Hoxton Park) is verified Filipino-affiliated, hosting the annual Feast of the Black Nazarene devotion since 1995.
- Holy Family Catholic Church (Ingleburn) is verified Filipino-affiliated, hosting a dedicated monthly Filipino Mass (4th Sunday at 4:30 pm) and Filipino choir.
- Mary Immaculate Catholic Church (Bossley Park) is verified Filipino-affiliated, hosting a Tagalog Mass on the 2nd Sunday of each month at 11:00 am, led by the Filipino Chaplain (Rev. Fr. Nards Mercene).
- Bethel Bible Baptist Church (Ingleburn) is verified Filipino-affiliated, led by a Filipino pastor (Pastor Arellano) with a strong Filipino congregation.
- Pentecostal Christian Assembly (PCA Church) in Ingleburn is Malayalam-speaking and 4C Community Church (Ingleburn) is Chinese-affiliated; neither is Filipino-affiliated.
- Sydwest Asian Christian Church (Cabramatta) is Chinese-affiliated (Mandarin/Cantonese services) and Sydney House of Praise (Lansvale) is Samoan/Pacific Islander-affiliated; neither is Filipino-affiliated.
- General Australian churches listing the Philippines as an overseas missionary/charity destination (e.g. Emmanuel Christian Family Church or Plumpton Community Church) are not Filipino-affiliated unless they host dedicated local services or ministries for the Filipino community.
- Foursquare Gospel Minchinbury (Minchinbury) is the Google Maps label for FCF Life Centre (formerly Filipino Christian Fellowship) and is verified Filipino-affiliated.
- Mary Queen of the Family Parish / St Patrick's Catholic Church (Blacktown) is verified Filipino-affiliated, hosting a monthly Filipino Mass and celebrating the Sinulog festival.
- Our Lady of the Rosary Catholic Cathedral (Waitara/Hornsby) is verified Filipino-affiliated, hosting a monthly Filipino Mass on the 2nd Sunday of the month at 3:30 pm.
- Franciscan Shrine of the Holy Innocents (Kellyville) is part of the Our Lady of the Rosary Parish Kellyville and does not host a separate Filipino Mass; avoid creating it as a separate listing.
- Web search queries combining a local parish name with "Filipino" or "Tagalog" can return false-positive snippets from a different parish of the same dedication in another country (e.g., Walnut Creek, California, for St John Vianney); verify that contact details, domains (e.g., sjvianney.org vs stjohnvianneydoonside.org.au), and addresses belong to the Australian parish before confirming affiliation.
- White Pages database entries showing "Catholic Church" at Lord Howe Drive, Green Valley are erroneous; no physical parish exists at that location, and Catholic services in the Green Valley area are served by St John the Baptist Parish in Bonnyrigg Heights.
- The Feast (Light of Jesus Family) prayer groups in Sydney (e.g., Winston Hills) typically meet inside existing Catholic parishes, sharing the same physical address/place ID and merging during database ingestion.
- Liverpool Catholic Club (Prestons) is a general family/social club that hosts Filipino community events, but is not a Filipino-affiliated church or organization, despite review snippets mentioning "Philippino culture and faith".
- Ingleburn RSL Club (Ingleburn) is a general family/social RSL club and is not Filipino-affiliated, despite review snippets mentioning a Filipino band (Alter Ego).
- Google Maps searches for community associations in low-density suburbs can return results from other states (e.g., VIC, QLD, NT); verify the state or telephone area code (e.g., (02) for NSW) to filter out out-of-bounds candidates.
- The Alliance of Philippine Community Organisations (APCO) Inc. registration was cancelled in January 2024; its successor is the Philippine Australian Global Alliance for Service & Advocacy (PAGASA) Inc. based in Liverpool.
- Google Maps searches for community associations can return regional administrative headquarters of global organizations (e.g. Rotary International South Pacific and Philippines Office) as false positives; verify that the entity directly organizes local services or events for the Filipino community in the target city before adding it.
- Active community associations in South West Sydney (e.g., PAGASA Inc, Visayan Association of Australia) often share a common leadership team and contact emails (e.g. jhunscelebration@gmail.com); identifying shared contacts helps trace sister organizations and avoid redundant verification steps.
- Commercial martial arts academies in Sydney offering Filipino Martial Arts (e.g. Armas Kali, Eskrima, or Arnis at MARA Prospect or INRG Martial Arts Seven Hills) belong to the SERVICES category, not the COMMUNITY category, despite teaching cultural heritage arts.
- Registered community organizations from official embassy/government directories (e.g., Bankstown Filcos Association) that lack any online footprint, contact info, or description cannot be verified or added and must be skipped.
- Google Maps listings can show a "Located in" tag referencing a food hall or market in a different suburb (e.g. Wow Filipino Food in Eastwood showing "Located in: Burwood Chinatown Night Market"); check the physical address field to verify the correct suburb.
- Pinoy Basketball Australia Sydney (PBAS) and PBA Originals (PBAO) are two distinct Filipino basketball associations operating at the same physical venue (Minto Indoor Sports Centre, 9 Redfern Rd, Minto) and must not be merged.
- Sydney FilOz Badminton (SFB) is a verified Filipino community sports group that meets weekly (Saturdays 1:00 PM - 4:00 PM) at Alpha Badminton Centre (Egerton) in Silverwater, using the DoublesTeam app for event queuing and coordinating via social media without a dedicated ABN.
- General public sports complexes and stadiums (e.g., Kevin Betts Stadium in Mount Druitt) that host community basketball games/leagues are not Filipino-affiliated community organizations themselves and should be rejected.
- Sydney church/religious searches in multicultural hubs (Blacktown, Seven Hills) return South Asian (Tamil, Malayalam, Hindi, Sinhala), Croatian, Indonesian, African (Ghanaian, Zimbabwean), and general charismatic groups (e.g. Servants of Jesus Community, Family Covenant Church, KLGM) as false positives.
- Sydney church/religious searches in South-West/Western Sydney multicultural hubs (e.g. Canley Heights, Liverpool) can return Spanish-speaking/Hispanic congregations (e.g., Global Family Church, Movimiento Misionero Mundial) as false positives.
- Sponsor directories and sponsor links on local Filipino sports league websites (e.g. PBA Originals) are high-yield sources for discovering new Filipino business storefronts, services, and home bakers in the region.
- Believers of Pentecost Church of God (Blacktown) is a Nigerian-led congregation (pastor Olumuyiwa Adams) and is not Filipino-affiliated, despite sharing its exact name with a verified Filipino church in Muñoz, Philippines.
- Uniting Churches (such as Quakers Hill Uniting Church) can host distinct, long-standing Filipino congregations and services, often identifiable by dedicated 'Filipino Service' Facebook groups.
- Missionary and 'Partners in Missions' pages on local independent church websites are high-yield sources for confirming Filipino affiliation and discovering sister congregations across other cities.
- UNITED PACIFIC FREIGHT PTY LTD (Minto) is a Pacific Island-focused shipping service (serving Samoa/Pacific Islands) and is not Filipino-affiliated, despite appearing in Balikbayan box queries.
- JNZ Movers Logistics Services (Parramatta) and Transco Sydney (Seven Hills) are Sri Lankan/Indian cargo services, and The City Box (Arndell Park) is an automotive truck accessory supplier; none is Filipino-affiliated despite appearing in Balikbayan box searches.
- Bayanihan Cargo Services (bayanihan.com.au / ABN 87 668 158 281) is headquartered in Queensland and Victoria, with no local Sydney physical footprint/depot.
- J. Cordon Express (jcordonexpress.com / ABN 95 612 893 615) is headquartered in Hallam, Victoria, with no local Sydney physical footprint/depot.
- SYDNEY: Balikbayan box search templates yield high numbers of non-Filipino national couriers (Australia Post, Pack & Send, DHL) and international cargo lines (Ceylon Shipping); the few genuine Filipino cargo agents are highly clustered in Western Sydney.
- SYDNEY: Cleaning service search templates in suburban Google Maps searches yield high rates of false positives (general local cleaning services and national franchises like Jim's or Housework Heroes) due to search radius and keyword expansion when no local Filipino cleaning services exist.
- Third-party business directories or quoting platforms (e.g. Oneflare) can contain explicit Filipino affiliation statements in their business descriptions even if the official website is generic.
- A candidate business website or social page may list a telephone number with a +63 (Philippines) country code prefix despite having an Australian address; this is a strong positive signal for Filipino affiliation.
- Inspecting owner/founder names on website 'About Us' pages, ABN registries, or linked personal socials (e.g., LinkedIn profiles, personal Instagram handles) is highly effective for verifying Filipino ownership or filtering out South Asian/non-Filipino false positives in local services.
- Service providers (e.g., cleaning, accounting) may advertise coverage in multiple states/cities on their website while being physically headquartered in another state; verify their actual office address to ensure they are local before ingesting.
- Google Maps search results can return multiple branch listings for mock cleaning services like 'Merryfull Cleaning', 'Rosemary's Cleaning Services', 'Glendale Cleaning Services', and 'Jojo Cleaning Service' (aka 'Cleanify' / 'Earthly Elegance' sharing phone 0452 431 242); these are placeholder mock pages generated by Calso Pty Ltd (Starworks) for demo/SEO purposes and should be rejected.
- The FiloConnect directory (filoconnect.com.au) lists local Filipino-owned businesses in Sydney but contains some placeholder/dummy contact details (e.g., example.com, 0411 222 333) which must be verified and cleaned or omitted during ingestion.
- Catering search templates (e.g., 'Filipino catering near <suburb>') in Google Maps search return established restaurants and cafes across the entire metropolitan area due to search radius expansion, leading to high duplicate rates.
- General food/catering candidates (e.g., Feedee Foods) can appear in search queries but may be Vietnamese-owned (e.g., Sycamore Khuat Pty Ltd); verify registered business owner names or ABN/ASIC registry names to filter out non-Filipino services.


## Enrichment Patterns
<!-- Techniques and observations from the listing enrichment workflow -->
- Instagram profiles for alcohol/liquor brands are age-restricted (18+) and cannot be viewed without login; follower counts and posts are inaccessible to unauthenticated Chrome DevTools sessions.
- Facebook pages for some businesses return "This content isn't available at the moment" when accessed without login; this is not a closure signal — the page may be restricted, renamed, or set to require authentication.
- When Google Maps does not display social media links in the business info panel, the business's own website footer often contains Facebook, Instagram, TikTok, YouTube, and LinkedIn links — always check the website as a fallback discovery source for social URLs.
- TikTok profiles may present a CAPTCHA challenge on first load in Chrome DevTools, blocking follower count extraction; this is an anti-bot measure that cannot be bypassed without human intervention.

## Events Patterns
<!-- Event discovery insights: date parsing quirks, platform event formats, classification edge cases -->

## City Intelligence
<!-- City-specific operational knowledge: aggregate geographic patterns, novel discoveries, high-yield zones -->
- SYDNEY CAFE/SHOP: All 60 suburbs for CAFE and SHOP categories are fully saturated at the city-level task tier. Filipino food/retail businesses are heavily concentrated in Western Sydney (Blacktown, Rooty Hill, Doonside, Mount Druitt, Fairfield, Parramatta corridor) with secondary clusters in South-West (Campbelltown, Ingleburn, Liverpool).
- SYDNEY Eastern/Northern coastal suburbs (Bondi Junction, Manly, Cronulla, North Sydney, Macquarie Park, Sydney Olympic Park) have zero local Filipino storefronts — Maps results always expand to Western Sydney duplicates.
- SYDNEY: Western Sydney suburbs (Parramatta, Granville, Lidcombe, Guildford, Merrylands) have a high density of established duplicate churches; search yields for new Filipino congregations in this corridor are very low.
- SYDNEY: Small Western Sydney residential suburbs (e.g. Oakhurst, Glendenning, Hassall Grove) have high Filipino populations but lack suburb-specific community organizations; searches for local community groups consistently resolve to regional duplicates (e.g. PCCNSW, SAFSI, TAA).
- SYDNEY: Northern Sydney suburbs (Epping, Ryde, Carlingford) yield zero new Filipino religious groups/communities, with search results dominated by Korean/Chinese congregations or resolving to established regional duplicates (e.g., PCCNSW, Filipino Chaplaincy of Parramatta).
- SYDNEY novel discovery: Auburn SHOP search discovered Supersave Convenience Store in nearby Berala.
- SYDNEY novel discovery: Sydney Olympic Park COMMUNITY search discovered Free Believers in Christ Fellowship International in Auburn.
- SYDNEY novel discovery: Blacktown CAFE search yielded 2 new operational listings; SHOP search discovered Karnehan Blacktown (Filipino butcher shop).
- SYDNEY novel discovery: Hurstville SHOP search created Lovely Variety Store as an online-only Filipino shop.
- SYDNEY novel discovery: Bondi Junction SHOP fish market search discovered Mabuhey App (online Filipino grocery, located in Haymarket) via Maps search radius expansion.
- SYDNEY novel discovery: Castle Hill CAFE search discovered Hanmades Bakehouse Windsor in surrounding western suburbs.
- SYDNEY novel discovery: Castle Hill COMMUNITY search discovered Hoops Sports Performance Minchinbury (commercial basketball training academy under SERVICES) after verifying that the Castle Hill location was permanently closed and searching/enriching the operational Minchinbury branch.
- SYDNEY novel discovery: Castle Hill SERVICES search discovered Leoncia's Filipino Desserts & Yema (dessert shop under CAFE) in Castle Towers Shopping Centre.
- SYDNEY novel discovery: PanaDarna (Filipino bakery) is located inside The Kamayan in Rooty Hill — a hidden-within-another-business pattern.
- SYDNEY novel discovery: Glenmore Park COMMUNITY search discovered The Kamayan (Rooty Hill), a landmark Filipino restaurant in operation since 1995.
- SYDNEY novel discovery: Prestons SHOP search discovered Tapsi Supermarket, a new operational Filipino grocery store.
- SYDNEY novel discovery: Fairfield COMMUNITY search discovered Filipino Community Cooperative Ltd (Mount Pritchard, est. 1981), a non-profit cooperative operating the HNB (Hiyas ng Bayan) Long Day Care & Pre-School and promoting Filipino arts/culture.
- SYDNEY novel discovery: Fairfield COMMUNITY search discovered Tita's Cakes (Rooty Hill bakery) via Maps search radius expansion.
- SYDNEY novel discovery: St Clair COMMUNITY search discovered Holy Spirit Parish (St Clair) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass on the 1st Sunday of the month at 11:30 AM.
- Australian-Filipino Community Services (AFCS) is headquartered in Doveton, Victoria; it is not a Sydney-based organization despite search results sometimes associating it with NSW seniors support.
- SYDNEY: Kapamilya Asian Groceries (Campbelltown) has cancelled its ABN as of 2025 — confirmed permanently closed.
- SYDNEY: Halal butcheries in Western Sydney (Guildford, Fairfield Heights, Mount Druitt, Quakers Hill) consistently yield non-Filipino results — dominated by Middle Eastern/Pakistani/Afghan halal butchers.
- SYDNEY: Fish market searches across all suburbs consistently yield only non-Filipino seafood stores and duplicates from other suburbs — this search template has near-zero yield for new Filipino listings.
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered St. Ezekiel Moreno Convent, The Love of Jesus Christian Ministries, West Sydney Community Church, and Come To Jesus Church as verified Filipino-affiliated congregations.
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered Doonside Anglican Church (St. John's) as a verified Filipino-affiliated congregation (home base for Renew Filipino Ministries).
- SYDNEY novel discovery: Doonside/Glendenning CHURCH search discovered St John Vianney Parish as a verified Filipino-affiliated Catholic parish hosting Tagalog-English bilingual masses and Simbang Gabi.
- SYDNEY novel discovery: Seven Hills/Arndell Park CHURCH search discovered Church of the Living God as a verified Filipino-affiliated congregation.
- SYDNEY novel discovery: Mount Druitt CHURCH search discovered Iglesia ni Cristo Minchinbury, Sacred Heart Catholic Church (Mt Druitt South), and Holy Family Catholic Parish (Mt Druitt) as verified Filipino-affiliated congregations.
- SYDNEY novel discovery: Mount Druitt CHURCH search discovered El Shaddai DWXI PPFI - El Shaddai House as a verified Filipino-affiliated charismatic congregation and administrative center.
- SYDNEY novel discovery: Mount Druitt/Prospect CHURCH search discovered Filoship Connect Church (NSW Filipino Adventist Church) in Prospect as a verified Filipino-affiliated Seventh-day Adventist congregation.
- SYDNEY novel discovery: Glenmore Park/Penrith CHURCH search discovered St Nicholas of Myra as a verified Filipino-affiliated Catholic parish hosting the monthly Filipino Mass and Our Lady of Peñafrancia devotions.
- SYDNEY: Our Lady of Lourdes Catholic Church in Seven Hills is verified Filipino-affiliated, whereas Our Lady of Lourdes Catholic Church in Baulkham Hills has no local Filipino services or community groups.
- SYDNEY: Search for Filipino Christian churches in Eastern Suburbs (e.g., Bondi Junction) yields zero local storefronts, expanding to CBD/Haymarket (e.g., Saint Peter Julian's Church) or Indonesian ministries.
- SYDNEY novel discovery: Eagle Vale CHURCH search discovered Mary Immaculate Catholic Church (Eagle Vale) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY: Mary Immaculate Parish (Quakers Hill) does not host a Filipino Mass and is not Filipino-affiliated, whereas Mary Immaculate Parish (Bossley Park) and Mary Immaculate Catholic Church (Eagle Vale) are both verified Filipino-affiliated; use suburb suffixes to distinguish.
- SYDNEY novel discovery: Toongabbie/Girraween CHURCH search discovered Jesus Our Banner Christian Church as a verified Filipino-affiliated congregation led by Pastors Omy and Jordan De Vera.
- SYDNEY novel discovery: Toongabbie CHURCH search discovered St Anthony of Padua Catholic Church (Toongabbie) as a verified Filipino-affiliated Catholic parish with an active Filipino choir.
- SYDNEY novel discovery: Wentworthville CHURCH search discovered Our Lady of Mount Carmel Catholic Church (Wentworthville) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Guildford CHURCH search discovered Our Lady of the Rosary Parish Kellyville (Kellyville) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Fairfield Heights/Cabramatta CHURCH search discovered Sacred Heart Catholic Church, Cabramatta as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass.
- SYDNEY novel discovery: North Sydney CHURCH search discovered Holy Spirit Catholic Church North Ryde (North Ryde) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Chatswood CHURCH search discovered St. Michael's Catholic Parish (Lane Cove) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Chatswood CHURCH search discovered Our Lady of Dolours Catholic Church (Chatswood) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Culture Mass.
- SYDNEY novel discovery: Chatswood COMMUNITY search discovered Filipino Chaplaincy Chatswood Parish (FCCP) as a verified Filipino-affiliated community organization and merged/updated Manila Sari-Sari Store.
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
- SYDNEY novel discovery: Manly CHURCH search discovered St Mary's Catholic Church (Manly) as verified Filipino-affiliated, hosting a dedicated Filipino Family Group morning tea on the 2nd Sunday of the month after the 10:30 am Mass.
- SYDNEY: Searches for "Sutherland" church listings can return St Therese Parish (Mascot) as a false positive location match due to its address on "Sutherland Street" (which has a verified Filipino Mass), whereas St Patrick’s Catholic Church in the actual suburb of Sutherland has no Filipino affiliation.
- SYDNEY novel discovery: Epping/Carlingford CHURCH search discovered St Kevin's Catholic Church (Eastwood) as a verified Filipino-affiliated parish hosting Tagalog Masses on the 1st Sunday of the month at 4:00 PM and the 3rd Sunday of the month at 11:45 AM.
- SYDNEY novel discovery: Erskine Park CHURCH search discovered Our Lady of the Way Parish (Emu Plains) hosting a monthly Filipino Mass on the 3rd Sunday at 12:00 PM.
- SYDNEY novel discovery: Casula/Horningsea Park CHURCH search discovered Holy Spirit Catholic Church Carnes Hill as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass.
- SYDNEY novel discovery: Glenmore Park/St Clair CHURCH search discovered Holy Spirit Parish (St Clair) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass on the 1st Sunday of the month at 11:30 AM.
- SYDNEY novel discovery: Minto CHURCH search discovered Our Lady of Mount Carmel Catholic Church (Varroville) as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass on the 3rd Sunday at 11:15 AM.
- SYDNEY novel discovery: Macquarie Fields CHURCH search discovered St Anthony's Catholic Church (Marsfield) hosting a monthly Filipino Mass on the 4th Sunday of the month at 11:00 am.
- SYDNEY novel discovery: Lidcombe/Merrylands CHURCH search discovered St Joachim’s Catholic Church as a verified Filipino-affiliated congregation hosting the annual Feast of Our Lady of Peñafrancia.
- SYDNEY novel discovery: Merrylands CHURCH search discovered St Margaret Mary's Parish as a verified Filipino-affiliated congregation hosting Simbang Gabi Christmas dawn masses.
- SYDNEY novel discovery: Lidcombe/Greenacre CHURCH search discovered St John Vianney Catholic Church (Greenacre) as a verified Filipino-affiliated parish hosting a monthly Filipino Mass on the 4th Sunday of the month.
- SYDNEY novel discovery: Marsden Park CHURCH search discovered Our Lady of Czestochowa Queen of Poland (Polish War Memorial Chapel) in Marayong as a verified Filipino-affiliated congregation hosting a monthly Filipino Mass on the 3rd Friday of the month at 8:00 PM.
- SYDNEY novel discovery: Marsden Park CHURCH search discovered St Luke’s Catholic Parish Marsden Park as a verified Filipino-affiliated congregation with active Filipino community participation and fundraisers.
- SYDNEY novel discovery: Kingswood/St Marys CHURCH search discovered Our Lady of the Rosary Church, St. Mary’s as a verified Filipino-affiliated parish hosting a monthly Filipino Mass on the 1st Sunday of the month at 11:30 AM.
- SYDNEY novel discovery: West Hoxton CHURCH search discovered Saint John the Baptist Catholic Church (Bonnyrigg Heights) as a verified Filipino-affiliated parish hosting a Tagalog Mass on the 4th Sunday of the month at 5:30 PM.
- SYDNEY novel discovery: West Hoxton CHURCH search discovered Our Lady of Victories Horsley Park as a verified Filipino-affiliated parish hosting a Filipino Mass on the 4th Sunday of the month at 11:00 AM.
- SYDNEY novel discovery: Edmondson Park CHURCH search discovered St Anthony of Padua Catholic Church (Austral), St. Francis Xavier Catholic Church (Lurnea), and St Therese's Catholic Church (Sadleir) as verified Filipino-affiliated congregations hosting a Filipino Mass on the 4th Sunday of the month at 11:00 AM.
- SYDNEY novel discovery: Guildford/Fairfield CHURCH search discovered Our Lady of the Rosary Catholic Church (Fairfield) as a verified Filipino-affiliated Catholic parish hosting a monthly Filipino Mass on the 4th Sunday of the month at 11:00 AM.
- SYDNEY novel discovery: Winston Hills CHURCH search discovered Saint Paul's Catholic Church (St Paul the Apostle) as a verified Filipino-affiliated parish hosting a monthly Filipino Mass on the 2nd Sunday of the month at 11:00 AM.
- SYDNEY novel discovery: Campbelltown CHURCH search discovered Catholic Church of St Paul of the Cross and the Immaculate Conception (Dulwich Hill) hosting a monthly Filipino Mass on the 1st Sunday at 11:30 AM via Maps search radius expansion.
- SYDNEY novel discovery: Blacktown COMMUNITY search discovered Filipino Sports Arts & Recreational Club (FILSPARC) and CFC ANCOP Australia.
- SYDNEY novel discovery: Campbelltown COMMUNITY search discovered Arts & Culture Innovation Central (ACI Central) and Pinoy Basketball Australia Originals - Minto NSW.
- SYDNEY novel discovery: Campbelltown COMMUNITY search discovered NARRA Cooperative Ltd (parent organization of ACI Central), a Filipino-Australian charity and co-operative.
- SYDNEY novel discovery: Merrylands COMMUNITY search discovered PICPA Australia (Philippine Institute of Certified Public Accountants Australia) as a verified Filipino professional association.
- SYDNEY novel discovery: Lidcombe COMMUNITY search discovered Philippine Australian Sports & Culture Inc. (Fiesta Kultura), organizer of the Grand Philippine Fiesta Kultura (Australia's largest single-day Filipino cultural festival at Fairfield Showground, annually in October).
- SYDNEY novel discovery: COMMUNITY search discovered United Architects of the Philippines - Australia Chapter (UAP Australia) representing Filipino architects in Australia/NZ.
- SYDNEY novel discovery: COMMUNITY search discovered Filipino Student Association of UTS (FSA UTS).
- SYDNEY: The Filipino Saturday School, Hills of Zion City Church Sydney, and PACSI programs all share the physical venue of the Rooty Hill Senior Citizens Centre at 34A Rooty Hill Rd S.
- SYDNEY novel discovery: Doonside COMMUNITY search discovered Filipino Walkers (Heart Foundation walking group meeting Saturday mornings at Nurragingy Reserve).
- SYDNEY novel discovery: Granville COMMUNITY search discovered St Mark's Anglican Church Granville (Filipino Service) led by Rev. Retchie Salvador.
- SYDNEY novel discovery: Quakers Hill COMMUNITY search discovered Joflow Basketball Academy (Kings Park) as a verified Filipino-affiliated sports academy under SERVICES.
- SYDNEY novel discovery: Hurstville COMMUNITY search discovered Sydney Kali Academy (Hurstville) and Bakbakan Martial Arts Centre (Marrickville, operating under Power Core MMA) as verified Filipino-affiliated martial arts schools under SERVICES.
- SYDNEY novel discovery: Mount Druitt COMMUNITY search discovered Christ To The Nations Ministries (Ganny O. Eco) as a verified Filipino-affiliated congregation.
- SYDNEY novel discovery: SERVICES search discovered Clean and Hale Services (Rooty Hill), a verified Filipino-affiliated cleaning service founded by registered nurses.


## Known Pitfalls
<!-- Failure modes, validation errors, and how to avoid them -->
- City Casing Case-Sensitivity: Firebase SQL Connect queries are case-sensitive (e.g. `city: { eq: "SYDNEY" }`). Any listings created or restored with capitalized or lowercase city names (e.g., `Sydney` or `sydney`) will be hidden from client browse/search results. Ad-hoc scripts and ingestion agents must always normalize city values to uppercase (as defined in the frontend's City enum).
- Listing ID Drift: Re-creating listings from backup generates new database UUIDs. Any external files or trackers referencing the old listing IDs will become obsolete and must be regenerated or updated.
- The existing city listings cache JSON file is written as a single line, making simple grep query matches prone to truncation or failure; always use the dedicated duplicate check script.
- The agent_check_duplicate.py script will skip name-based duplicate matches if any URL is passed to --url but the cached listing has no social URLs (all null); omit --url or use specific parameters (e.g. --facebook-url) to enable name-matching and merge detection.
- The duplicate check script (agent_check_duplicate.py) skips name-based match when a website URL is passed to --url because listing_urls only includes social media URLs; omit --url or use specific parameters to ensure name-based match is evaluated.
- The GraphQL UpdateListingData mutation expects tags as a comma-separated String, not a list, whereas CreateListing automatically normalizes a list of tags.
- The name normalization function does not replace curly apostrophes (') with straight apostrophes ('), meaning duplicate checks (e.g. for Tita's Cakes vs Tita's Cakes) will fail unless inputs are normalized first.
- The Google Maps detail panel may render operating hours with day names and times on separate lines, causing `parse_maps_opening_hours` to return `None`; clean the text to 'Day: Hours' format before parsing.
- The GraphQL CreateListing and UpdateListingData mutations expect `operatingHours` as a serialized JSON String, not a JSON object/map; passing a raw dictionary will trigger a GraphQL INVALID_ARGUMENT execution error.
- The GraphQL CreateListing mutation requires a non-empty `description` string; omitting it or setting it to null will trigger an `INVALID_ARGUMENT: $description (String) is missing` execution error.
- The `agent_check_duplicate.py` name matching is highly sensitive to naming variations; Google Maps results containing descriptive suffixes (e.g., "The Bangketa Grocer - Filipino shop" vs "The Bangketa Grocer") will fail to match, so you should check with the base/shortened name if duplicate checks fail.
- The GraphQL `CreateListing` mutation variables do not accept a `suburb` key; passing it will trigger an `INVALID_ARGUMENT` execution error indicating `$suburb is not expected`.
- The GraphQL `UpdateListingData` mutation does not accept `name` as a variable; passing it will trigger an `INVALID_ARGUMENT: $name is not expected` execution error.
- Separate parishes of the same dedication (e.g., Mary Immaculate Catholic Church in Bossley Park vs Eagle Vale) share identical names; append the suburb or location suffix to the listing name to prevent incorrect name-based duplicate collisions.
- When Google Maps has no structured hours for a listing (common for churches, community orgs, markets), extract schedule information from the listing's description and gathered web/social text. Store as standard `operatingHours` JSON. If Maps hours also exist, merge with ` | ` separator per day (Maps hours first, then description context). Tag listings with `description-hours` for provenance tracking.
- The local city listings cache and database deduplication query limits are set to 2000 to prevent false-negative duplicate checks and redundant insertions in cities with more than 1000 listings (e.g., Sydney).
- For sub-groups (like choirs) sharing a physical location with a church, do not use the Google Maps URL as the sourceUrl; use the website or profile URL to prevent the deduplication engine from merging it into the church listing.
- Parenthesis Name-Matching Failure: The name-matching duplicate check is sensitive to parenthetical qualifiers (e.g., "Filipino Women Support Group Macarthur" vs "Filipino Women Support Group (Macarthur)"); manually verify the local listings cache using grep or database queries when checking names with potential parenthetical suffixes.
- Google Maps search results can sometimes return corrupt or placeholder pins with a literal dot (.) as the business name, sharing coordinates/addresses with other verified businesses; reject these during verification.
- Patching builtins.open in unit tests intercepts all Python standard library file accesses (e.g., gettext loading locale catalogs during argparse initialization); mock script-specific open (e.g., agent_graphql_push.open) instead.
- Name-matching duplicate checks fail when listings have varying suffixes (e.g. 'Faith in Christ Fellowship Macarthur' vs 'Faith in Christ Fellowship'), making exact social media or website URL comparison crucial for catching name-variant duplicates.
- Name-matching duplicate checks are highly sensitive to spacing and concatenation variations (e.g. 'FastboxPH' vs 'FASTBOX PH'), making URL-based comparison critical for identifying these duplicates.
- URL-based duplicate checks can fail if there are minor protocol or subdomain variations (e.g., http vs https, or presence/absence of www.); normalize URLs to base domains or check via name match if a candidate URL fails to trigger a duplicate match.
- Web search queries combining "Filipino" or "Pinoy" with "Sydney" can return false-positive candidates located in Sydney, Nova Scotia, Canada (e.g. probate notifications or local business filings); verify the country/state and address before evaluating.
- Google Maps search results for service providers with no physical address can return multiple candidate pins mapped to the exact same suburb centroid coordinates (e.g., Lidcombe centroid -33.8482439, 150.9319747); verify and reject these if they lack distinct addresses, websites, or verified Filipino affiliation.
- Google Maps URL duplicate checks can fail if the cached sourceUrl uses the place_id format (e.g., /maps/place/?q=place_id:...) while the candidate URL uses the browser path format (e.g., /maps/place/Name/data=...); database-level checks during push will resolve it via exact sourceUrl match of the formatted place_id payload.
- Substring searches on the local listings cache file (e.g., searching for "Descanso" or "Smoky") are a robust manual fallback to identify name-variant duplicates when the duplicate check script fails to match due to spacing or suffix differences.
- A business relocation (e.g., Sydney Cebu Lechon moving Newtown → Blacktown) that subsequently has its Google Maps page marked "Permanently closed" along with all official web domains and online ordering pages returning 404/no host signals a final permanent closure; update the status of the existing listing to CLOSED_PERMANENTLY.



