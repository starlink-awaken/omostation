---
id: waiver-2026-09-21-a8-evidence-sha-recovery
scope: BET-Y1Q4-T10-151 A8 evidence SHA truth recovery
created: '2026-09-21'
owner: governance-team
status: active
lifecycle: history
last-reviewed: '2026-09-21'
type: governance-evidence
---

# A8 evidence SHA truth recovery waiver

## Authority

The active recovery objective authorizes truthful execution-environment
closeout. Because this is an evidence-only correction to an already-terminal
BET, canonical Workspace run
`20260921T062109Z-governance-state-mutation-b798a514` was started once with
`AGCP_REQUIREMENT_ITERATION_GATE=0` as a process-level prefix. Claims and all
later verification, changeset, publication, PR, required checks, and closeout
use default gates.

The only tracked changes are:

- `docs/plans/3y-bet-ledger.yaml`: replace the unreachable
  `de5cafe0662e2eaac464be69f5850df1e5bafc42` in the
  `BET-Y1Q4-T10-151` engineering `merged_reachable_commit` with
  `5e1f7eae9b024dccc7a5977139e2de906c25b76c`.
- this waiver.

## Evidence

- OMO PR #173 merge `5e1f7eae9b024dccc7a5977139e2de906c25b76c` is an ancestor
  of `projects/omo` origin/main.
- It added exactly `src/omo/workflow/external_transaction.py` and
  `tests/test_external_transaction.py`.
- Focused A8 verification passes: `22 passed in 0.18s`.
- The old `de5cafe...` SHA is absent locally after fetch and GitHub returns
  `422 No commit found for SHA`.

## Boundary and rollback

Do not change A8 status, completion axes, value evidence, implementation,
tests, other BET entries, gitlinks, branch protection, runtime state, or user
configuration. Rollback is limited to reverting the Ledger SHA and this waiver.
