---
schema_version: specification/v1
spec_version: 1.0.0
title: External write-root claims bridge v1
bet_id: BET-Y2Q2-T10-153
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-21'
last-reviewed: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
type: ssot
---

# External write-root claims bridge v1

## Problem

Canonical claims authority correctly prevents arbitrary paths outside
`/Users/xiamingxing/Workspace`, but some admitted product surfaces—such as the
local-only Zhixing dashboard repository—live outside that root. The current
all-or-nothing boundary forces either unsafe direct edits or an unavailable
claim path.

## Design

Introduce an explicit registry of admitted external local-git write roots. A
root must have a stable identifier, a non-symlink directory outside Workspace,
a clean admission status, and explicit relative path patterns. Claims map a
validated external file to a deterministic synthetic canonical path,
`external/<root-id>/<relative-path>`. The same mapping is used by WorkPacket
scope validation, lifecycle claim normalization, lock identity, affected-graph
classification, and external-git change discovery.

Unregistered roots, symlinks, escaping paths, non-git roots, or paths outside a
root's patterns remain rejected. The registry never grants root-level writes and
never changes the canonical claims store location.

## Acceptance

- An admitted external file can be claimed only through the synthetic root path.
- Unregistered external files, traversal paths, disallowed patterns, and
  non-git roots are rejected.
- WorkPacket hashes remain reproducible from the same Ledger and registry.
- External git changes appear with the synthetic prefix in workflow verify.
- The existing Zhixing dashboard root is admitted for JavaScript and Python
  implementation surfaces only.
- Focused OMO workflow tests and default governance gates pass.

## Non-goals

This does not activate Claims Authority v2, move the canonical claims store,
grant arbitrary home-directory access, permit remote filesystems, rewrite
historical claims, bypass PR checks, or prove business value.

## Rollback

Remove the registry admission and revert the OMO/root changes. External repos
remain unaffected and previously claimed Workspace paths retain their existing
semantics.
