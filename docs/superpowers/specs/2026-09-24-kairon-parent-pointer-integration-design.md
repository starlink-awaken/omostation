---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: Kairon parent gitlink integration
bet_id: BET-Y2Q2-T11-03
created: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
---


# BET-Y2Q2-T11-03: Kairon parent gitlink integration

## Problem

The Kairon dependency lock remediation is committed and independently verified in the child repository, but the root repository still points at the prior Kairon gitlink. The verified child commit must be promoted to the root's declared pointer without changing any other submodule.

## Decision

Advance only `projects/knowledge/kairon` to child commit `642311f4728cb893e0c643f34f78407d66af4b67`, verify that the commit is reachable from the child repository and that the child lock/tests remain green, then commit the root pointer together with the already verified root worktree URL synchronization repair.

## Non-goals

- No child source changes beyond the already committed `uv.lock` remediation.
- No other submodule pointer movement.
- No force push, reset, or destructive cleanup.
- No claim of value acceptance.

## Verification

```text
cd projects/knowledge/kairon && uv lock --check
cd projects/knowledge/kairon && uv run pytest packages/kairon-pipeline/tests -q
bash -n bin/gac/gac-worktree.sh
uv run --with pytest pytest -q tests/test_gac_worktree_claim_pasw.py
make gac-local-gate
make ssot-guardian
```
