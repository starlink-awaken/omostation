---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
bet_id: BET-Y1Q3-T10-34
---

# Session brief Workspace owner evidence

The daily 06:15 session-brief schedule invokes the canonical
`bin/mof/generate-brief.py` owner with explicit `OMOSTATION_WORKSPACE_ROOT` and
`OMOSTATION_BRIEF_OUTPUT`. The scheduled command writes only the Workspace
brief and does not invoke the legacy Documents session-brief chain.

## Verification

- Active 06:15 owner line count: exactly `1`, target root `accepted-20260908`.
- Accepted release is clean and contains the canonical generator.
- Focused tests: `3 passed`.
- Generator help: exit `0`.
- Temporary-root isolation: explicit Workspace/output paths were honored; no
  Documents path was created.
- Existing live owner evidence reports exit `0` when the normalized brief is
  unchanged; this is truthful no-op behavior.

The legacy Documents brief remains available as rollback/content material.
Documents `@驾驶舱/_control/BRIEF.md` is not an execution output of the owner.
Personal value and semantic quality of the brief remain outside this BET.
