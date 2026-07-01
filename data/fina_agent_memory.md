# Fina Agent Memory

> Self-evolving shared memory for Fina discovery and enrichment agents.
> Agents read this file at session start and update it post-execution.
> Maximum budget: **500 lines**. Agents must aggressively prune stale entries.
> Supersession rule: new insights that contradict existing entries replace them.
> Format: concise bullet points (one line per insight). No prose paragraphs.

## Platform & Browser Insights
<!-- Reusable facts about platforms, anti-bot patterns, and browser behaviour -->
- On Facebook profile pages, the contact/about directory sub-page sk=directory_privacy_and_legal_info (Privacy and legal info) often contains a detailed 'Service Description' text block, which is a prime source for synthesising community group descriptions.
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
- When an Instagram profile contains multiple bio links (indicated by "and 1 more" or similar text), clicking the links button opens a modal dialog listing all the URLs; extract the additional URLs (e.g. websites, contact forms) from this modal snapshot.
- Candidate websites using Cloudflare security verification or Turnstile challenges will block browser automation; fallback to already loaded homepage content or other social media profiles to extract contact information.
- The Google Maps search input ID can be dynamic; use document.querySelector('input[name="q"]') as a robust fallback selector to focus and clear the input before typing.
- In Google Maps browser scraping, operating hours can be reliably extracted day-by-day by querying buttons with an aria-label containing "Copy open hours" and removing the copy suffix.
- Navigating the primary browser page away from a Google Maps search results view resets the loaded results list, requiring re-running the scroll container logic to rebuild the candidate queue upon returning.
- In Google Maps detail panel, the phone number button's data-item-id attribute contains the phone number itself (e.g. phone:tel:0430373884); use the prefix selector button[data-item-id^="phone:tel:"] to locate and extract it.
- Business websites can contain social media buttons with empty/placeholder `href` attributes (""); verify profile existence via search if links are blank.
- Business website social links may point to template placeholder paths (e.g. /website/social/facebook) that redirect to the platform's generic homepage instead of a specific business profile; verify profile handles before extracting follower counts.
- When a business found via web search does not have a dedicated Google Maps listing under its name, search Google Maps for its physical street address to resolve coordinates.
- In Google Maps details panel, if the "Copy open hours" button is absent, the weekly hours table can be extracted by querying the first `table` element and mapping cell values of each `tr` row to standard day abbreviations.
- When extracting Google Maps opening hours from the weekly table element, join the row text values using newlines (\n) instead of commas to ensure the day parser correctly splits and identifies the day name prefixes.
- On macOS, the browser subagent (`open_browser_url`) fails with "local chrome mode is only supported on Linux". Use direct Chrome DevTools MCP tool calls instead.
- When `evaluate_script` is denied by security/permission policies, scroll the Google Maps search results feed by clicking the Results heading and issuing multiple "PageDown" keyboard events via the `press_key` tool.
- When `evaluate_script` is denied by security/permission policies, the redirected/current Google Maps URL can be retrieved via `list_pages` to inspect the URL of the selected tab.
- When `evaluate_script` is denied by security/permission policies, use the `take_snapshot` tool to retrieve the page elements from the Google Maps details panel.
- When `evaluate_script` is denied by security/permission policies, elements can be clicked by taking a snapshot via `take_snapshot` to obtain their `uid` and then using the `click` tool with that `uid`.
- A business listing showing 'Closed' on all days in Google Maps weekly hours may be undergoing a scheduled temporary closure; check their social media profiles for temporary closure notices before marking them permanently closed.
- Google Maps Place ID query (`place_id:ChIJ...`) can resolve to the main commercial building instead of the tenant business when the tenant does not have a dedicated Maps pin. Fallback to independent web search and directory registries.
- Google Maps search query for a business with no pin or listing can redirect to a completely unrelated business name; always verify the loaded panel's heading to prevent extracting incorrect information.
- Facebook and Instagram web page views may present a login overlay dialog modal when browsed without a login; click the Close button on the modal to dismiss it and view the profile page and follower counts.
- Facebook profile URLs using a slug-to-ID structure (e.g. /people/Slug-Name/ProfileID) will resolve to the page associated with the ProfileID even if the Slug-Name belongs to a completely different organization; verify the loaded page's heading and branding to confirm identity.
- Targeting the virtual environment executable (e.g. ./.venv/bin/python3) inside nested python subprocess calls ensures installed packages such as httpx are resolved correctly.
- When Google Maps search suggestions/autocomplete dropdown is active, pressing Enter on the search input may select a suggestion from history instead of searching the typed query; clear the input via the Close button first and execute by clicking Search directly.
- When executing python code containing emojis or special character surrogates on macOS, passing them directly via command-line arguments can raise UnicodeEncodeError; write the payload to a JSON/text file first and load it within python to bypass shell encoding limitations.
- Targeting Facebook's native page search directory (e.g. facebook.com/search/pages/?q=<name>) via browser navigation is highly effective for discovering business profiles that do not rank in external search engines or use numeric IDs.
- In the Google Maps details panel reviews tab, if keyboard navigation or scrolling fails to load more reviews, click on a visible review text body element to focus the scrollable pane, then press PageDown sequentially to trigger the lazy loading of additional reviews.
- In Chrome DevTools MCP, clicking on interactive elements that trigger heavy page navigation or panel updates on Google Maps with includeSnapshot set to true can cause the page to reset to about:blank; call click with includeSnapshot set to false instead, followed by a separate take_snapshot call.
- Facebook reviews can be extracted from the /reviews tab or URL of the page, where they appear as user recommendation posts rather than standard numbered star ratings.
- WordPress Elementor websites may have content hidden or delayed in the Chrome DevTools accessibility tree snapshot; fetching and inspecting the raw HTML via read_url_content is a reliable fallback to retrieve footer social links and contact details.

