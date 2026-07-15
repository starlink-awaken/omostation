---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0187 — Scheme C 5c L1: `omo lint path-acl` 只读巡检

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + omo

## Context

ADR-0186 froze OS ACL design and ordered enforcement layers. Step 1 of the
implementation plan is an **advisory doctor** that never mutates host ACL.

## Decision

1. New module `omo.omo_path_acl` + CLI: **`omo lint path-acl`**
2. Profile SSOT: `projects/omo/etc/omo-path-acl.yaml` (override: `OMO_PATH_ACL_PROFILE`)
3. Surfaces scanned: `.omo/state`, `_control`, `_delivery`, `_truth`, `spaces`
4. Findings: world-writable, mode 0777, optional missing, group-write on git-owned
5. **Default non-strict**: warnings do not fail CI; `--strict` / `OMO_PATH_ACL_STRICT=1` escalates
6. **`mutation: false` always** — no chmod/setfacl/chown

## Non-goals

- L2 `omo acl apply` (still future, opt-in `OMO_OS_ACL=1`)
- Windows ACL
- launchd plist changes

## Verification

```bash
cd projects/omo
uv run pytest tests/test_omo_path_acl.py -q
uv run python -m omo.cli lint path-acl --workspace-root ../.. --json
```

## References

- ADR-0186
- `projects/omo/src/omo/omo_path_acl.py`
- `docs/METAOS-ECOS-SCHEME-C.md` Phase 5c
