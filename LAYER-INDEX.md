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

| Layer | Role | Projects / Surfaces |
|-------|------|---------------------|
| L4 Self | Domain-facing self layer | `l4-kernel` |
| L3 Entry | Human CLI/Web and user-facing orchestration | `cockpit`, `cockpit-ui` |
| I0 Weave | BOS routing and MCP hub | `agora` |
| L2 Engine | Knowledge, memory, governance, orchestration | `kairon`, `gbrain`, `omo`, `metaos` |
| L1 Runtime | Scheduling, health, sandbox, service lifecycle | `runtime` |
| L0 Protocol | Protocol, MOF, L0 constraints | `ecos` |
| M0 Lifecycle | Model-driven lifecycle framework | `model-driven` |
| X Cross-cutting | Shared capabilities across layers | `aetherforge`, `c2g`, `bus-foundation`, `omo-debt`, `observability`, `family-hub`, `spaces` |

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
| X1 Audit | Is the operation traceable and safe? | [`.omo/_truth/x1-governance-policies.yaml`](.omo/_truth/x1-governance-policies.yaml) |
| X2 Freshness | Is the state fresh enough? | [`.omo/_truth/x2-freshness-rules.yaml`](.omo/_truth/x2-freshness-rules.yaml) |
| X3 Value | Is the work worth the cost? | [`.omo/_truth/x3-value-stack.yaml`](.omo/_truth/x3-value-stack.yaml) |
| X4 Consistency | Are rules and surfaces aligned? | [`.omo/_truth/x4-consistency-rules.yaml`](.omo/_truth/x4-consistency-rules.yaml) |

## Update Rule

Update this file only when the stable layer placement changes. If only a count, port, health value, test result, version, or service inventory changed, update the relevant SSOT instead.