## Discovery Patterns
<!-- What works and what doesn't when searching for Filipino businesses -->

### Search Effectiveness
- Suburb-level searches for Filipino student associations consistently yield zero results, as student organizations in Sydney are strictly university-based (e.g. USYD, UNSW, UTS, Macquarie, WSU).
- `search_web` with `site:facebook.com` or `site:instagram.com` for niche suburb queries returns aggregated summaries rather than direct profile URLs — most candidates come from Round 4 (Google Maps browser).
- Multi-branch organizations or churches often share a single national website or regional Facebook page; evaluate physical address and branch name rather than relying solely on URL matches to prevent incorrect duplicate detections.
- Searches containing "Filipino" can return Sanfilippo Children's Foundation as a false positive due to substring similarity; Sanfilippo is a genetic disease charity.
- Google Maps searches for community associations in low-density suburbs can return results from other states (e.g., VIC, QLD, NT); verify the state or telephone area code (e.g., (02) for NSW).

### False-Positive Filtering Heuristics
- Business names containing "Pacific" (e.g. AK Pacific Repairs) often refer to Pacific Islander/Oceania communities rather than Filipino, requiring active verification of ownership.
- Business owners addressing reviewers with titles like 'Sis.' or 'Bro.' (e.g., 'Thank you Sis. Nette') in Google Maps review replies is a strong cultural signal for Filipino/Pinoy community or church affiliation.
- A candidate business website or social page may list a telephone number with a +63 (Philippines) country code prefix despite having an Australian address; this is a strong positive signal for Filipino affiliation.
- Facebook pages displaying language support details (e.g., 'English' and 'Filipino language') under profile details is a highly reliable positive signal for confirming Filipino community or business affiliation.
- Google Maps or third-party reviews containing explicit community or ethnic statements (e.g., 'You need to be a Filo' or references to 'kabayan'/'kababayan') are highly reliable positive signals for confirming Filipino affiliation.
- Inspecting owner/founder names on website 'About Us' pages, ABN registries, or linked personal socials (e.g., LinkedIn) is highly effective for verifying Filipino ownership or filtering non-Filipino false positives.
- Third-party business directories or quoting platforms (e.g. Oneflare) can contain explicit Filipino affiliation statements even if the official website is generic.
- Business directories (like Cybo) listing 'Filipino' under supported languages can be auto-generated or inaccurate; verify via official social pages, websites, or reviews.
- Verifying generic trading names on local directories such as everythingindian.com.au helps identify South Asian or other non-Filipino false positives.
- The "Support Pinoy's in Australia" directory (supportpinoys.com.au) lists several non-Filipino businesses; always verify ABN registration and owner names.
- Web search queries combining "Filipino" or "Pinoy" with "Sydney" can return false-positive candidates located in Sydney, Nova Scotia, Canada; verify the country/state and address.
- Spanish tapas bars or venues (e.g. named "Una Más" or serving "tapas") can be false positives due to historical naming and culinary overlaps, despite serving strictly Spanish or Mediterranean cuisine.


