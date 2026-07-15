# Closeout — 2026-07-15 ops residual (ACL host + docker digest)

## Short-term worktree

- `work/short-term-improvements` already **merged** as PR #376; worktree gone. No further action.

## Landed

| Item | Detail |
|------|--------|
| ADR-0205 | Docker digest pin + macOS ACL host validation evidence |
| agora `05ba491` | `DEFAULT_DOCKER_IMAGE` + YAML pin `python:3.13-slim@sha256:bffeb7bd…` |
| Runbook §6 | macOS validation table |
| Scheme C roadmap | 5b pin + 5c ACE validation marked ✅ |

## Host evidence (this machine)

- path-acl: all ok
- chmod +a: works
- setfacl: N/A
- docker Desktop available; image pulled for digest capture
- **did not** run `OMO_OS_ACL=1 apply` on real `.omo/`

## Verify

```bash
rg -n 'bffeb7bd' projects/agora/etc/container-executor-profiles.yaml
PYTHONPATH=projects/omo/src python3 -m omo.cli lint path-acl --workspace-root . --json | head
```
