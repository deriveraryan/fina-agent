# Fina Places Finder Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/{YYYYMMDD}/fina_refresh_listing_maps_finder_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_refresh_listing_maps_finder |
| **Target City** | {CITY} |
| **Categories Scanned** | {COMMA_SEPARATED_CATEGORIES e.g. RESTAURANT, CAFE, SHOP, CHURCH, COMMUNITY, GOVERNMENT, SERVICES} |
| **Google Places API Calls** | {NUMBER_OF_API_CALLS e.g. 0 (Cache Hit) or 15} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |


## Summary

| Category | Candidates Evaluated | Listings Created | Listings Merged/Updated | Total Persisted |
| :--- | :---: | :---: | :---: | :---: |
| **RESTAURANT** | — | — | — | — |
| **CAFE** | — | — | — | — |
| **SHOP** | — | — | — | — |
| **CHURCH** | — | — | — | — |
| **COMMUNITY** | — | — | — | — |
| **GOVERNMENT** | — | — | — | — |
| **SERVICES** | — | — | — | — |
| **TOTAL** | **—** | **—** | **—** | **—** |

## Verified Listing Details

### Created Listings

<!-- Sort entries by category (RESTAURANT → CAFE → SHOP → CHURCH → COMMUNITY → GOVERNMENT → SERVICES), then alphabetically within each category. -->

1. **{Listing Name}** ({CATEGORY})
   - Address: {full address}
   - Description: {brief description of the business}
   - DB ID: `{database_id}`

### Merged/Updated Listings

<!-- Sort entries by category, then alphabetically within each category. -->

1. **{Listing Name}** ({CATEGORY})
   - Address: {full address}
   - Description: {brief description of the business}
   - DB ID: `{database_id}`

## Skipped / Rejected Candidates

<!-- List all candidates that were evaluated but NOT pushed to the database. -->

| Candidate Name | Category | Reason |
| :--- | :--- | :--- |
| {name} | {CATEGORY} | {Not Filipino-affiliated / Out of city boundary / Permanently closed / Duplicate} |

## Errors & Warnings

- None encountered.

<!-- If errors occurred, replace the above line with a bullet list describing each error/warning. -->
