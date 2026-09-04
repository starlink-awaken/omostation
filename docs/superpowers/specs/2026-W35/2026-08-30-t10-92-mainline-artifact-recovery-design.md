---
schema_version: specification/v1
spec_version: 1.0.0
title: Restore T10-92 artifacts dropped from the mainline merge tree
bet_id: BET-Y1Q3-T10-94
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Restore T10-92 artifacts dropped from the mainline merge tree

## Intent

Restore the already accepted T10-92 OPC quarantine evidence that is present in
the merged T10-92 tree but absent from the current `origin/main` merge tree.
This recovery keeps the mainline ledger, migration registry, and evidence
artifacts consistent with the real host-side quarantine state.

## Contract

- Treat `78fb360d4e27d1c65b62d9fe5bf68d40fed89bc1`, the merged T10-92 commit,
  as the immutable source for the six missing root artifacts.
- Restore only the T10-92 registry evidence, ledger entry, specification,
  implementation report, retrospective, and bootstrap waiver.
- Preserve the current mainline changes from merge #2645 and do not alter
  Documents, Workspace quarantine payloads, submodule pointers, runtime state,
  or unrelated governance records.
- Keep `opc-tools` at `in_progress`, retain its exact quarantine fingerprints,
  and do not convert the restoration into a new owner-parity claim.

## Acceptance

1. The current mainline tree contains the same six T10-92 artifacts as the
   immutable T10-92 source tree, except for no unrelated changes.
2. The restored ledger passes dependency, completion-evidence, and lint
   validation; `BET-Y1Q3-T10-92` remains `done` with value `NOT_PROVEN`.
3. The restored registry reports `opc-tools: in_progress` with its original
   manifest, fingerprints, consumer receipt, and pending owner parity.
4. The next family-runtime BET can depend on T10-92 without an unresolvable
   dependency.
