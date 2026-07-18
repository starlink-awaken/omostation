# Phase escapes (committed, CI-visible)

Escapes under `.omo/_delivery/phase-escape/` are runtime-only (often gitignored).
For a PR to use an escape in GitHub Actions, place a JSON file **here** and
reference it via `id` / `pr_number` / `PHASE_ESCAPE_ID`.

Schema:

```json
{
  "id": "unique-escape-id",
  "phase": "phase2",
  "pr_number": "424",
  "reason": "human-readable justification",
  "active": true
}
```

See ADR-0223.
