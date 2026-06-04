# Fina Socials Finder Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/fina_socials_finder_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_socials_finder |
| **Target City** | {CITY} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |

## Summary

| Metric | Count |
| :--- | :--- |
| **Total Listings Evaluated** | {N} |
| **Listings Enriched (Socials Pushed)** | {N} |
| **Listings Evaluated (No Socials Found)** | {N} |
| **Errors Encountered** | {N} |

## Enriched Listings

<!-- List all listings where at least one social URL was discovered and pushed. Use — for platforms where no URL was found. -->

| Listing Name | Address | DB ID | Facebook URL | Instagram URL |
| :--- | :--- | :--- | :--- | :--- |
| {name} | {address} | `{id}` | {url or —} | {url or —} |

## Non-Enriched Listings

<!-- List all evaluated listings where no socials were found or pushed. Include the reason for each. -->

| Listing Name | Address | DB ID | Reason |
| :--- | :--- | :--- | :--- |
| {name} | {address} | `{id}` | {No active socials found / Permanently closed / Already has socials / etc.} |

## Errors & Warnings

- None encountered.

<!-- If errors occurred, replace the above line with a bullet list describing each error/warning. -->
