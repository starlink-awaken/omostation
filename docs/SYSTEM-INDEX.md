---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# SYSTEM-INDEX.md — 全景导航

> Single navigation hub. All docs route through here.

## Quick Start

1. This file → global structure
2. Target project `AGENTS.md` → operating rules
3. `ARCHITECTURE.md` → architecture contracts

## SSOT Navigation

| Need | Source |
|------|--------|
| Project metadata | [docs/project-registry.yaml](docs/project-registry.yaml) |
| Runtime state | [.omo/state/system.yaml](.omo/state/system.yaml) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Port assignments | [protocols/port-registry.yaml](protocols/port-registry.yaml) |
| GaC rules | [.omo/_truth/registry/governance-checks.yaml](.omo/_truth/registry/governance-checks.yaml) |
| ADR decisions | [.omo/_knowledge/decisions/INDEX.md](.omo/_knowledge/decisions/INDEX.md) |
| BOS services | [projects/agora/etc/bos-services.yaml](projects/agora/etc/bos-services.yaml) |
| L0 constraints | [projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) |
| Document templates | [docs/templates/](docs/templates/) (ssot/derived/ephemeral) |

## Domain Directories

| Domain | Location |
|--------|----------|
| Architecture blueprints | [docs/architecture/](docs/architecture/) |
| Operations SOPs | [docs/operations/](docs/operations/) |
| Active plans | [docs/plans/](docs/plans/) |
| Governance & ADR | [docs/governance/](docs/governance/) |
| Reports | [docs/reports/](docs/reports/) |
| Design specs | [docs/superpowers/specs/](docs/superpowers/specs/) |
| Design plans | [docs/superpowers/plans/](docs/superpowers/plans/) |
| Evidence | [docs/evidence/](docs/evidence/) |
| ISA artifacts | [isa/](isa/) |

## Layer Model

`5+4+1+1`: L0 Protocol → L1 Runtime → L2 Engine → L3 Entry → L4 Self + I0 Weave + M0 Crosscut + X Extension.

> Full layer contracts: [ARCHITECTURE.md](ARCHITECTURE.md) · Dependency rules: [docs/layer-contract.yaml](docs/layer-contract.yaml)

## Key Tools

| Category | Location |
|----------|----------|
| GaC governance | `bin/gac/` |
| SSOT checks | `bin/ssot/` |
| Agent workflow | `bin/agent-workflow.py` |
| Resident agent | `make resident-status` |
| BCOS | `make bcos-evolve` |

> Full tool catalog: [bin/README.md](bin/README.md)

## Scene Execution

- Scene cards: [docs/superpowers/specs/](docs/superpowers/specs/)
- Journey specs: [docs/superpowers/specs/](docs/superpowers/specs/) (journey-*.md)
- Resident routes: `projects/omo/src/omo/resident/resident-routes.yaml`

## Maintenance

| Event | Action | Priority |
|-------|--------|----------|
| New project | Update project-registry.yaml | P1 |
| New tool | Register in script-registry | P2 |
| ADR decision | Add to .omo/_knowledge/decisions/ | P2 |
| Architecture change | Update ARCHITECTURE.md | P1 |
