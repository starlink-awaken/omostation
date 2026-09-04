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

## 8. Closeout & Retrospective

1. Review `git diff --stat`
2. Run verification appropriate for change surface
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs
4. Mention files changed and checks run
5. Do not create commits unless explicitly requested

**复盘+固化 (P74 精神)** — 触发条件: 系统性分析/方案任务 / 多轮返工 / Stop hook 反馈后:
- 诊断前置 4 问: ①反证找了吗 ②查运行时实证了吗 ③读相关 ADR 了吗 ④扫了 bin/ssot + .github/workflows 确认"缺的"真缺
- 三层固化: 教训写 memory + AGENTS.md/CLAUDE.md (协议层) + hook (harness 层)

**Round Workflow**: 详见 [.omo/_knowledge/decisions/0148-round-trip-playbook.md](.omo/_knowledge/decisions/0148-round-trip-playbook.md)

---

> **Pyramid principle**: This file owns **entry + pointers only**. Detailed operational content lives in dedicated docs. No duplication. All original information preserved.
