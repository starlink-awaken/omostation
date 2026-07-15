---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0196 — `omo acl plan --acl` 命名 ACE 干跑脚本

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

ADR-0194 designed setfacl/chmod+a. Operators need a reviewable script before
any host mutation. Note: number **0195** is already used by architecture
convergence ISC-2 — this feature is **0196**.

## Decision

1. `omo acl plan --acl` appends `named_acl` (script + commands) to chmod plan
2. Linux `setfacl` / macOS `chmod +a` from `etc/omo-path-acl.yaml::acl.entries`
3. **Never executes** ACE script (`mutation: false`)
4. `apply --acl` still deferred

## Verification

```bash
omo acl plan --acl --json
pytest projects/omo/tests/test_omo_path_acl.py -q
```
