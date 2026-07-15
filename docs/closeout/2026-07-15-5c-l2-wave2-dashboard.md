# Closeout — 2026-07-15 5c L2 + Wave2 dashboard contract

## Landed

| Item | Detail |
|------|--------|
| ADR-0189 | `omo acl plan|apply|status` opt-in chmod |
| omo | plan/apply in omo_path_acl + omo_acl CLI |
| ADR-0190 | `c2g.wave2.dashboard.v1` + `cockpit wave2` |
| c2g | `dashboard_export` module |
| cockpit | `commands/wave2.py` L3 entry |

## Commands

```bash
omo acl plan --json
OMO_OS_ACL=1 omo acl apply --yes   # operator only
cockpit wave2 dashboard
```

## Deferred

- setfacl / macOS ACL entries
- cockpit-ui React heatmap (JSON ready)
