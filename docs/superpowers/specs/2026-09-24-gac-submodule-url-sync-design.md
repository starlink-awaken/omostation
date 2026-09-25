---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: GAC worktree submodule URL synchronization
bet_id: BET-Y2Q2-T11-02
created: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# BET-Y2Q2-T11-02: GAC worktree submodule URL synchronization

## Problem

Canonical workspaces may contain local `submodule.<path>.url` overrides in `.git/config`. A newly created worktree inherits those overrides, while `.gitmodules` still declares the authoritative repository URLs. `gac-worktree.sh claim` currently runs `git submodule update --init` without first synchronizing the worktree's submodule configuration. The initializer can therefore fetch from a stale local checkout and fail even when the pinned commit is reachable from the declared remote.

## Decision

Before every bulk submodule initialization in `gac-worktree.sh`, run `git submodule sync --recursive` inside the new worktree. If synchronization fails, fail closed before attempting checkout. The existing shallow/full initialization and timeout behavior remain unchanged.

Add a regression test that installs a stale local submodule URL override and proves the claim path restores the `.gitmodules` URL before initialization.

## Non-goals

- No changes to `.gitmodules` URLs.
- No submodule pointer changes.
- No changes to submodule repositories.
- No changes to `SKIP_SUBMODULE_INIT=1` semantics.
- No retries, force operations, or URL rewriting in the canonical workspace.

## Verification

```text
bash -n bin/gac/gac-worktree.sh
pytest -q tests/test_gac_worktree_claim_pasw.py
```

The focused test must prove a stale local URL override does not control the new worktree's initialization.
