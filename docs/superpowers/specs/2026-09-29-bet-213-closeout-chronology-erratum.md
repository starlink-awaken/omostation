---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-213 — Correct PR-3 Closeout Workflow Chronology
bet_id: BET-Y2Q4-T10-213
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-29
---

# Closeout report chronology erratum

## Objective

Correct only §9 bullet 6 of
`docs/reports/2026-09-29-projection-plane-phase2-pr3-closeout.md`. The current sentence says
both workflow runs closed after the report's PR merged. The recorded timeline contradicts that
claim:

| Event | Authoritative timestamp / state |
|---|---|
| Code workflow `20260929T044531Z-project-code-change-e23ad439` closed | `blocked`, 2026-09-29 07:21:24Z |
| PR #4534 merged | 2026-09-29 07:34:56Z |
| Documentation workflow `20260929T073730Z-project-doc-change-3a7a7ec8` started | 2026-09-29 07:37:30Z |
| PR #4544 merged | 2026-09-29 08:14:47Z |
| Documentation workflow closed | `ok`, 2026-09-29 08:16:23Z |

The corrected text must distinguish the blocked code run from the successful documentation
run and must not imply that both closeouts occurred after merge.

## Invariants and non-goals

- Do not change BET-Y2Q4-T10-212's status, completion evidence, or retrospective conclusions.
- Do not change any byte of its accepted specification or its recorded digest.
- Do not alter either historical workflow run record.
- Do not alter any other report text or broaden this into a governance-policy change.

## Acceptance criteria

1. §9 bullet 6 states the code run's `blocked` close at 07:21:24Z, before PR #4534's 07:34:56Z
   merge, and the documentation run's `ok` close at 08:16:23Z, after PR #4544's 08:14:47Z
   merge.
2. The values match the immutable workflow run records and GitHub PR merge metadata.
3. The diff changes only that report bullet plus BET-213's required ledger/spec/waiver/retro
   governance records.
4. BET-212's ledger entry, accepted spec bytes/digest, and retro are byte-identical to the base.
