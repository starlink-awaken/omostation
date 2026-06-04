# AGENTS.md — Workspace Development Guide

> Multi-project knowledge engineering & research workspace (root directory).

## Project Overview

This root directory is a **multi-project workspace** containing independent git repos:

| Project | Stack | Location | Status |
|---------|-------|----------|--------|
| `kairon` | Python (uv, pytest) | `projects/kairon/` | 🟢 Active — 25 packages |
| `gbrain` | TypeScript (bun) | `projects/gbrain/` | 🟢 Active — Knowledge Brain |
| `SharedBrain` | Python | `projects/_archived/SharedBrain-original/` | ⚪ Archived — 代码已迁移至 kairon，数据层在 `data/sharedbrain/` |
| `agentmesh` | TypeScript (bun) | `projects/_archived/` | ⚪ Archived — 100% 迁移至 kairon |
| `hermes-console` | TypeScript | `projects/hermes-console/` | 🟡 独立项目，待评估 |
| `_archived` | — | `projects/_archived/` | ⚪ 24 项已迁移旧项目备份 |

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

# gbrain (projects/gbrain/) — See AGENTS.md in that directory
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local

# agentmesh (projects/agentmesh/) — 已归档，参照 kairon 替代包
```

## Architecture

### Workspace Plane Structure (OMO v4.0)

1. **Governance layer** (`.omo/`) — The K0 Data Plane (goals, state, tasks). DO NOT manually modify; use `omo-cli`.
2. **Engine layer** (`projects/omo/`) — The K1 Ribosome Engine. Contains `omo-cli` for GC, Ledger, and Bridge.
3. **Capability layer** (`projects/`) — independent repos with own build/test/lint contracts.
4. **User-space layer** (`spaces/`) — tenant / workspace manifest boundaries.
5. **Data substrate** (`data/`) — shared databases, indexes, snapshots.
6. **Runtime residue** (`runtime/`) — ephemeral logs, temp state.

### Key Dependencies

- **gbrain** depends on **agentmesh** (SDK)
- **kairon/agora** provides service discovery / routing
- **kairon/sharedbrain-standalone** replaces legacy SharedBrain code

## Testing Pattern

### Integration Tests

Located at `tests/integration/` in root:

```bash
# Run all integration tests
bash tests/integration/run-all.sh

# Individual test scripts:
bash tests/integration/test-01-identity.sh
bash tests/integration/test-02-pipeline.sh
bash tests/integration/test-03-constraints.sh
bash tests/integration/test-04-phase-lock.sh
bash tests/integration/test-05-pricing.sh
bash tests/integration/test-06-trace.sh
bash tests/integration/test-07-collab-agentmesh.sh
bash tests/integration/test-08-knowledge-pipeline.sh
bash tests/integration/test-09-agora-degrade.sh
bash tests/integration/test-10-runtime-check.sh
bash tests/integration/test-11-i0-integration.sh

# Python tests
python3 tests/integration/test-e2e-phase1.py
python3 tests/integration/test-fault-injection.py
python3 tests/integration/test-user-journeys.py
python3 tests/integration/test-perf-baseline.py
```

### CI Configuration

GitHub Actions workflows in `.github/workflows/` (11 workflows):
- `pytest.yml` — kairon Python 3.14 测试
- `phase11-ci.yml` — kairon 全包基线测试 (Python 3.13 + uv)
- `integration.yml` — 集成测试 (3 个 Python 版本矩阵)
- `quality.yml` / `ruff-check.yml` — Lint 和格式化
- `workspace.yml` — 全工作区 CI
- `governance-check.yml` — 治理层验证
- `constraint-validation.yml` — arcnode 约束验证
- `config-check.yml` — Agora 配置校验
- `sharedbrain-kairon-integration.yml` — 跨项目集成测试
- `phase11-ci.yml` — Phase 11 基线 CI

## Gotchas

1. **kairon uses uv** — Not pip/poetry. `uv sync` to install, `uv add <package>` to add deps.

2. **Python 3.13+** — kairon targets Python 3.13+ (`ruff` config shows `target-version = "py313"`)

3. **agentmesh needs bun** — Uses Bun as runtime, not Node/npm:
   ```bash
   cd projects/agentmesh && bun install
   ```

4. **Database paths are gitignored** — `data/db/` and each project's local DB files are `.gitignore`d

5. **Cross-project dependencies** — Each repo is independent; changes to one don't automatically reflect in others

6. **No root-level test command** — Tests run per-project (via project Makefiles)

7. **SharedBrain 数据层在 `data/sharedbrain/`** — 旧 `projects/SharedBrain/` 已归档至 `_archived/SharedBrain-original/`

## Style Conventions

### Python (kairon)

- **Formatter**: ruff (`ruff format packages/`)
- **Linter**: ruff (`ruff check packages/`)
- **Line length**: 120
- **Target**: Python 3.13+
- **Import sorting**: isort enabled via ruff

### TypeScript (gbrain, agentmesh)

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
