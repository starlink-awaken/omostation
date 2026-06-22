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
| `.omo/capabilities/system-packages.yaml` | Package baseline records |
| `.omo/capabilities/agent-clis.yaml` | Agent CLI baseline |
| `pilot-contract.yaml` | Selected Phase 12 pilot interface contract |
| `article-samples.yaml` | Article ingestion policy samples |
| `package-baseline.yaml` | Package dry-run baseline |
| `omo-governance-surfaces.yaml` | `.omo` 顶层资产分类 + `projects/omo`/`projects/c2g` 联动治理注册表 |

## Rule

Registry records are evidence for discovery and binding. They do not authorize live mutation or external installation.
