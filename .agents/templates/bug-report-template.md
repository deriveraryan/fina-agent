# Triage & Bug Diagnosis Report

---

## 1. Overview & Symptom

- **Failure Summary**: [Brief summary of the issue, scraper crash, or GraphQL push failure]
- **Reproduction Command**: [CLI script command that reproduces the issue]
- **Observed Behavior**: [What actually happened, e.g. traceback, schema validation error, or exception logs]
- **Expected Behavior**: [What should have happened]

---

## 2. Technical Diagnostics

### Stack Trace / Logs
```
[Insert relevant logs, traceback, or failed test assertions here]
```

### Root Cause Analysis (RCA)
- **Primary Cause**: [Isolate why the failure occurs, referencing files and lines]
- **Architectural Implications**: [Explain how the error affects data integrity, category definitions, or GraphQL queries]

---

## 3. Recommended Fix

### Proposed Code Diff
```diff
# [Insert git-style code modifications here]
- old_code
+ new_code
```

---

## 4. Verification Plan

### TDD Green Execution
- [ ] Failing test case added first (Red Phase).
- [ ] Test verified as green after implementation (Green Phase) using `python3 -m unittest discover tests`.

### Logging & Cleanup Check
- [ ] Ensure `--trace-id` is correctly propagated to all backend logs.
- [ ] Ensure any temporary variable files in `tmp/` are cleaned up.
