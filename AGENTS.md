# AGENTS.md — Workspace Development Guide

> Multi-project knowledge engineering & research workspace (root directory).

## Project Overview

This root directory is a **multi-project workspace** organized in the 5+3+1 (eCOS v5) architecture:

| Layer | Project | Stack | Location | Status |
|-------|---------|-------|----------|--------|
| L3 | `cockpit` | Python (uv, pytest) | `projects/cockpit/` | 🟢 Active — 统一入口 (CLI + Web) |
| I0 | `agora` | Python (uv, pytest) | `projects/agora/` | 🟢 Active — MCP Hub · 98 src, 1112 tests |
| L2 | `kairon` | Python (uv, pytest) | `projects/kairon/` | 🟢 Active — 知识引擎 · 25 packages |
| L2 | `gbrain` | TypeScript (bun) | `projects/gbrain/` | 🟢 Active — 知识数据库 · 163K TS |
| L2 | `omo` | Python (uv, pytest) | `projects/omo/` | 🟢 Active — 治理面 · 82 src files |
| L2 | `metaos` | Python (uv, pytest) | `projects/metaos/` | 🟢 Active — 编排引擎 · 163 tests |
| L1 | `runtime` | Python (uv, pytest) | `projects/runtime/` | 🟢 Active — 运行时 · matrix + scheduler + kei |
| L0 | `ecos` | Python (uv, pytest) | `projects/ecos/` | 🟢 Active — SSB 协议 · 122 tests |
| — | `hermes-console` | TypeScript | `projects/hermes-console/` | 🟡 待集成至 cockpit |
| — | `SharedBrain` | Python | `projects/_archived/SharedBrain-original/` | ⚪ Archived |
| — | `agentmesh` | TypeScript (bun) | `projects/_archived/` | ⚪ Archived — 100% 迁移至 kairon |

**Also contains:**
- `.omo/` — Workspace governance (goals, state, standards, tasks, audits)
- `spaces/` — User-space / tenant-space manifests and ownership boundaries
- `data/` — Shared databases (substrates: `db/`, `kos/`, `sharedbrain/`, `backups/`)
- `runtime/` — Ephemeral runtime residue (logs, temp state)
- `tests/integration/` — Integration test suite (11 scripts + 4 Python tests)
- `scripts/` — Utility scripts and governance automation (独立 git 仓库)
- `bin/` — Executable tools (workspace CLI, verify scripts)

## Essential Commands

### Root Makefile

```bash
# Run kairon tests (all 31 packages)
make kairon-test

# Ruff lint check
make kairon-lint

# Install kairon
make kairon-build

# Governance verification chain
make governance-verify
```

### Per-Project Commands

```bash
# kairon (projects/kairon/)
cd projects/kairon && make test         # All packages
cd projects/kairon && make test-fast   # Unit tests only
cd projects/kairon && make lint       # Ruff check

# agora (projects/agora/)
cd projects/agora && uv run pytest tests/ -q   # 1105/1112 pass

# cockpit (projects/cockpit/)
cd projects/cockpit && uv run pytest tests/ -q  # 445/490 pass

# runtime (projects/runtime/)
cd projects/runtime && uv run pytest tests/ -q  # 171/175 pass

# omo (projects/omo/)
cd projects/omo && uv run pytest tests/ -q      # 221/400+ (182 skipped)

# metaos (projects/metaos/)
cd projects/metaos && uv run pytest tests/ -q   # 163/163 pass

# ecos (projects/ecos/)
cd projects/ecos && uv run pytest tests/ -q     # 113/122 pass

# gbrain (projects/gbrain/)
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local
```

## Architecture

### 5+3+1 分层快照 (Phase 28 · 2026-06-06 审计)

```
L4 自我层 ── ~/Documents/驾驶舱/CARDS/ (SQLite) + ~/Documents/学习进化/ (MD)
L3 入口层 ── cockpit (CLI 13 + MCP 🔴 + HTTP 8) 🟡 MCP 待修复
I0 织层   ── agora (CLI 35 + MCP 42 + HTTP 30+) ✅ 99.37% tests
L2 引擎面 ── kairon 25 packages (630 shared-lib tests) ✅
L2 治理面 ── omo (CLI 28 + MCP 10) ✅
L2 记忆面 ── gbrain 163K TS (MCP 67) ✅
L2 编排   ── metaos (CLI 5 + MCP 11) ✅
L1 运行时 ── runtime (CLI 3 + MCP 30 + HTTP 5) ✅
L0 协议   ── ecos (CLI 3 + HTTP dashboard :9090) + protocols 16 YAML 🟡

X1 审计 ── KEI sandbox (runtime) | X2 抗熵 ── scheduler autoheal | X3 价值栈 ── llm-gateway cost
```

### 项目测试健康度

| 项目 | 总测试 | 通过 | 通过率 |
|------|--------|------|--------|
| agora | 1112 | 1105 | 99.37% |
| cockpit | 490 | 445 | ~90% |
| kairon | 1810+ | ~1750+ | ~97% |
| runtime | 175 | 171 | 100% |
| omo | 400+ | 221 | 100%* |
| metaos | 163 | 163 | 100% |
| ecos | 122 | 113 | 92.6% |
| gbrain | TS | TS | N/A |

*OMO: 182 skipped (需要完整环境)

### 对外接入能力

