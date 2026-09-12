---
schema_version: specification/v1
spec_version: 1.0.0
title: projects/omlxc root gitlink pointer closeout (inventory-baseline reset)
bet_id: BET-Y1Q4-T10-162
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-12
---

# T10-162 — projects/omlxc root gitlink pointer closeout (inventory-baseline reset)

## Context

`omostation-omlxc` PR #73 added a way to accept an intentional
inventory-drop baseline (`omlxc nodes reset-inventory-baseline
<node_id> <backend_id>`), fixing three long-standing `inventory_drop`
false-alarm warnings that had no correction mechanism: the persisted
high-water mark only ever ratchets up by design, so an intentional
model-catalog shrink (unused local model files removed) left a stale,
unreachable baseline warning forever. The PR merged to
`omostation-omlxc` main as commit
`c030788e8792482845b66f1247bd937f077f2efd`, live-verified: the new
command was run against all three real flagged backends on this
machine, and `omlxc status` now reports clean with no warnings.

The root `omostation` repo's `projects/omlxc` gitlink still pointed at
the pre-merge commit `e92317572eefbc539bb99c29029cf001c6261388`. As with
prior pointer-closeout BETs, this is a documentation/consistency gap
only: the live daemon runs from a `uv tool install`ed copy of the
submodule's own source tree, not from a root-repo checkout.

## Goal

Bump the root `projects/omlxc` gitlink to `c030788e` so the root repo
accurately reflects the merged, live inventory-baseline-reset fix.

## Non-goals

- Do not modify `projects/omlxc` source, branch history, or any other
  gitlink.
- Do not touch runtime, host schedule, LaunchAgents, or any file outside
  the gitlink pointer and this BET's own ledger/spec/retro entries.

## Done when

- Root `projects/omlxc` gitlink equals
  `c030788e8792482845b66f1247bd937f077f2efd`.
- The candidate SHA is reachable from `omostation-omlxc`'s `origin/main`
  (already verified: PR #73 merged there).
- `gac-local-gate` / governance-release-gate pass on the pointer-bump PR.

## Rollback

Revert the gitlink back to `e92317572eefbc539bb99c29029cf001c6261388`
(the prior committed value) — a single-line gitlink revert, no other
state depends on this change.
