# Fina Listing Auditor Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/{YYYYMMDD}/fina_listing_auditor_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_listing_auditor |
| **Target City** | {CITY} |
| **Listings Evaluated** | {N} |
| **Corrections Applied** | {N} |
| **Dry-Run Mode** | {True / False} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |

## Summary

| Metric | Count |
| :--- | :---: |
| **Total Listings Scanned** | — |
| **Listings Correct / Unchanged** | — |
| **Listings Re-categorized** | — |
| **Errors Encountered** | — |

## Corrections Log

<!-- List all listings that required correction and what was updated. -->

### Applied Updates

1. **{Listing Name}**
   - **Old Categories**: {categories}
   - **New Categories**: {categories}
   - **Reason**: {Reason given by LLM}
   - **DB ID**: `{database_id}`

## Errors & Warnings

- None encountered.
