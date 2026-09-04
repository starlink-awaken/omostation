---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-95
---

# T10-93 ledger mainline recovery — implementation evidence

## Finding

The family runtime quarantine delivery head `775bbb82f` contains the completed
T10-93 BET block, including its accepted Spec binding and completion matrix.
Neither the T10-93 merge tree `7b5a1ad028` nor the later mainline
`b6004fd5d` contains that ledger block, even though the family registry,
quarantine report, retrospective, and waiver are present.

## Recovery

The exact T10-93 ledger block was restored into `docs/plans/3y-bet-ledger.yaml`
from the immutable delivery head. The current mainline T10-92 and T10-94
records remain unchanged. No registry, Documents path, Workspace quarantine
payload, runtime state, submodule pointer, or value claim was modified.

## Verification

- Before recovery: `origin/main=b6004fd5d` had no T10-93 ledger entry.
- Source: `775bbb82f` had exactly one T10-93 block with status `done`,
  `overall_state=delivery_accepted`, and value `NOT_PROVEN`.
- After recovery: ledger lint and the non-recursive T10-95 assertion pass;
  T10-92 and T10-94 remain present, and the diff is limited to the T10-93
  ledger block plus T10-95's own evidence surfaces.

## Boundary

This is a root ledger recovery caused by merge-tree loss, not a new family
migration or a change to physical quarantine state. The existing family
owner-parity status remains `in_progress`/pending as recorded by T10-93.
