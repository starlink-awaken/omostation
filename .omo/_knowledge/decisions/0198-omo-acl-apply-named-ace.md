---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0198 — `omo acl apply --yes --acl` 命名 ACE 执行

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

ADR-0196 delivered dry-run ACE scripts. Operators still needed a gated
executor that cannot run by accident in CI or multi-agent defaults.

## Decision

1. `omo acl apply --yes --acl` requires **`OMO_OS_ACL=1`** and **`--yes`**
2. Execution order: existing chmod plan (`apply_acl_actions`) then
   `apply_named_acl_actions` (setfacl / chmod +a + Python `chmod o-w`)
3. No `shell=True` — argv lists only
4. Missing paths: skip (ok)
5. Missing `setfacl` on Linux: skip ACE (not hard fail); still strip other-write
6. CI never sets `OMO_OS_ACL`

## Non-goals

- Recursive ACL on entire monorepo
- Creating `omo-writers` group
- Windows ACL

## Verification

```bash
# dry-run
omo acl plan --acl --json
# operator only:
# export OMO_OS_ACL=1
# omo acl apply --yes --acl --workspace-root .
pytest projects/omo/tests/test_omo_path_acl.py -q
```

## References

- ADR-0189, ADR-0194, ADR-0196
- `apply_named_acl_actions` in `omo_path_acl.py`