### Church & Religious Search Patterns
- Sydney church searches near multicultural hubs return South Asian (Tamil, Malayalam, Hindi, Sinhala), Croatian, Indonesian, African, Hispanic, and general charismatic groups as false positives; verify congregation language and leadership.
- Bread of Life Christian Church (under "1503 Mission Network") is Taiwanese-affiliated and CCCS is Samoan-affiliated; neither is Filipino.
- Maronite, Chaldean, Coptic, Slovenian, and Melkite Greek Catholic churches serve non-Filipino diaspora communities.
- General Australian churches listing the Philippines as an overseas missionary/charity destination are not Filipino-affiliated unless they host dedicated local services or ministries.
- Web search queries combining a local parish name with "Filipino" can return false-positive snippets from a parish of the same dedication in another country (e.g., California); verify Australian addresses and domains.
- Separate parishes of the same dedication (e.g., Mary Immaculate in Bossley Park vs Eagle Vale vs Quakers Hill) share identical names; append suburb to distinguish and prevent duplicate collisions.
- The Feast (Light of Jesus Family) prayer groups typically meet inside existing Catholic parishes, sharing the same physical address/place ID and merging during ingestion.
- Uniting Churches can host distinct, long-standing Filipino congregations, identifiable by dedicated 'Filipino Service' Facebook groups.
- Missionary and 'Partners in Missions' pages on local independent church websites are high-yield sources for confirming Filipino affiliation.
- Catholic diocesan directories and multicultural ministry records are highly reliable sources for retrieving specific Filipino Mass schedules and service times for churches or convents lacking Google Maps hours.

### Business & Services Search Patterns
- Independent websites are critical for discovering social media profiles of businesses that use numeric profile IDs (e.g., profile.php?id=...) which do not rank well in search queries.
- Google Maps listings can show a "Located in" tag referencing a food hall in a different suburb; check the physical address to verify the correct suburb.
- Sponsor directories on local Filipino sports league websites (e.g. PBA Originals) are high-yield sources for discovering new Filipino businesses.
- The FiloConnect directory (filoconnect.com.au) lists local Filipino-owned businesses but contains some placeholder/dummy contact details which must be verified.
- Candidates sharing a building address with established Filipino businesses can be verified via co-tagging, 'with', or 'at' mentions on Facebook.
- Service providers may advertise coverage in multiple states while being physically headquartered in another state; verify actual office address.
- Google Maps search results can return mock cleaning service pages generated by Calso Pty Ltd (Starworks) for demo/SEO purposes; reject these.
- Catering search templates in Google Maps return established restaurants across the entire metro area due to radius expansion, leading to high duplicate rates.
- General food/catering candidates may be non-Filipino-owned (e.g., Vietnamese, Indian); verify registered business owner names or ABN/ASIC registry.
- PanaDarna (Filipino bakery) is located inside The Kamayan in Rooty Hill — a hidden-within-another-business pattern to watch for.


