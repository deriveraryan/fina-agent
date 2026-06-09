---
name: plan
description: Architectural planning skill for generating modular implementation plans.
---

# Feature Planning & Architecture Skill

This skill guides the agent in gathering context, analyzing functional requirements, and creating modular implementation plans for the data scraper pipeline.

## Guidelines

- **Context Synthesis**: Search the codebase and documentation first using search/read tools before drafting any plan. Verify existing scripts in `scripts/` and helper structures in `features/`.
- **Micro-Logical Phase Division**: Divide features into structured, logical, and small phases (Phase 1: Foundation / Off-line Testing, Phase 2: Core Processing Logic, Phase 3: Integration & CLI Triggers).
- **Incorporate Testing First**: Ensure the TDD Strategy section outlines mock assertions, unit boundary isolation, and offline verification (Mocking HTTPX, Places API, and GraphQL endpoints).
- **Review Constraints**: Keep all planning strictly focused on design. Do not make premature file writes or modifications until the plan is approved.
- **Deduplication and Heuristics Rules**: Ensure any changes adhere to database deduplication rules (using `sourceUrl`, name normalization, pgvector semantic embedding similarity) and category validation against `data/categories.json`.

## Plan Template
Refer to [.agents/templates/plan-template.md](../../templates/plan-template.md) for structuring feature implementation plans.
