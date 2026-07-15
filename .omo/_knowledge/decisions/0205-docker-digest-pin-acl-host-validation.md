---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0205 — 5b Docker image digest pin + macOS ACL host validation evidence

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team + agora + omo

## Context

Scheme C 5b shipped `docker_image: python:3.13-slim` as a **floating tag**.  
Ops residual: pin production digest. Separately, 5c L2 ACE apply needed **host
evidence** that macOS `chmod +a` works (Linux `setfacl` N/A on this workstation).

## Decision

### D1 — Pin default docker image by digest

SSOT (`projects/agora/etc/container-executor-profiles.yaml` + builtin default):

```text
python:3.13-slim@sha256:bffeb7bd6a85767587059c6ba23e1e9122078e3aa3fa836099171b9bb5a9bb00
```

- Pulled on operator host 2026-07-15 (Docker Desktop darwin/arm64).
- Override still allowed: `AGORA_SPAWN_DOCKER_IMAGE` (floating or other pin).
- Refresh procedure: pull tag → `docker image inspect … RepoDigests` → update YAML + `DEFAULT_DOCKER_IMAGE` + this ADR date.

### D2 — macOS ACL host validation (read-only ops evidence)

On macOS 26.5.1 (arm64), workspace root sample:

| Check | Result |
|-------|--------|
| `omo lint path-acl` | ok, 0 warn/halt; modes 0o755 on profiled surfaces |
| `omo acl plan` | 0 chmod actions (no other-write to strip) |
| `omo acl plan --acl` | generates `chmod +a` for broker user + optional `omo-writers` group |
| `setfacl` | **not present** (expected macOS) |
| Temp-file `chmod +a "$USER allow read,write,execute"` | **OK** (verified with `ls -le`) |
| Host `apply --yes --acl` | **not executed** this session (opt-in ops window only) |

Conclusion: L1 doctor/plan paths are healthy; named ACE **can** be applied on this
macOS host when operators set `OMO_OS_ACL=1`. Group ACE requires pre-created
`omo-writers` (or `OMO_ACL_GROUP`).

## Non-goals

- Applying ACL to shared multi-agent host without operator presence
- CI enabling `OMO_OS_ACL`
- Replacing default backend (`local` remains CI-safe)

## Verification

```bash
# image pin
rg -n 'sha256:bffeb7bd' projects/agora/etc/container-executor-profiles.yaml
# ACL (read-only)
PYTHONPATH=projects/omo/src python3 -m omo.cli lint path-acl --workspace-root . --json
PYTHONPATH=projects/omo/src python3 -m omo.cli acl plan --acl --json | head
```

## References

- ADR-0184 container executor · ADR-0187/0189/0198 path-acl · runbook `docs/operations/omo-path-acl-runbook.md`
