---
name: prompt-articulator
description: Refines rough draft task descriptions into clear, explicit, and actionable prompts tailored to the Fina Agent codebase context.
---

# Prompt Articulator (Fina Agent Repository)

Use this skill when the user provides a rough draft, scattered thoughts, or an informal prompt and wants it articulated into a clear, explicit, and straightforward statement before starting work.

## How to use this skill

1. **Analyze the Draft**: Read the user's draft to extract the core goal, the specific subagents, scripts, or features involved.
2. **Contextualize with Fina Agent Architecture**:
   - Translate general ideas into Fina Agent-specific components (e.g. `fina_listing_map_search`, `fina_listing_web_search`, `agent_graphql_push.py` REST impersonation operations, categories validations via `data/categories.json`).
   - Reference appropriate CLI triggers (`scripts/agent_*.py` or `features/**/*.py`).
   - Align the goals with standard project workflows (such as TDD under `tests/`, Trace ID correlation via `--trace-id`, and GraphQL impersonation REST layer).
3. **Draft the Refined Prompt**: Present a structured, clear, and actionable prompt. Ensure it outlines:
   - **Goal**: Clear statement of the desired outcome.
   - **Scope/Components**: Specific scripts, feature slices, or file patterns to modify/create.
   - **Execution Details**: Specific CLI command triggers and test suite commands (e.g., `python3 -m unittest discover tests`).
   - **Constraints**: Remind the agent of repository rules (e.g., Rule 1.1 GraphQL REST client, Rule 1.2 CLI Workflows, Rule 1.5 TDD Mandate, etc.).

## Articulation Template

When the user provides a rough draft, respond with the refined version following this format:

```markdown
### Refined Prompt

[Insert the refined, clear, and explicit prompt here. Make it direct and imperative, focusing on actions, scripts, and correctness.]

### Context & Mapping
- **CLI Trigger / Feature**: [e.g., scripts/agent_maps_fetch.py, features/scanning]
- **TDD Strategy**: [Identify the unit/mock tests needed under tests/]
- **Relevant Rules**: [Reference AGENTS.md rules, e.g., GraphQL client rule, Trace ID correlation, category verification rules]
```
