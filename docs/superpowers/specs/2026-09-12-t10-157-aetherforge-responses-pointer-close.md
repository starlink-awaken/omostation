---
schema_version: specification/v1
spec_version: 1.0.0
title: projects/aetherforge root gitlink pointer closeout (Responses API)
bet_id: BET-Y1Q4-T10-157
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-12
---

# T10-157 — projects/aetherforge root gitlink pointer closeout

## Context

`omostation-aetherforge` PR #71 added OpenAI Responses API support
(`/v1/responses`, including SSE streaming) to the AetherForge gateway,
directly unblocking Codex CLI's `wire_api="responses"` requirement against
the local compute gateway. The PR merged to `omostation-aetherforge` main
as commit `452f0db047e09657d56fc0913b6b54c36e8532c0`, live-verified against
the running gateway and against a real `codex exec` invocation.

The root `omostation` repo's `projects/aetherforge` gitlink still pointed at
the pre-merge commit `f3df9b4b259c93d737ec5acd0c312eeeb3d383fe`. This was a
pure documentation/consistency gap: the live gateway process runs directly
from the submodule's own source tree (not from a root-repo checkout), so
the stale pointer had no effect on the already-working, already-merged
fix. It did affect fresh recursive clones and any tooling that reads the
root repo's gitlink as the source of truth for what `projects/aetherforge`
contains.

## Goal

Bump the root `projects/aetherforge` gitlink to `452f0db0` so the root repo
accurately reflects the merged, live Responses API support.

## Non-goals

- Do not modify `projects/aetherforge` source, branch history, or any other
  gitlink.
- Do not touch runtime, host schedule, LaunchAgents, or any file outside
  the gitlink pointer and this BET's own ledger/spec/retro entries.

## Done when

- Root `projects/aetherforge` gitlink equals
  `452f0db047e09657d56fc0913b6b54c36e8532c0`.
- The candidate SHA is reachable from `omostation-aetherforge`'s
  `origin/main` (already verified: PR #71 merged there).
- `gac-local-gate` / governance-release-gate pass on the pointer-bump PR.

## Rollback

Revert the gitlink back to `f3df9b4b259c93d737ec5acd0c312eeeb3d383fe` (the
prior committed value) — a single-line gitlink revert, no other state
depends on this change.
