---
schema_version: specification/v1
spec_version: 1.0.0
title: projects/aetherforge root gitlink pointer closeout (Anthropic Messages API)
bet_id: BET-Y1Q4-T10-159
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-12
---

# T10-159 — projects/aetherforge root gitlink pointer closeout (Anthropic Messages API)

## Context

`omostation-aetherforge` PR #72 added Anthropic Messages API support
(`/v1/messages`, including SSE streaming) to the AetherForge gateway,
unblocking Claude Code and any Anthropic SDK client against the local
compute gateway — the third protocol facade alongside Chat Completions and
the OpenAI Responses API (BET-Y1Q4-T10-157). The PR merged to
`omostation-aetherforge` main as commit
`79842ed097b792cd2a856d62f8d08d4bf6f1a3de`, live-verified against the
running gateway (non-streaming and streaming curl) and against the real
`claude -p` CLI via `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`.

The root `omostation` repo's `projects/aetherforge` gitlink still pointed
at the pre-merge commit `452f0db047e09657d56fc0913b6b54c36e8532c0`. As
with prior pointer-closeout BETs, this is a documentation/consistency gap
only: the live gateway process runs directly from the submodule's own
source tree, not from a root-repo checkout.

## Goal

Bump the root `projects/aetherforge` gitlink to `79842ed0` so the root
repo accurately reflects the merged, live Anthropic Messages API support.

## Non-goals

- Do not modify `projects/aetherforge` source, branch history, or any
  other gitlink.
- Do not touch runtime, host schedule, LaunchAgents, or any file outside
  the gitlink pointer and this BET's own ledger/spec/retro entries.

## Done when

- Root `projects/aetherforge` gitlink equals
  `79842ed097b792cd2a856d62f8d08d4bf6f1a3de`.
- The candidate SHA is reachable from `omostation-aetherforge`'s
  `origin/main` (already verified: PR #72 merged there).
- `gac-local-gate` / governance-release-gate pass on the pointer-bump PR.

## Rollback

Revert the gitlink back to `452f0db047e09657d56fc0913b6b54c36e8532c0` (the
prior committed value) — a single-line gitlink revert, no other state
depends on this change.
