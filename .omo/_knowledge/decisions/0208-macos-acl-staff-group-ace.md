---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0208 — macOS group ACE via `OMO_ACL_GROUP=staff`（无 sudo 路径）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0207 applied user ACE on `~/Workspace` but **failed** `group:omo-writers` (group missing).  
Creating `omo-writers` needs interactive `sudo` (no passwordless agent path).

## Decision

For **single-operator macOS hosts**, prefer **Option B**:

```bash
export OMO_ACL_GROUP=staff          # user already in staff (gid 20)
export OMO_OS_ACL=1
bash bin/gac/omo-acl-ops-window.sh --workspace-root="$HOME/Workspace" --apply --yes --acl
```

### Evidence (2026-07-15)

| Metric | Value |
|--------|--------|
| Target | `/Users/xiamingxing/Workspace` |
| `applied_ok` | **7** |
| `applied_fail` | **0** |
| Group ACE | `group:staff` on `.omo/_delivery` |
| User ACE | `user:xiamingxing` on `.omo/state`, `_control`, `_delivery` |

```text
ls -led .omo/_delivery
  0: group:staff allow list,add_file,search,delete,add_subdirectory,file_inherit,directory_inherit
  1: user:xiamingxing allow list,add_file,search,...
```

## When to still create `omo-writers`

Multi-user machines where `staff` is too broad — follow  
`docs/operations/omo-writers-group-setup.md` **Option A** (human + sudo).

## Non-goals

- Agent-run `sudo dseditgroup`
- Changing default profile group away from `omo-writers` in SSOT (env override is enough)

## References

- ADR-0206 / 0207 · `omo-writers-group-setup.md` · `omo-acl-ops-window.sh`
