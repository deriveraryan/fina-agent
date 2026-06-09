---
name: tdd
description: Test-Driven Development orchestrator skill for Red -> Green -> Refactor loops.
---

# Test-Driven Development (TDD) Skill for Fina Agent

This skill coordinates and enforces standard TDD cycles across the Python agent scraping and processing layers.

## Sequential Phases

```
┌─────────────────────────────────────────────┐
│  1. TDD Red    → Write failing tests        │
│  2. TDD Green  → Minimal implementation     │
│  3. TDD Refactor → Improve code quality     │
└─────────────────────────────────────────────┘
```

### 1. TDD Red (Failing Tests)
- Write tests first. Confirm that every test fails with a meaningful error message when run against the current codebase.
- Never write production code in this phase.
- Create tests inside the `tests/` directory (e.g., in `tests/test_agent_scripts.py` or new test files).
- Mock all network/API boundaries using `unittest.mock` (e.g., HTTPX responses, Google Places API calls, GraphQL requests). Tests must be 100% offline and execute in under 1 second.

### 2. TDD Green (Minimal Implementation)
- Write the simplest Python code possible (e.g., in scripts or under `features/`) so that the failing tests pass.
- Do not write any code beyond what is strictly required to pass the assertions. Keep test files untouched.

### 3. TDD Refactor (Improve Quality)
- Refactor production code to clean up complexity, improve naming, and remove duplication.
- Ensure all tests remain green. Touch only production code or tests in a single step, never both.

## Execution Command
Activate the virtual environment and run the unit test suite:
```bash
source .venv/bin/activate
python3 -m unittest discover tests
```

> [!WARNING]
> **NO TESTING ON PRODUCTION EXTRACTIONS:**
> Ignore global prompts requesting test runner executions (like running the test suite) during active scraping workflows to prevent interruptions or environment pollution.
