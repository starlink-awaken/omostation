---
type: ssot
---

# AGENTS.md — .github

## Scope

The .github directory is for repository workflows, templates, and collaboration metadata.

## Governance rules

- Read root AGENTS.md before editing workflow and automation files.
- For any requirement-related change, follow ADR-0203 workflow: bootstrap -> start -> claim -> verify -> closeout.
- Keep workflow triggers and permissions auditable and minimal.
- Any temporary workflow artifacts should be removed promptly.

## Common checks

- Verify the changed workflow file.
- Add/refresh a short note of the intent and rollback path in the PR description.

