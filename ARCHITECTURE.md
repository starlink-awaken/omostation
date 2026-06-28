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
| Governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| L0 constraints | [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) |
| X1-X4 rules | [`.omo/_truth/`](.omo/_truth/) |
| Documentation ownership | [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) |

## 2. Layer Model

```
L4  Self layer       -> l4-kernel
L3  Entry layer      -> cockpit / cockpit-ui
I0  Weave layer      -> agora
L2  Engine layer     -> kairon / gbrain / omo / metaos
L1  Runtime layer    -> runtime
L0  Protocol layer   -> ecos
M0  Lifecycle layer  -> model-driven
X   Cross-cutting    -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub / spaces
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
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | Broader product/capability panorama |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | Documentation ownership contract |