## Enrichment Patterns
<!-- Techniques and observations from the listing enrichment workflow -->
- Instagram profiles for alcohol/liquor brands are age-restricted (18+) and cannot be viewed without login; follower counts and posts are inaccessible to unauthenticated Chrome DevTools sessions.
- Facebook pages for some businesses return "This content isn't available at the moment" when accessed without login; this is not a closure signal — the page may be restricted, renamed, or require authentication.
- When Google Maps does not display social media links in the business info panel, the business's own website footer often contains Facebook, Instagram, TikTok, YouTube, and LinkedIn links — always check the website as a fallback.
- TikTok profiles may present a CAPTCHA challenge on first load in Chrome DevTools, blocking follower count extraction; this is an anti-bot measure that cannot be bypassed without human intervention.
- When a business has global or regional social media pages under the same brand, verify page location/contact details before extracting follower counts to prevent incorrect data associations.
- Stored social media URLs in task data can sometimes point to a business with the exact same name but located in another country (e.g. Chicago, USA instead of Sydney, Australia); cross-reference location details and address to confirm, and retrieve the correct URL from the official local website footer.
- When a stored social media URL returns "Page not found" or "Content not available", check for handle suffix variations (e.g., .sydney vs .syd) or typos to locate the correct active page.
- When a stored social media profile returns a 404 or not found page, cross-referencing the official business website footer or contact links is highly effective for discovering the correct active social media handles.
- For Filipino non-profit or community associations with no Google Maps pin, local ethnic news publications (e.g., Munting Nayon) are high-yield sources for historical facts and activities needed to synthesise descriptions.
- For community and religious associations with no commercial reviews, public community news (e.g., Catholic Outlook) and local/state parliament recognition statements serve as high-quality sources for web reviews and testimonials.
- Instagram profiles can contain direct links to the Facebook page in the link or bio section; checking these links is highly effective for discovering the business's Facebook page when standard web search fails to return it.
- Stored business social URLs can sometimes match a case-insensitive handle that belongs to a personal profile instead of the official page (e.g., `/Ausphin` vs `/AusphinGroup`); verify page contents or check their Linktree/website for the correct corporate handle.
- Stored social media URLs may redirect to or load the profile of a collaborating partner, sponsor, or host organisation; verify the page identity and branding before extracting metrics like follower counts or reviews to avoid mixing distinct entities.
- Hostinger or Astro-based business websites may pack their official social links and metadata inside `<script type="application/ld+json">` or `astro-island` component properties; extract these using regular expressions or JSON parsing when standard DOM selectors fail.
- WordPress Divi theme websites may store social/external link destinations in a JavaScript configuration array named `et_link_options_data`; run `grep_search` on the page source to extract the URLs.
- When an affiliated business listing lacks reviews or hours on its own Google Maps listing, check if it operates under or shares a physical space with an umbrella/parent brand (e.g. Power Core MMA for Bakbakan Martial Arts); extracting from the parent's panel is a valid and robust fallback if the relationship is confirmed.
- Food trucks and market vendors (e.g. Bar-B-Skew) often lack a permanent Google Maps pin or fixed operating hours; extract descriptions, contact details, reviews, and follower counts directly from their Facebook and Instagram profiles.
- When Google Maps hours show a business is closed on certain days or has shorter hours, cross-reference their official website's hours section, which may list more extensive active operating hours.
- When a business website returns a Cloudflare block page or Turnstile challenge and ASIC registry records indicate historical voluntary deregistration from previous years, classify the business status as CLOSED_PERMANENTLY.
- Squarespace-based business websites often embed structured `ld+json` schema blocks for `LocalBusiness` and `Organization` containing precise `openingHours` and `sameAs` social media links, serving as an excellent source of schedule and contact details.
- GoDaddy Website Builder (GoCentral) sites render structured widgets with unique `data-ux` attributes; extracting all readable text nodes while filtering stylesheet and script tags is highly effective for locating hidden weekly service schedules and contact details.
- A business marked 'Permanently closed' on Google Maps may still list active hours and locations on its official website; trust the Google Maps closure banner as the strongest status signal.
- When a listing's sourceUrl points to a multi-purpose venue (e.g. The Epping Club) rather than a dedicated business pin, extract reviews and contact details from the business's social profiles or search for the specific business name on Google Maps to avoid capturing the venue's reviews and opening hours.
- When a business website obfuscates its official email address on contact pages (e.g., using asterisks or Javascript protection), performing a web search for the domain name combined with 'email' is highly effective for retrieving the plain email address.
- For businesses operating within a host clinic or venue (e.g., 'Operating within Allied Health Clinic'), the host clinic's Google Maps weekly hours can serve as a proxy/bound for the business's schedule when its own listing lacks hours.

## Events Patterns
<!-- Event discovery insights: date parsing quirks, platform event formats, classification edge cases -->

## City Intelligence
<!-- City-specific operational knowledge: aggregate geographic patterns, high-yield zones -->

### Sydney — Geographic Saturation
- All 60 suburbs for CAFE and SHOP categories are fully saturated at the city-level task tier. Filipino food/retail businesses are heavily concentrated in Western Sydney (Blacktown, Rooty Hill, Doonside, Mount Druitt, Fairfield, Parramatta corridor) with secondary clusters in South-West (Campbelltown, Ingleburn, Liverpool).
- Eastern/Northern coastal suburbs (Bondi Junction, Manly, Cronulla, North Sydney, Macquarie Park, Sydney Olympic Park) have zero local Filipino storefronts — Maps results always expand to Western Sydney duplicates.
- Western Sydney suburbs (Parramatta, Granville, Lidcombe, Guildford, Merrylands) have a high density of established duplicate churches; search yields for new Filipino congregations in this corridor are very low.

