# Closeout — 2026-07-15 ACL ops window + session hygiene

## Local ops

- Released broken/merged `ws-ecos-health-skill` (PR #379 already on main; working tree was mass-deleted noise)
- Worktree claim now shows next ADR hint + default omo/cockpit/agora init (ADR-0204)

## Landed

| Item | Path |
|------|------|
| Ops window script | `bin/gac/omo-acl-ops-window.sh` |
| ADR-0206 | dual-gate apply guidance |
| Runbook / bootstrap | point to ops window + install-hooks check |
| AGENTS | one-liners for ops window + hooks |

## Verify

```bash
bash bin/gac/omo-acl-ops-window.sh
bash bin/gac/omo-acl-ops-window.sh --probe-macos
# must refuse without env:
bash bin/gac/omo-acl-ops-window.sh --apply --yes ; echo exit=$?   # expect 3
```
