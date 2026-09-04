---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# omostation · eCOS v6

> Knowledge engineering & AI operations workspace — polyglot monorepo, 5+4+1+1 layered architecture.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/starlink-awaken/omostation/actions/workflows/workspace.yml/badge.svg)](https://github.com/starlink-awaken/omostation/actions)

## Quick Start

```bash
# Read operating guide
cat AGENTS.md

# Run governance gate
make gac-local-gate

# View project registry
cat docs/project-registry.yaml
```

## Architecture

`5+4+1+1` layered model: L0 Protocol → L1 Runtime → L2 Engine → L3 Entry → L4 Self + I0 Weave + M0 Crosscut + X Extension.

> Full contracts: [ARCHITECTURE.md](ARCHITECTURE.md) · Layer index: [docs/generated/project-layer-index.md](docs/generated/project-layer-index.md)

## Entry Points

| Audience | Entry | Source of Truth |
|----------|-------|-----------------|
| Human CLI/Web | `cockpit` | [protocols/port-registry.yaml](protocols/port-registry.yaml) |
| AI Agent | `agora` MCP | [projects/agora/etc/bos-services.yaml](projects/agora/etc/bos-services.yaml) |
| Agent workflow | `bin/agent-workflow.py` | [.omo/_truth/registry/agent-workflows/](.omo/_truth/registry/agent-workflows/) |
| Governance | `omo` CLI | [.omo/standards/](.omo/standards/) |

## Key Directories

| Path | Purpose |
|------|---------|
| `projects/` | Sub-projects (independent submodules) |
| `bin/` | Governance & automation tools |
| `docs/` | Documentation (architecture, plans, reports) |
| `protocols/` | Port/registry SSOTs |
| `.omo/` | Governance state & evidence plane |

## Documentation

- Operating guide: [AGENTS.md](AGENTS.md)
- AI session startup: [CLAUDE.md](CLAUDE.md)
- System navigation: [docs/SYSTEM-INDEX.md](docs/SYSTEM-INDEX.md)
- Architecture contracts: [ARCHITECTURE.md](ARCHITECTURE.md)
- Governance navigation: [GOVERNANCE.md](GOVERNANCE.md)

## Testing

```bash
# Root integration suite
bash tests/integration/run-all.sh

# kairon (Python)
cd projects/knowledge/kairon && make test-diff

# gbrain (TypeScript)
cd projects/knowledge/gbrain && bun test
```

## License

[MIT](LICENSE)
