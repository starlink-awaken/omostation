---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-101
---

# Learning L4 control-plane owner convergence — implementation evidence

## Scope

This wave provides one Workspace owner for the legacy learning control-plane
inspection surface and removes five inactive wrappers from Documents:

- `_control/l4-kernel.sh`
- `_control/vault-healthcheck.sh`
- `_control/daemon/daemon-install.sh`
- `_control/daemon/health-daemon.sh`
- `.githooks/pre-commit-g18`

The nine `_control/executors/*` implementations remain in Documents and are
explicitly pending a separate executor-parity wave. The learning content,
contracts, projections, and launchd declaration remain Documents-owned data.

## Workspace owner

The existing `bin/gac/documents-domain-owner-job.py` entry now exposes
`learning-control-plane` with aggregate JSON modes:

```text
python3 bin/gac/documents-domain-owner-job.py learning-control-plane check --json
python3 bin/gac/documents-domain-owner-job.py learning-control-plane health --json
python3 bin/gac/documents-domain-owner-job.py learning-control-plane all --json
```

Modes are `check`, `health`, `control-loop`, `signals`, `bus`, `sync`,
`lessons`, `decay`, and `all`. The owner is read-only, path-contained, system
Python 3.9 compatible, and delegates decay to the existing
`documents-learning-decay` owner rather than duplicating its scanner.

## Verification and live canary

- TDD RED occurred before the module existed; GREEN completed with 17 focused
  tests, Ruff check, and format check passing.
- The live `all` canary against `/Users/xiamingxing/Documents/@学习进化`
  returned `attention` for `check`, `health`, and delegated `decay`, while
  `control-loop`, `signals`, `bus`, `sync`, and `lessons` were available. The
  result was aggregate-only with `writes_documents: false`.
- The `com.ecos.vault-health` plist passed `plutil -lint`, was confirmed not
  loaded by `launchctl`, and its execution pointer/log paths were updated to
  Workspace without changing `StartInterval` or `RunAtLoad`.
- Fresh consumer evidence remained `status: ok`, active=188,
  content_references=176, workspace_read_owners=12, forbidden_executors=0,
  unmatched=0.

## Physical transaction

L4 preflight selected exactly one regular runtime file for each of the five
scopes. Each was moved to the actual canonical Workspace quarantine, with
source/target fingerprint equality and `permanent_deletion: false`:

| Source | Bytes | Source/target fingerprint | Manifest SHA-256 |
|---|---:|---|---|
| `_control/l4-kernel.sh` | 13735 | `83e0f2a4cae30da65e14afdd06068dec8ef236da27eb56ca506c08937d1ac579` | `921b16106325717946a9e36f42db583a707a5c502d5ae713db0e337b53c46f05` |
| `_control/vault-healthcheck.sh` | 3192 | `8bfb47e1a0ab966efa0f91bc10278466765554208c8ae31a0ceea78f731efae5` | `88b67ebc77162d5224b3a897e4c0bab3d30ce2f01177979bdd2ae1326a8276c3` |
| `_control/daemon/daemon-install.sh` | 877 | `90237684f7e3fc3e44d8a7409ff1353ecad1ef39cd3e088bf14b35e0fe205a9d` | `c0270194f527fd83b676ab9476f3655b360a1b83f3ada4af482709f25b9d4cca` |
| `_control/daemon/health-daemon.sh` | 1179 | `05d00f305500b0b201347d8b67473b0c1525125d8eefb4724afb035ce9fd3afc` | `5cdaff127c276de2dd8c65032925e2e535511af9317be39c6c7f1fa810830eff` |
| `.githooks/pre-commit-g18` | 960 | `5e78867312bedd489377510d7a1e71ffd6b6dfa1bf699f5dd33803f5ba0c16d2` | `f0e9b5a4f249fc08b6aac7e6ee0223aeb1209f3322c363c44c7708475f9cbeff` |

Postflight shows `_control` runtime=9 (the nine unaddressed executors),
`.githooks` runtime=0, and no source handles in `lsof`. The canonical root
`runtime/quarantine/*/` ignore rule protects all manifests.

## Mainline closure

Root PR #2701 merged to root `origin/main` as
`bbfecdfd44547f36290dc995b2f11d79dbd2d83d`. Required checks all completed
successfully, including integration, gac, interface, and governance-verify.
The root gitlink remains aligned with the already merged Runtime child main.

## Boundary

The migration family remains `learning-runtime: in_progress` with
`owner_parity: partial`: read-only, guarded content operations, and the L4
control-plane owner are now available, but KEMS/Minerva/G18 executor parity
and the final full-tree physical purity gate remain open.
