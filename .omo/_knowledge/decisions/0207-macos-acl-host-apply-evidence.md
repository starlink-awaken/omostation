---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0207 — macOS 主机 `omo acl apply --acl` 实机证据

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0205 recorded read-only validation; ADR-0206 shipped `omo-acl-ops-window.sh`.  
Ops still needed **one real apply** on the multi-agent host (`~/Workspace`) with dual-gate.

## Decision / Evidence

Executed on 2026-07-15 against `/Users/xiamingxing/Workspace`:

```bash
export OMO_OS_ACL=1
bash bin/gac/omo-acl-ops-window.sh \
  --workspace-root=/Users/xiamingxing/Workspace \
  --apply --yes --acl
```

| Result | Count / detail |
|--------|----------------|
| `applied_ok` | **6** |
| `applied_fail` | **1** — `group:omo-writers` UUID missing |
| User ACE | `user:xiamingxing allow list,add_file,search,delete,add_subdirectory,file_inherit,directory_inherit` on `.omo/state`, `_control`, `_delivery` |
| chmod plan | 0 mode changes (already 0o755, o-w no-op) |

Post-check (`ls -led`):

```text
.omo/state      0: user:xiamingxing allow list,add_file,search,...
.omo/_control   0: user:xiamingxing allow list,add_file,search,...
.omo/_delivery  0: user:xiamingxing allow list,add_file,search,...
```

## Residual

1. Create macOS group `omo-writers` (or set `OMO_ACL_GROUP` to an existing group) before group ACE is useful.  
2. Do **not** create the group automatically from agents (host admin decision).

## Non-goals

- Auto-apply from cron/doctor
- CI `OMO_OS_ACL=1`

## References

- ADR-0205 / 0206 · `bin/gac/omo-acl-ops-window.sh` · runbook §6
