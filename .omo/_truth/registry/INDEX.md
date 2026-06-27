---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-28
---

# Capability registry

> Status: active
> Owner: governance
> Runtime path: `.omo/capabilities/`
> Legacy compatibility: `.omo/registry/` is retained only for historical evidence lookup

## Files

| File | Purpose |
|------|---------|
| `.omo/capabilities/projects-capabilities.yaml` | Core workspace capability records |
| `.omo/capabilities/sharedwork-sample.yaml` | External/SharedWork sample records for Phase 14 triage |
| `.omo/capabilities/system-packages.yaml` | Package baseline records (merged package-baseline.yaml) |
| `.omo/capabilities/agent-clis.yaml` | Agent CLI baseline |
| `pilot-contract.yaml` | Selected Phase 12 pilot interface contract |
| `article-samples.yaml` | Article ingestion policy samples |
| `omo-governance-surfaces.yaml` | `.omo` 顶层资产分类 + `projects/omo`/`projects/c2g` 联动治理注册表 |
| `mutation-surfaces.yaml` | Brokered write entry points (CLI entrypoints → mutation targets) |
| `internal-write-profiles.yaml` | Worker/dispatch internal write paths (runtime writes) |
| `direct-io-baseline.yaml` | Grandfathered direct I/O baseline (policy: must stay empty) |
| `governance-checks.yaml` | GaC declarative rule registry (ADR-0106) + X1-X4 checker classes |
| `governance-alerts.yaml` | X1-X4 alert rules when checks fail |
| `task-policies.yaml` | Task YAML field validators (red-line policies) |
| `debt.yaml` | Tech debt item catalog + dashboard/report refs |
| `dependency-baseline.yaml` | Workspace-wide min version constraints |
| `mof-capabilities.yaml` | 4-layer MOF tool registry |
| `workers.yaml` | Worker role/lease/transport policy |
| `compute/engines.yaml` | LLM runtime engine + scheduling endpoints |
| `compute/nodes.yaml` | Physical compute nodes |

## Write Surface Registries Boundary

Three registries describe write paths from different angles:

| Registry | View | When to update |
|----------|------|----------------|
| `omo-governance-surfaces.yaml` | Architectural/top-down: which planes/assets exist and who may write them | New asset or plane added |
| `mutation-surfaces.yaml` | Operational/bottom-up: which CLI entrypoints perform brokered writes | New broker write command added |
| `internal-write-profiles.yaml` | Runtime/worker: which worker-internal paths are permitted | New worker write path added |

## Rule

Registry records are evidence for discovery and binding. They do not authorize live mutation or external installation.
