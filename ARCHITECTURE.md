# ARCHITECTURE.md — eCOS v6 Architecture Contracts

> This document owns stable architecture concepts: layers, dependency direction, routing contracts, and governance boundaries.
> It does not own runtime facts, current phase, health score, test counts, tool counts, service counts, or ports.

## 1. Source-Of-Truth Map

| Fact Type | Authoritative Source |
|-----------|----------------------|
| Runtime state, health, active tasks | [`.omo/state/system.yaml`](.omo/state/system.yaml) |
| Current goals | [`.omo/goals/current.yaml`](.omo/goals/current.yaml) |
| Project metadata | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| BOS services | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Ports | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| Vault paths (iCloud/local) | [`protocols/vault-paths.yaml`](protocols/vault-paths.yaml) |
| X-axis guarantees | [`protocols/x-axis-registry.yaml`](protocols/x-axis-registry.yaml) |
| Governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| L0 constraints | [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) |
| GaC rules (X1-X4) | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) |
| Agent workflows | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| Runtime projection registry | [`.omo/_truth/registry/runtime-projections.yaml`](.omo/_truth/registry/runtime-projections.yaml) |
| Debt registry | [`.omo/_truth/registry/debt.yaml`](.omo/_truth/registry/debt.yaml) |
| Task lifecycle | [`.omo/tasks/README.md`](.omo/tasks/README.md) |
| ADR index & process | [`.omo/_knowledge/decisions/INDEX.md`](.omo/_knowledge/decisions/INDEX.md) · [process standard](.omo/standards/adr-process.md) |
| Registry index (all registries) | [`.omo/_truth/registry/INDEX.md`](.omo/_truth/registry/INDEX.md) |
| Documentation ownership | [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) |
| MOF M3 元元模型 | [`projects/ecos/src/ecos/ssot/mof/m3.yaml`](projects/ecos/src/ecos/ssot/mof/m3.yaml) |
| MOF M1 governance 实例 | [`projects/ecos/src/ecos/ssot/mof/m1/governance/`](projects/ecos/src/ecos/ssot/mof/m1/governance/) |
| MOF capabilities | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| P74 workflow solidification (ADR-0130) | [`.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`](.omo/_knowledge/decisions/0130-p74-workflow-solidification.md) |

## 2. Layer Model

Layer names and project placement are owned by [`docs/project-registry.yaml`](docs/project-registry.yaml) and generated into [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md).

The stable dependency direction remains:

```text
entry surfaces -> routing mesh -> engines/runtime/protocol -> governed state and evidence
```

## 3. Entry Architecture

| Audience | Preferred Entry | Contract |
|----------|-----------------|----------|
| Human operator | `cockpit` CLI/Web | One human-facing entry surface |
| AI agent | `agora` MCP via `bos://` URI | Cross-layer calls go through the mesh |
| Governance automation | `omo` CLI/MCP broker | Governed state mutations are audited |
| Web/API consumers | cockpit-mounted HTTP surfaces | Public web entry remains converged at L3 |

Do not introduce a new top-level human or agent entry without updating the relevant registry, boundary documentation, and governance checks.

## 4. BOS URI Domains

| Domain | URI Prefix | Role |
|--------|------------|------|
| Memory | `bos://memory/` | Knowledge, facts, search, storage |
| Governance | `bos://governance/` | OMO, policy, task/debt/audit flows |
| Analysis | `bos://analysis/` | Research, ontology derivation, code analysis |
| Persona | `bos://persona/` | Persona and personal knowledge bridges |
| Capability | `bos://capability/` | Tools, runtime capabilities, execution surfaces |

The complete machine-readable service map is [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml). Markdown should reference that file rather than duplicating service counts or route inventories.

## 5. Governance Surfaces

```
.omo/                 -> state plane: goals, state, evidence, tasks, audits
projects/omo/         -> kernel plane: schemas, brokers, audit/lint/sync logic
projects/c2g/         -> ingress plane: strategy/pitch-to-task materialization
projects/ecos/        -> protocol plane: MOF and L0 constraints
```

Rules:

- `.omo/` is data and evidence, not a place for new long-lived execution logic.
- State mutations should use OMO CLI/MCP, C2G ingress, or registered brokers.
- New governance surfaces require runtime behavior, registry entries, and validation gates. Documentation alone is not implementation.
- Direct `.omo/` or `spaces/` writes are violations unless routed through an approved audited path.

## 6. Core Flows

```
user or agent -> cockpit or agora -> bos:// route -> target service -> audited response or state transition
external or local source -> kairon ingestion/schema/search -> gbrain or local substrate -> retrieval
intent or pitch -> c2g or OMO broker -> task/debt/audit registry -> validation -> evidence
service definition -> runtime scheduler/matrix/sandbox -> health observation -> governance alert or recovery
```

## 7. Related Documents

| Document | Role |
|----------|------|
| [`README.md`](README.md) | Front door and quick orientation |
| [`AGENTS.md`](AGENTS.md) | Agent/developer operating guide |
| [`CLAUDE.md`](CLAUDE.md) | AI session context loader |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer index |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | System panorama and BOS routing |
| [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) | Architecture deep-dive (modules, data flow, control flow) |
| [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) | Functional capability map (8 domains, 32 capabilities) |
| [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) | Agora BOS URI callchain white-box |
| [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) | Vision and roadmap |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | Documentation ownership contract |
