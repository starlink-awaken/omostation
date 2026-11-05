---
schema_version: specification/v1
spec_version: 1.0.0
title: LifeOS 7.40.4 shared core across Magpie clients — migration, coverage, and runtime proof
bet_id: BET-Y2Q4-T10-254
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-19
---

# LifeOS 7.40.4 shared core across Magpie clients

## Goal

Make the pinned LifeOS core a stable, shared foundation for every client currently routed through Magpie. Preserve the existing authoritative USER and MEMORY data, carry existing client configuration forward additively, and establish a repeatable inventory-to-runtime verification path. Keep client-specific differences explicit and never infer session loading or usability from an assignment or file path.

## Current baseline

- The shared core resolves to LifeOS 7.40.4; the canonical USER and MEMORY remain at their established `~/.claude/LIFEOS/` paths.
- The latest live Magpie snapshot contains 43 client roots, 40 LifeOS skill targets, and 16 instruction targets (688 client-root/agent pairs).
- The crosswalk records 20 scoped PASS, 20 UNKNOWN, and 3 BLOCKED_AUTH. These values are a snapshot, not fixed future dimensions.
- The read-only contract validator and its 16 regression tests pass. Current live inventory and per-client summary fingerprints match the snapshot.

## Invariants

1. Keep one pinned LifeOS core and one authoritative USER/MEMORY pair. Do not create per-agent copies or import blank legacy templates.
2. Use live Magpie client inventory and Library assignments as the dynamic source of scope. Every current root and instruction target must appear in the crosswalk; newly appearing roots remain explicit candidates until their owner, adapter, version, and capabilities are established.
3. Preserve the distinction between detected, configured, rendered, loaded, and usable. A successful result requires a fresh session to read the shared entry and a real supported client operation; assignment, static path resolution, or MCP initialization alone is insufficient.
4. For each root actually routed through Magpie, obtain fresh-session evidence and correlate the request to Magpie usage, or retain an explicit blocked status and the exact user action needed. Do not mark unavailable clients as passed.
5. Use the contract validator against a fresh inventory receipt. Reject stale membership, dimension drift, malformed contracts, and per-client summary fingerprint drift before trusting prior runtime PASS records.
6. Preserve existing client model/provider choices and settings unless a specific repair is necessary for the shared LifeOS path. Back up any changed configuration and record its rollback path.
7. Read only the shared CONTEXT and LifeOS entry skill for routine canaries. Do not inject full personal identity or MEMORY into ordinary client probes.

## Acceptance criteria

- A fresh live inventory readback and its generated crosswalk contain exactly all current client roots, skill targets, and instruction targets; the dynamic root × instruction relation is complete and the validator returns `valid=true`.
- No client root has duplicated USER/MEMORY storage. The active core pin and canonical data links resolve to the same preserved sources.
- Every currently Magpie-routed client root has an explicit runtime result from a fresh session: scoped loaded/usable evidence correlated to the selected Magpie route, or a precise `BLOCKED_AUTH`/operator-action record. No unknown Magpie-routed client is silently counted as complete.
- Each current Library skill and instruction assignment is accounted for. Supported shared skill discovery paths are verified; unsupported or gated clients remain documented with a concrete next action.
- Drift handling is repeatable: a representative inventory, assignment, route-summary digest, and stale observation mutation each cause a non-green result until re-readback and revalidation.
- A migration/rollback record identifies changed paths, backups, and restoration steps; existing user data and unrelated client settings remain unchanged.
- The optimization roadmap and MP-012 task ledger are refreshed from current evidence, with remaining unknowns and blockers visible.

## Verification

- `python3 -m unittest discover -s work/lifeos-audit -p test_crosswalk_contract.py`
- `python3 -m py_compile work/lifeos-audit/crosswalk_contract.py work/lifeos-audit/test_crosswalk_contract.py`
- Run `crosswalk_contract.py` with a fresh Magpie inventory readback; require `valid=true`, exact live set matches, and exact digest matches.
- Re-read the core version and canonical data links, then run restricted fresh-session canaries for each Magpie-routed client and correlate each operation with live Magpie usage.
- Inspect every changed client configuration and its backup/rollback record before closing the BET.

## Non-goals

- Do not rewrite the LifeOS core, replace the Magpie router, or force every installed but non-Magpie client onto a new model/provider.
- Do not fabricate authentication, accept third-party legal terms, or bypass client security gates.
- Do not duplicate personal data, automatically read full USER/MEMORY in ordinary tasks, or claim native hooks/continuous memory where the client does not prove them.
- Do not commit unrelated workspace or submodule changes.
