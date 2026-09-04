---
schema_version: specification/v1
spec_version: 1.0.0
title: Learning L4 control-plane owner convergence
bet_id: BET-Y1Q3-T10-101
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Learning L4 control-plane owner convergence

## Intent

Move the remaining learning control-plane implementations out of Documents
without creating another operating system. Workspace owns one aggregate owner
entry; Documents keeps control Markdown, contracts, signals, and declarations.

## Scope

The selected legacy files are:

- `_control/l4-kernel.sh`
- `_control/vault-healthcheck.sh`
- `_control/daemon/daemon-install.sh`
- `_control/daemon/health-daemon.sh`
- `.githooks/pre-commit-g18`

The nine `_control/executors/*` implementations remain untouched for a
separate parity wave because they represent distinct KEMS/Minerva/validation
behaviors rather than one control-plane contract.

## Canonical owner

```text
python3 bin/gac/documents-domain-owner-job.py learning-control-plane check --json
python3 bin/gac/documents-domain-owner-job.py learning-control-plane health --json
python3 bin/gac/documents-domain-owner-job.py learning-control-plane all --json
```

The owner supports `check`, `health`, `control-loop`, `signals`, `bus`, `sync`,
`lessons`, `decay`, and `all`. It is read-only, emits aggregate JSON, and
delegates decay to the already merged Workspace learning owner. `attention`
means an observed health finding; it must not be coerced into exit 0.

## Safety and migration

- All paths are resolved below the supplied Documents root; Documents and
  Workspace roots must be disjoint and symlink scopes are refused.
- The daemon and hook wrappers are not scheduled by this change. Existing
  launchd/cron state is observed but not changed.
- Each selected source is moved, never deleted, to the canonical Workspace
  `runtime/quarantine` with hash/mode/byte manifest and reversible rollback.
- Content, contracts, projections, signals, and the nine executor files remain
  in Documents. The registry remains `learning-runtime: in_progress`.
