# Fina New Listing Web Finder Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/{YYYYMMDD}/fina_new_listing_web_finder_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_new_listing_web_finder |
| **Target City** | {CITY} |
| **Platforms Searched** | {Facebook, Instagram} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |

## Summary

| Metric | Count |
| :--- | :--- |
| **Total Candidate Pages Evaluated** | {N} |
| **Verified Listings Created** | {N} |
| **Candidates Rejected** | {N} |
| **Errors Encountered** | {N} |

## Verified Community Listings

### Created Listings

<!-- Group entries by Category (e.g., #### RESTAURANT). Within each category, sort entries by platform (Facebook first, then Instagram), then alphabetically. -->

1. **{Name}** ({Platform})
   - Category: {COMMUNITY / CHURCH / GOVERNMENT / SERVICES / etc.}
   - Address: {full address or "Online-only — city center coordinates"}
   - Description: {brief description of the community/organisation}
   - Social URL: {facebook or instagram url}
   - DB ID: `{database_id}`
   - Tags: {comma-separated tags e.g. google-search,online-org}

## Skipped / Rejected Candidates

<!-- List all candidate pages that were evaluated but NOT pushed to the database. -->

| Candidate Name | Platform | Reason |
| :--- | :--- | :--- |
| {name} | {Facebook / Instagram} | {Not Filipino-affiliated / Duplicate / Inactive page / Personal profile / etc.} |

## Errors & Warnings

- None encountered.

<!-- If errors occurred, replace the above line with a bullet list describing each error/warning. -->
