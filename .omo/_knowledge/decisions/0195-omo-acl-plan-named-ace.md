---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0195 — `omo acl plan --acl` 命名 ACE 干跑脚本

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

ADR-0194 designed setfacl/chmod+a. Operators need a **reviewable script**
before any host mutation. Apply-with-ACE remains deferred.

## Decision

1. `omo acl plan --acl` appends `named_acl` to the chmod plan
2. Script targets Linux `setfacl` or macOS `chmod +a` (platform auto/env)
3. Profile `etc/omo-path-acl.yaml::acl.entries` is SSOT
4. **Never executes** ACE script in this ADR (`mutation: false`)
5. `apply --acl` still **not** implemented

## Verification

```bash
omo acl plan --acl --json | head
pytest projects/omo/tests/test_omo_path_acl.py -q
```
