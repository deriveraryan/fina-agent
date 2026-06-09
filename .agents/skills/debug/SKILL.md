---
name: debug
description: Diagnostic debugging skill for root cause analysis and triage.
---

# Diagnostic Triage & Debugging Skill

This skill guides the agent in investigating failures, analyzing errors, and diagnosing the root causes of issues in the data scraper pipeline in a non-destructive manner.

## Guidelines

- **Read-Only Investigation**: Never modify source code, cache data, or environment configurations during diagnostic analysis. Focus strictly on gathering details.
- **Log & Trace Audits**: Read failing unittest runs, trace files inside `logs/`, or output logs associated with a particular `--trace-id` to isolate where the exception arose.
- **Root Cause Isolation**: Determine the core issue rather than applying quick patches. Explain:
  1. What is failing (e.g. Places API cache miss, browser-use selector mismatch, GraphQL mutation validation error).
  2. Why it is failing (e.g. incorrect category name, empty display name, schema type mismatch).
  3. The permanent fix using the [bug report template](../../templates/bug-report-template.md).