| 项目 | CLI 入口 | MCP 工具 | HTTP 端口 | 依赖 |
|------|---------|---------|-----------|------|
| agora | `agora` | 42+ tools | :7422/:7431/:8080 | fastmcp, httpx, aiohttp |
| cockpit | `cockpit`, `workspace` | 15 | stdlib http | runtime |
| runtime | `runtime`, `ecos-matrix-scheduler` | 30 | FastAPI | fastmcp, apscheduler |
| omo | `omo`, `cards`, `omo-debt` | 10 | — | httpx, pyyaml |
| metaos | `metaos` | 11 | — | structlog |
| ecos | `ecos-ssb`, `ecos-dashboard` | — | :9090 | requests, jinja2 |
| gbrain | `gbrain` | 67 | — | bun |

### Key Dependencies

- **I0 agora** provides MCP service discovery / routing / proxy (all cross-layer communication)
- **L1 runtime** provides service registry, health monitoring, KEI sandbox
- **L2 kairon** provides knowledge engineering pipeline (eidos/kos/minerva/...)
- **L2 gbrain** provides Postgres knowledge database (67 MCP tools)
- **L2 omo** provides governance CLI, debt registry, task management

## Testing Pattern

### Integration Tests

Located at `tests/integration/` in root (5 active scripts, 简化为当前可运行集合):

```bash
# Run all integration tests
bash tests/integration/run-all.sh

# Active test scripts:
bash tests/integration/test-02-pipeline.sh
bash tests/integration/test-05-pricing.sh
bash tests/integration/test-10-runtime-check.sh
python3 tests/integration/test_runtime_e2e.py
```

### CI Configuration

GitHub Actions workflows in `.github/workflows/` (**18 workflows**, 9/9 项目覆盖):

**kairon (7)**: `pytest.yml`, `phase11-ci.yml`, `integration.yml`, `quality.yml`, `ruff-check.yml`, `config-check.yml`, `publish-pypi.yml`
**omo (3)**: `governance-check.yml`, `omo-autopilot.yml`, `constraint-validation.yml`
**runtime (1)**: `meta-model-check.yml`
**独立项目 CI (5, 2026-06-06 新建)**: `cockpit-ci.yml`, `agora-ci.yml`, `metaos-ci.yml`, `ecos-ci.yml`, `gbrain-ci.yml`
**跨项目 (2)**: `sharedbrain-kairon-integration.yml`, `workspace.yml`

## Gotchas

1. **kairon uses uv** — Not pip/poetry. `uv sync` to install, `uv add <package>` to add deps.

2. **Python 3.13+** — kairon targets Python 3.13+ (`ruff` config shows `target-version = "py313"`)

3. **gbrain needs bun** — Uses Bun as runtime, not Node/npm:
   ```bash
   cd projects/gbrain && bun install
   ```

4. **Database paths are gitignored** — `data/db/` and each project's local DB files are `.gitignore`d

5. **Cross-project dependencies** — Each repo is independent; changes to one don't automatically reflect in others

6. **No root-level test command** — Tests run per-project (via project Makefiles)

7. **SharedBrain 数据层在 `data/sharedbrain/`** — 旧 `projects/SharedBrain/` 已归档至 `_archived/SharedBrain-original/`

8. **!!! 关键修改必须立即 git commit !!!** — kairon 项目历史中有 `git reset` 操作会静默回滚未提交的修改。AI Agent 每次修改文件后必须立即 commit，否则修改可能丢失。参见 FLOW-OMC-REVERT。
9. **Pre-commit 已改为仅检查已暂存文件** — pre-commit hook("~/.hermes/scripts/git-hooks/pre-commit")从 `ruff check packages/` 改为 `git diff --cached --name-only | ruff check`，只检查本次提交的文件。
10. **快速差异测试: `make test-diff`** — 只测试自 HEAD 以来修改过的包，取代全量 `make test-fast`。修改单个包时用此命令。

## Style Conventions

### Python (kairon)

- **Formatter**: ruff (`ruff format packages/`)
- **Linter**: ruff (`ruff check packages/`)
- **Line length**: 120
- **Target**: Python 3.13+
- **Import sorting**: isort enabled via ruff

### TypeScript (gbrain)

- **Formatter/Auto-fix**: bun fmt / bun run lint:fix
- **Testing**: bun test + bun run ci:local

## File Organization

- `projects/*/` — Independent project repos
- `.omo/` — Workspace governance docs (read for context, don't modify without clear reason)
- `spaces/` — User-space / tenant-space manifests and routing boundaries
- `data/` — Shared data layer (`db/`, `kos/`, `sharedbrain/`, `backups/`)
- `runtime/` — Ephemeral runtime residue; avoid storing durable truth here
- `tests/integration/` — E2E test scripts
- `scripts/` — Utility scripts and automation (独立 git 仓库, `omo/` + `shell/`)
- `bin/` — Executable tools
- `.github/workflows/` — CI configurations (11 workflows)
- `.hermes/` — Hermes-related scripts and adapters

## Reading Before Working

- **For incoming AI Agents**: YOU MUST READ `projects/omo/CLAUDE.md` to understand how to interact with the OMO v4.0 Operating System. Do NOT manually edit `.omo` files. Use the Contract-based Dispatch workflow.
- **For kairon work**: Read `projects/kairon/CLAUDE.md` + `projects/kairon/AGENTS.md` for monorepo conventions. Package structure in `projects/kairon/pyproject.toml`.
- **For gbrain work**: Read `projects/gbrain/AGENTS.md` + `projects/gbrain/CLAUDE.md`
- **For governance**: Read `.omo/standards/` for architectural standards
- **For integration tests**: Read individual test scripts in `tests/integration/`
