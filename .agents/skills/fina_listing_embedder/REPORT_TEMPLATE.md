# Fina Listing Embedder Report — {CITY}

<!--
  TEMPLATE: Follow this structure exactly when writing the final report.
  Replace all {PLACEHOLDER} values with actual data.
  Filename: logs/{YYYYMMDD}/fina_listing_embedder_report_{CITY}_{YYYYMMDD}_{HHMM}.md
-->

## Run Metadata

| Field | Value |
| :--- | :--- |
| **Agent** | fina_listing_embedder |
| **Target City** | {CITY} |
| **Listings Missing Embeddings** | {N} |
| **Embeddings Generated** | {N} |
| **Execution Date** | {YYYY-MM-DD HH:MM AEST} |
| **Trace ID** | `{TRACE_ID}` |

## Summary

| Metric | Count |
| :--- | :---: |
| **Total Listings Evaluated** | {N} |
| **Embeddings Generated Successfully** | {N} |
| **Errors Encountered** | {N} |

## Processed Listings Log

<!-- List all listings that had their embeddings generated and updated. -->

| Listing Name | DB ID | Text Used for Embedding | Status |
| :--- | :--- | :--- | :--- |
| {Listing Name} | `{database_id}` | `{embedding_text}` | {Success / Failed} |

## Errors & Warnings

- None encountered.

<!-- If errors occurred, replace the above line with a bullet list describing each error/warning. -->
