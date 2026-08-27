# LAYER-INDEX.md — eCOS v6 Layer Index

> Human-readable placement index for the 5+4+1+1 architecture.
> Runtime status and project metadata are not owned here.

## Source Of Truth

| Need | Read |
|------|------|
| Current phase, health, active tasks | [`.omo/state/system.yaml`](.omo/state/system.yaml) |
| Project metadata and counts | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| Full architecture contracts | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| BOS routes | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Ports | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |

## Layers

The machine-derived layer table is [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md). It is generated from [`docs/project-registry.yaml`](docs/project-registry.yaml) with:

```bash
python3 "bin/project-layer-index.py" --write
```

## BOS Domains

| Domain | Prefix | Purpose |
|--------|--------|---------|
| Memory | `bos://memory/` | Knowledge and factual substrates |
| Governance | `bos://governance/` | Governance, task, debt, audit flows |
| Analysis | `bos://analysis/` | Research, derivation, code analysis |
| Persona | `bos://persona/` | Persona and personal-knowledge bridges |
| Capability | `bos://capability/` | Tools, runtime execution, capability registry |

The concrete service inventory belongs to [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml).

## X-Axis Guarantees

| Axis | Question | Registry |
|------|----------|----------|
| X1 Audit | Is the operation traceable and safe? | [`.omo/_truth/x1-governance-policies.yaml`](.omo/_truth/x1-governance-policies.yaml) · [standard](.omo/standards/x1-swarm-trust-protocol.md) |
| X2 Freshness | Is the state fresh enough? | [`.omo/_truth/x2-freshness-rules.yaml`](.omo/_truth/x2-freshness-rules.yaml) · [standard](.omo/standards/x2-budget-integrity-standard.md) |
| X3 Value | Is the work worth the cost? | [`.omo/_truth/x3-value-stack.yaml`](.omo/_truth/x3-value-stack.yaml) · [standard](.omo/standards/x3-value-stack-standard.md) |
| X4 Consistency | Are rules and surfaces aligned? | [`.omo/_truth/x4-consistency-rules.yaml`](.omo/_truth/x4-consistency-rules.yaml) · [standard](.omo/standards/x4-hitl-mutation-standard.md) |

## Update Rule

Update this file only when the stable layer placement changes. If only a count, port, health value, test result, version, or service inventory changed, update the relevant SSOT instead.