### Sydney — Low-Yield Search Patterns (Consistently Zero New Results)
- Small Western Sydney residential suburbs (e.g. Oakhurst, Glendenning, Hassall Grove) have high Filipino populations but lack suburb-specific community organizations; searches resolve to regional duplicates.
- Northern Sydney suburbs (Epping, Ryde, Carlingford) yield zero new Filipino religious groups/communities — dominated by Korean/Chinese congregations.
- Northern Sydney (Ryde, Epping) and Western Sydney Korean hub (Lidcombe) hair salon/beauty searches are dominated by Korean/Japanese salons — zero Filipino results.
- South-West residential suburbs (Prestons, Hoxton Park, Casula, Ingleburn) yield zero local Filipino hair salons — dominated by South Asian/Middle Eastern salons.
- Western Sydney residential suburbs yield zero local Filipino mechanics — dominated by Indian/South Asian, Assyrian/Middle Eastern workshops or general franchises.
- Marsden Park/Melonba/Tallawong and South Asian hubs (e.g. Wentworthville) hair salon searches are dominated by South Asian (Indian), Persian, and Anglo-owned salons — zero Filipino results.
- Suburb-level SERVICES (catering) searches in Western Sydney expand to surrounding regional duplicates due to Maps search radius expansion — total duplicate saturation.
- Halal butcheries in Western Sydney (Guildford, Fairfield Heights, Mount Druitt, Quakers Hill) consistently yield non-Filipino results — dominated by Middle Eastern/Pakistani/Afghan halal butchers.
- Fish market searches across all suburbs consistently yield only non-Filipino seafood stores and duplicates — near-zero yield for new Filipino listings.
- Cleaning service search templates yield high false positives (general local cleaning services and national franchises) when no local Filipino cleaning services exist.
- Church/religious searches in Eastern Suburbs (e.g., Bondi Junction) yield zero local results, expanding to CBD/Haymarket or Indonesian ministries.
- Balikbayan box search templates yield high numbers of non-Filipino national couriers; genuine Filipino cargo agents are highly clustered in Western Sydney.

### Sydney — Notable Operational Facts
- The Filipino Saturday School, Hills of Zion City Church Sydney, and PACSI programs all share the physical venue of the Rooty Hill Senior Citizens Centre at 34A Rooty Hill Rd S.
- APCO NSW officially rebranded to PAMAI in 2025 led by Ronna Guzman; former officers formed PAGASA Inc. in Liverpool. Both remain active.
- Active community associations in South West Sydney (e.g., PAGASA Inc, Visayan Association of Australia) often share common leadership teams and contact emails; identifying shared contacts helps trace sister organizations.
- Pinoy Basketball Australia Sydney (PBAS) and PBA Originals (PBAO) are two distinct Filipino basketball associations operating at the same venue (Minto Indoor Sports Centre) and must not be merged.
- Kapamilya Asian Groceries (Campbelltown) has cancelled its ABN as of 2025 — confirmed permanently closed.
- Australian-Filipino Community Services (AFCS) is headquartered in Doveton, Victoria; not a Sydney-based organization.
- Bayanihan Cargo Services (bayanihan.com.au) is headquartered in QLD/VIC, and J. Cordon Express (jcordonexpress.com) is headquartered in Hallam, VIC; neither has a local Sydney depot.
- White Pages database entries showing "Catholic Church" at Lord Howe Drive, Green Valley are erroneous; no physical parish exists at that location.
- Liverpool Catholic Club (Prestons) is a general family/social club and Ingleburn RSL Club is a general RSL; neither is Filipino-affiliated despite review snippets mentioning Filipino activities.
- Mekeni Food (Blacktown) is an alternative name or duplicate listing for Pinoy Station (24 Main St, Blacktown).


