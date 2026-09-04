---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# AGENTS.md — Workspace Development Guide

> Root operating guide. Full policy details in [GOVERNANCE.md](GOVERNANCE.md). Session startup in [CLAUDE.md](CLAUDE.md). Tool catalog in [bin/README.md](bin/README.md).

## 0. First Steps

1. Read [CLAUDE.md](CLAUDE.md) for session startup
2. Read target project `AGENTS.md` / `CLAUDE.md`
3. Check `git status --short`
4. For requirement iterations: run `bootstrap → start --profile → claim` first (ADR-0203)
5. For governed state: use OMO/C2G brokers, not direct `.omo` writes

## 1. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. No long-lived execution logic. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint |
| `projects/c2g/` | Strategy ingress: pitch/bet → governed tasks |
| `projects/ecos/` | Protocol and MOF layer |
| `spaces/` | User/tenant-space manifests (governed config) |
| `scripts/` | Removed (ADR-0394). Tools live in `bin/` |
| `runtime/` | Runtime logs. Do not edit manually. |
| `kos/` | Knowledge index. Runtime product. |
| `bin/` | Governance tools (gac-*, doc-ssot-*, agent-workflow) |
| `protocols/` | SSOT registries. Read-only for agents. |

## 2. Documentation SSOT Contract

| Document | SSOT For |
|----------|----------|
| [README.md](README.md) | Front door & quick orientation |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layer contracts, BOS URI, DFSQ/SFOP slots |
| [docs/project-registry.yaml](docs/project-registry.yaml) | Project metadata (layer/stack/status) |
| [protocols/port-registry.yaml](protocols/port-registry.yaml) | Port assignments |
| [.omo/_truth/registry/governance-checks.yaml](.omo/_truth/registry/governance-checks.yaml) | GaC rules (32 CR-* rules) |
| [.omo/state/system.yaml](.omo/state/system.yaml) | Runtime state |

> **Rule**: Do not hard-code phase, health score, test counts, port values, or rule inventories in Markdown. Use pointers.

## 3. Git & Submodule Discipline

- No direct commits to main — use worktree + PR (`gac-worktree.sh claim <session>`)
- No `sed -i` for adding/removing entries — use Python read→check→modify→write
- Submodule commits: `cd projects/X && git add && commit` → `push` → `cd root && git add projects/X && commit && push`

Full policy: [GOVERNANCE.md §6](GOVERNANCE.md)

## 4. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` |
| Root governance docs | `make gac-local-gate` + `make ssot-guardian` |
| Python code | `uv run pytest` or project `make test` |
| kairon | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun test` |
| cockpit-ui | `npm run build` or `bun run build` |
| Cross-project | Test every touched consumer |

## 5. Key Commands Reference

```bash
# Agent workflow
uv run python bin/agent-workflow.py bootstrap

# Governance gate
make gac-local-gate

# SSOT checks
make doc-ssot-lint && make ssot-guardian

# Architecture slots
python3 bin/gac/check-sfop-slots.py --json
```

Full command catalog: [bin/README.md](bin/README.md)

## 6. Resident Agent & BCOS

- Resident: `make resident-status` · Routes: `projects/omo/src/omo/resident/resident-routes.yaml`
- BCOS: `make bcos-evolve` · Spec: [docs/architecture/bcos-system-v1.md](docs/architecture/bcos-system-v1.md)

## 7. Historical Patterns & Architecture

- Architecture theory: [docs/architecture/dao-fa-shu-qi.md](docs/architecture/dao-fa-shu-qi.md)
- Runtime slots: [docs/architecture/os-operating-pattern-v1.md](docs/architecture/os-operating-pattern-v1.md)
- Patterns: [.omo/_knowledge/patterns/](.omo/_knowledge/patterns/)

---

> **Pyramid principle**: This file owns **entry + pointers only**. Detailed operational content lives in dedicated docs. No duplication.
