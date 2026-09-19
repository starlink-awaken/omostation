---
schema_version: specification/v1
spec_version: 1.0.0
title: Quarantine unconsumed learning runtime helper scripts
bet_id: BET-Y1Q3-T10-96
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Quarantine unconsumed learning runtime helper scripts

## Intent

Remove a narrow set of unconsumed legacy helper implementations from the
learning Documents execution plane after the Workspace concept-weave preflight
cutover, while leaving owner-dependent learning commands in place until their
replacement contracts are proven.

## Contract

- Select only the four file scopes under
  `@学习进化/_control/scripts/`: the two backfill helpers,
  `concept-weave.py`, and `run-monthly-weave.sh`.
- Require a fresh consumer receipt with zero forbidden executors and zero
  unmatched consumers before each move; do not infer safety from filename
  absence alone.
- Move regular files into separate, protected Workspace quarantine packages;
  preserve bytes, modes, hashes, and reversible manifests.
- Do not move `l4-kernel.sh`, `vault-healthcheck.sh`, `knowledge-decay.sh`,
  daemon/executor implementations, `.githooks/pre-commit-g18`,
  `_inbox/inbox-router.sh`, or any learning content.
- Keep `learning-runtime` at `in_progress` because residual owner-dependent
  runtime remains and Runtime/Kairon parity is not proven.

## Acceptance

1. The four scoped L4 audits each select exactly one regular runtime file.
2. Source absence, target equality, and rollback manifests are independently
   verified for all four files; permanent deletion is false.
3. Postflight retains learning content and the residual runtime surfaces, and
   the migration registry records only completed helper subscopes.
