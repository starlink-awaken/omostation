---
schema_version: specification/v1
spec_version: 1.0.0
title: projects/omlxc root gitlink pointer closeout (probe-candidate availability fix)
bet_id: BET-Y1Q4-T10-158
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-12
---

# T10-158 — projects/omlxc root gitlink pointer closeout

## Context

`omostation-omlxc` PR #72 fixed a persistent `available: false` false
positive in `OmlxAppAdapter.discover()`: the readiness probe only ran when
one hardcoded `probe_model_id` happened to already be the currently-loaded
model, so on a backend that holds only one model at a time (`coding`,
`qwen-3.8-27b`, and other chat models sharing `mbp-m5-max-128g-omlx-app`)
the probe silently skipped almost all the time and `generation_ready`
stayed permanently false even though the model responded correctly when
hit directly. The PR merged to `omostation-omlxc` main as commit
`e92317572eefbc539bb99c29029cf001c6261388`, live-verified against the
running daemon after a reinstall and restart.

The root `omostation` repo's `projects/omlxc` gitlink still points at the
pre-merge commit `a438f9ae7a7927a91a3f43b70d7749558a8c3bf9`. As with prior
pointer-closeout BETs, this is a documentation/consistency gap only: the
live daemon runs from a `uv tool install`ed copy of the submodule's own
source tree, not from a root-repo checkout.

## Goal

Bump the root `projects/omlxc` gitlink to `e9231757` so the root repo
accurately reflects the merged, live probe-candidate availability fix.

## Non-goals

- Do not modify `projects/omlxc` source, branch history, or any other
  gitlink.
- Do not touch runtime, host schedule, LaunchAgents, or any file outside
  the gitlink pointer and this BET's own ledger/spec/retro entries.

## Done when

- Root `projects/omlxc` gitlink equals
  `e92317572eefbc539bb99c29029cf001c6261388`.
- The candidate SHA is reachable from `omostation-omlxc`'s `origin/main`
  (already verified: PR #72 merged there).
- `gac-local-gate` / governance-release-gate pass on the pointer-bump PR.

## Rollback

Revert the gitlink back to `a438f9ae7a7927a91a3f43b70d7749558a8c3bf9` (the
prior committed value) — a single-line gitlink revert, no other state
depends on this change.
