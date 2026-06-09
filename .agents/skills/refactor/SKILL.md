---
name: refactor
description: Pure-function refactoring skill for safe structural updates.
---

# Code Refactoring Skill

This skill guides the agent in improving Python code readability, removing duplication, and modernizing structure without changing application behavior.

## Rules for Safe Refactoring

- **One Step at a Time**: Execute localized, incremental adjustments (e.g. renaming a variable, extracting a parsing method, simplifying heuristics conditions).
- **Run Tests Constantly**: Run `python3 -m unittest discover tests` inside the virtual environment after *every* change to ensure functionality remains completely green.
- **Pure-Function Alignment**: Propose stateless, side-effect-free helper routines (especially inside `features/scanning/heuristics.py` or parser scripts) to simplify testing and mocking.
- **Separate Production and Test Refactoring**: Never refactor production code and test files in the same step.
- **Clean Up Temporary Files**: Keep directories like `tmp/` clean and free from temporary JSON outputs when working.
