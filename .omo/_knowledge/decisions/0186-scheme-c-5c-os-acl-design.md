---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0186 — Scheme C Phase 5c: OS 写面 ACL 设计（design-only）

- **Status**: ACCEPTED (design scope only — **no host ACL mutation in this ADR**)
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

Scheme C 5b landed a container executor for stdio spawn isolation.
Phase 5c targets **OS-level write ACL** on `.omo/` and `spaces/` so only
broker processes (omo CLI / approved daemons) can write, closing the gap
left by contract_gatekeeper + direct-omo-io lint (which are process-local).

Host reality:

- Multi-agent worktrees share one repo; launchd/cron/MCP all write `.omo`.
- macOS ACL (`chmod +a`) and Linux POSIX ACL differ; CI runners are ephemeral.
- Wrong ACL bricks concurrent agents and launchd jobs.

## Decision (design freeze)

### D1 — Subjects (who may write)

| Subject | Role | Write surfaces |
|---------|------|----------------|
| `omo` CLI / `omo state sync` | broker of record | `.omo/state/**`, `_control/**` |
| `agent-workflow.py` / GaC tools | governed writers | `.omo/_delivery/**`, workflow run dirs |
| Human operator (interactive shell) | break-glass | full (explicit) |
| Agent language runtimes (node/python ad-hoc) | **deny** direct write | must call broker |

### D2 — Surfaces

| Path | Mode goal | Notes |
|------|-----------|-------|
| `.omo/state/` | broker-write | projection; regenerate via `omo state sync` |
| `.omo/_control/` | broker-write | governance-data.json |
| `.omo/_delivery/` | broker + workflow | evidence artifacts |
| `.omo/_truth/` | human/PR only | SSOT registries — git-owned, not runtime ACL |
| `spaces/` | tenant broker | future multi-tenant |

### D3 — Enforcement layers (ordered)

1. **L0 process policy** (already): direct-omo-io + contract_gatekeeper  
2. **L1 advisory doctor** (Phase 5c-impl step 1): `omo lint path-acl` reports
   world-writable / unexpected owners — **no mutation**  
3. **L2 optional host ACL** (Phase 5c-impl step 2, **opt-in**):
   `omo acl apply --dry-run` then `--apply` on macOS/Linux when
   `OMO_OS_ACL=1`  
4. **L3 container** (5b): untrusted spawn never mounts `.omo` RW

### D4 — Non-goals of this ADR

- No `chmod`/`setfacl` executed by merge of this ADR.
- No change to launchd plists in this design pass.
- No Windows ACL.

## Implementation plan (future PR)

1. `bin/omo` or `projects/omo` doctor: inventory writers + recommend ACL.
2. Profile YAML: `etc/omo-path-acl.yaml` (subjects → paths → mode).
3. Integration test: dry-run only on CI (no privileged ACL).
4. Operator runbook in `docs/METAOS-ECOS-SCHEME-C.md` Phase 5c.

## Acceptance for *design* ADR

- Subjects + surfaces + layering written and linked from Scheme C doc.
- Implement PR must cite this ADR and start with dry-run doctor.

## References

- `docs/METAOS-ECOS-SCHEME-C.md` Phase 5c
- ADR-0181, ADR-0184
- `.omo/standards/agent-mutation-protocol.md` (broker path)
