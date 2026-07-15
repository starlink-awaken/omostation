---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0206 — `omo-acl-ops-window` 运维窗口脚本

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0205 validated macOS `chmod +a` and left host apply to an ops window. Operators still
need a **single guided entry** that:

1. Defaults to dry-run (lint + plan + plan --acl)
2. Never auto-exports `OMO_OS_ACL=1` (CI / agent safety)
3. Requires dual confirmation for mutation (`OMO_OS_ACL=1` env + `--yes`)

## Decision

Add `bin/gac/omo-acl-ops-window.sh`:

| Mode | Behavior |
|------|----------|
| default | dry-run report only |
| `--probe-macos` | temp-file `chmod +a` probe |
| `--apply --yes` | `omo acl apply --yes` (chmod plan) |
| `--apply --yes --acl` | + named ACE apply |

Script refuses apply when `OMO_OS_ACL` ≠ `1` or `--yes` missing. Uses `PYTHONPATH=projects/omo/src` so it works in partial worktrees without full uv project graph.

## Non-goals

- Auto-apply from doctor/cron
- Creating `omo-writers` group
- Windows ACL

## Verification

```bash
bash bin/gac/omo-acl-ops-window.sh
bash bin/gac/omo-acl-ops-window.sh --probe-macos
# mutation (ops only):
# export OMO_OS_ACL=1 && bash bin/gac/omo-acl-ops-window.sh --apply --yes --acl
```

## References

- ADR-0189 / 0198 / 0205 · `docs/operations/omo-path-acl-runbook.md`
