---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0189 — Scheme C 5c L2: `omo acl plan|apply`（opt-in chmod）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

ADR-0187 delivered L1 read-only `path-acl` doctor. L2 needs a safe apply path
without bricking multi-agent hosts (ADR-0186).

## Decision

| Item | Choice |
|------|--------|
| CLI | `omo acl plan` (default) · `omo acl apply --yes` · `omo acl status` |
| Gate | **`OMO_OS_ACL=1`** required for apply; also requires `--yes` |
| Mutation scope | **chmod only** — strip other-write; map 0777 → 0775/0664 |
| Forbidden | setfacl, chown, launchd, recursive tree walk beyond profile surfaces |
| CI | never sets `OMO_OS_ACL`; tests use `force=True` unit path only |

## Verification

```bash
omo acl plan --workspace-root . --json
OMO_OS_ACL=1 omo acl apply --yes --workspace-root .   # operator only
pytest projects/omo/tests/test_omo_path_acl.py -q
```

## References

- ADR-0186, ADR-0187
- `projects/omo/src/omo/omo_acl.py`
- `projects/omo/src/omo/omo_path_acl.py` (`plan_acl_actions` / `apply_acl_actions`)