## Known Pitfalls
<!-- Failure modes, validation errors, and how to avoid them -->
- City Casing Case-Sensitivity: Firebase SQL Connect queries are case-sensitive (e.g. `city: { eq: "SYDNEY" }`). Always normalize city values to uppercase.
- Listing ID Drift: Re-creating listings from backup generates new database UUIDs. External files referencing old IDs will become obsolete.
- The existing city listings cache JSON file is written as a single line; always use the dedicated duplicate check script.
- The agent_check_duplicate.py script will skip name-based duplicate matches if any URL is passed to --url but the cached listing has no social URLs (all null); omit --url or use specific parameters to enable name-matching.
- The duplicate check script skips name-based match if the candidate URL is a social media link but does not match any URL in the cache (e.g., /p/ profile pages vs username pages); run without --url to fallback to name-based matching.
- The duplicate check name matching is highly sensitive to naming variations: descriptive suffixes, spacing/concatenation (e.g. 'FastboxPH' vs 'FASTBOX PH'), parenthetical qualifiers, and curly vs straight apostrophes all cause match failures. Use shortened names, URL-based comparison, or substring searches on the cache file as fallbacks.
- The GraphQL UpdateListingData mutation expects tags as a comma-separated String, not a list, whereas CreateListing automatically normalizes a list of tags.
- The Google Maps detail panel may render operating hours with day names and times on separate lines, causing `parse_maps_opening_hours` to return `None`; clean the text to 'Day: Hours' format before parsing.
- The GraphQL CreateListing and UpdateListingData mutations expect `operatingHours` as a serialized JSON String, not a JSON object/map.
- The GraphQL CreateListing mutation requires a non-empty `description` string; omitting it triggers an INVALID_ARGUMENT error.
- The GraphQL CreateReview mutation does not accept a `source` field. Valid fields: `listingId`, `externalSourceId`, `authorName`, `rating`, `text`, `publishedDate`.
- The GraphQL `CreateListing` mutation does not accept `suburb`, and `UpdateListingData` does not accept `name`.
- When Google Maps has no structured hours for a listing (common for churches, community orgs), extract schedule information from the listing's description and web/social text. Tag with `description-hours` for provenance tracking.
- The local city listings cache and database deduplication query limits are set to 2000 to prevent false-negative duplicate checks in cities with 1000+ listings.
- For sub-groups (like choirs) sharing a physical location with a church, do not use the Google Maps URL as the sourceUrl; use the website or profile URL to prevent deduplication merging.
- Google Maps search results can sometimes return corrupt or placeholder pins with a literal dot (.) as the business name; reject these.
- Patching builtins.open in unit tests intercepts all Python standard library file accesses; mock script-specific open (e.g., agent_graphql_push.open) instead.
- URL-based duplicate checks can fail with minor protocol or subdomain variations (http vs https, www vs non-www); normalize URLs or check via name match as fallback.
- Google Maps URL duplicate checks can fail if the cached sourceUrl uses the place_id format while the candidate URL uses the browser path format; database-level checks during push resolve via exact sourceUrl match.
- A business relocation that subsequently has its Google Maps page marked "Permanently closed" along with all domains returning 404 signals a final permanent closure; update status to CLOSED_PERMANENTLY.
- A cancelled ABN registry entry does not necessarily mean a business is closed; cross-reference active reviews and operational status on Google Maps or social media before assuming closure.
- Google Maps search results for service providers with no physical address can return multiple candidate pins mapped to the exact same suburb centroid coordinates; verify and reject if they lack distinct addresses or websites.
- Fuzzy name matching (token_set_ratio > 85) can transitively group distinct brand branches (e.g. ALiN Cargo vs LBC Express) in the same suburb due to shared descriptors like "Express", "Cargo", or "Branch"; filter out suburb and common generic descriptors before brand name similarity checks.
- Naive suburb extraction regexes can fail when addresses contain commas before the state (e.g., "Blacktown, NSW"); normalize or strip commas before identifying the suburb name.
- Standard street address comparisons must filter out city names (e.g. "Sydney") and check length bounds to prevent empty or generic address fields from triggering false-positive duplicate matches.
- When executing Python command-line code containing emoji or unicode escape sequences, avoid using UTF-16 surrogate pairs (such as \ud83c or \udf3a) which raise UnicodeEncodeError in standard Python 3 environments; use actual emoji characters or 32-bit escapes (such as \U0001f33a) instead.
- Listings mistakenly generated under the wrong city (e.g. Brisbane business in Sydney tasks) can have their address, latitude, and longitude corrected via UpdateListingData, but the city property cannot be updated as it is not accepted by the mutation.

