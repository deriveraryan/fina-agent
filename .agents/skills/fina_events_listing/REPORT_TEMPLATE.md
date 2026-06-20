# Fina Events Listing Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/{YYYYMMDD}/fina_events_listing_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_events_listing |
| **Target City** | {CITY} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |

## Summary

| Metric | Count |
| :--- | :--- |
| **Social URLs Scanned** | {N} |
| **Events Discovered & Pushed** | {N} |
| **Follower Counts Updated** | {N} |
| **Bookmarks Updated** | {N} |
| **Errors Encountered** | {N} |

## Discovered Events

<!-- List all events that were discovered and pushed to the database. -->

| Event Name | Host Business | Start Date | End Date | Source URL | DB ID |
| :--- | :--- | :--- | :--- | :--- | :--- |
| {event_name} | {business_name} | {YYYY-MM-DD} | {YYYY-MM-DD or —} | {source_url} | `{id}` |

## URLs Evaluated (No Events Found)

<!-- List all social URLs that were visited but yielded no upcoming events. -->

| Business Name | Social URL | Reason |
| :--- | :--- | :--- |
| {name} | {url} | {No upcoming events / Page inaccessible / Page requires login / etc.} |

## Errors & Warnings

- None encountered.

<!-- If errors occurred, replace the above line with a bullet list describing each error/warning. -->
