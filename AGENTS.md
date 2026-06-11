# AGENTS.md — Workspace Development Guide

> Multi-project knowledge engineering & research workspace (root directory).

## Project Overview

This root directory is a **multi-project workspace** organized in the 5+4+1+1 (eCOS v5) architecture:

| Layer | Project | Stack | Location | Status |
|-------|---------|-------|----------|--------|
| L4 | `l4-kernel` | Python (uv, pytest) | `projects/l4-kernel/` | 🟢 Active — 自我层管理面 · 21域 · 250 tests · 43 MCP tools |
| — | `model-driven` | Python (uv, pytest) | `projects/model-driven/` | 🟢 Active — 全生命周期模型驱动平台 · 24 M2类型 · 7阶段 · 12工具 · 190 tests |
| L3 | `cockpit` | Python (uv, pytest) | `projects/cockpit/` | 🟢 Active — 统一入口 (CLI + Web) · 33 tests |
| I0 | `agora` | Python (uv, pytest) | `projects/agora/` | 🟢 Active — MCP Hub · 172 src, 1371 tests |
| L2 | `kairon` | Python (uv, pytest) | `projects/kairon/` | 🟢 Active — 知识引擎 · 19 active (+6 archived) packages |
| L2 | `gbrain` | TypeScript (bun) | `projects/gbrain/` | 🟢 Active — 知识数据库 · 163K TS |
| L2 | `omo` | Python (uv, pytest) | `projects/omo/` | 🟢 Active — 治理面 · 100+ tests · **AppendOnlyLog 5 consumers + fcntl 跨进程锁** |
| L2 | `metaos` | Python (uv, pytest) | `projects/metaos/` | 🟢 Active — 编排引擎 · 188 tests |
| L1 | `runtime` | Python (uv, pytest) | `projects/runtime/` | 🟢 Active — 运行时 · matrix + scheduler + kei |
| L0 | `ecos` | Python (uv, pytest) | `projects/ecos/` | 🟢 Active — SSB 协议 · 195 tests |
| — | `hermes-console` | TypeScript | `projects/hermes-console/` | 🟡 待集成至 cockpit |
| — | `SharedBrain` | Python | `projects/_archived/SharedBrain-original/` | ⚪ Archived |
| — | `agentmesh` | TypeScript (bun) | `projects/_archived/` | ⚪ Archived — 已拆分为独立项目 (agora/runtime/cockpit/aetherforge) |

**Also contains:**
- `.omo/` — Workspace governance (goals, state, standards, tasks, audits)
- `spaces/` — User-space / tenant-space manifests and ownership boundaries
- `data/` — Shared databases (substrates: `db/`, `kos/`, `sharedbrain/`, `backups/`)
- `runtime/` — Ephemeral runtime residue (logs, temp state)
- `tests/integration/` — Integration test suite (3 scripts + 1 Python test)
- `scripts/` — Utility scripts and governance automation (独立 git 仓库)
- `bin/` — Executable tools (workspace CLI, verify scripts)

## Essential Commands

### Root Makefile

> 用 `make help` 查看全部可用 target。

```bash
# Run kairon tests (all 19 active packages)
make kairon-test

# Fast diff test — only packages changed since HEAD (推荐日常使用)
make test-diff

# Parallel test — all packages, up to 4 concurrent
make test-parallel

# Ruff lint check
make kairon-lint

# Ruff format
make kairon-format

# Install kairon
make kairon-build

# Clean build artifacts
make kairon-clean

# Governance verification chain
make governance-verify
```

### Per-Project Commands

```bash
# kairon (projects/kairon/)
cd projects/kairon && make test           # All packages
cd projects/kairon && make test-fast      # Unit tests only
cd projects/kairon && make test-diff      # Only packages changed since HEAD (推荐日常)
cd projects/kairon && make test-parallel  # All packages, up to 4 concurrent
cd projects/kairon && make test-e2e       # E2E: Postgres + gbrain + kairon (容器化)
cd projects/kairon && make lint           # Ruff check
cd projects/kairon && make format         # Ruff format
cd projects/kairon && make clean          # Clean __pycache__, .ruff_cache, .venv

# kairon — E2E 环境管理
cd projects/kairon && make e2e-up         # 启动 E2E 环境 (Postgres:5433, gbrain:3000)
cd projects/kairon && make e2e-down       # 停止并清理 E2E 环境

# kairon — 单个包/单个测试
cd projects/kairon/packages/eidos && uv run pytest tests/ -q
cd projects/kairon/packages/kos && uv run pytest tests/test_xxx.py -q
cd projects/kairon/packages/kos && uv run pytest tests/ -k "keyword" -q

# agora (projects/agora/)
cd projects/agora && uv run pytest tests/ -q            # 1165/1371 pass
cd projects/agora && uv run pytest tests/ -k "keyword" -q

# cockpit (projects/cockpit/)
cd projects/cockpit && uv run pytest tests/ -q          # 498/514 pass
cd projects/cockpit && uv run pytest tests/ -k "keyword" -q

# runtime (projects/runtime/)
cd projects/runtime && uv run pytest tests/ -q          # 171/176 pass
cd projects/runtime && make sync-state                  # 同步状态到 ~/runtime/
cd projects/runtime && make shellcheck                  # Shell 脚本检查
cd projects/runtime && make fmt                         # Ruff format

# omo (projects/omo/)
cd projects/omo && uv run pytest tests/ -q               # 100+ tests (AppendOnlyLog 5 轮收口后)

# AppendOnlyLog 5 个 consumer (Round 1-5 收尾):
#   omo_audit, omo_bos_metrics, omo_sync, omo_alert, omo_event
# 详细: .omo/_knowledge/management/append-only-log-pattern-2026-06-09.md

# 关键命令 (omo-cli):
omo bos status          # BOS invoke metrics (p50/p95/p99)
omo bos discover        # Pydantic 验证后的注册表
omo bos health          # endpoint + metrics 健康报告
omo observability log tail --type knowledge [--file X]   # 多文件 tail
omo event emit --type X --source Y --payload '...'      # 用户面向样板
omo governance          # 6 项治理审计 (期望 100.0 A+)

# metaos (projects/metaos/)
cd projects/metaos && uv run pytest tests/ -q            # 188/188 pass

# ecos (projects/ecos/)
cd projects/ecos && uv run pytest tests/ -q              # 112/122 pass

# gbrain (projects/gbrain/)
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local
```

## Architecture

### 5+3+1 分层快照与 BOS URI 挂载图谱 (Phase 33 · 2026-06-06 确立)

eCOS v5 已进入大一统阶段。通过 `agora` 作为服务网格 (Mesh) 动态反向代理，所有的项目和包都被抽象为 5 大 BOS URI 命名空间：

*   **域 1：记忆与事实源 `bos://memory`** ── `kos` (跨域搜索)、`kronos` (摄取管线)、`gbrain` (TS知识库)、`sot-bridge` (SSOT 桥接)
*   **域 2：治理与律法 `bos://omo`** ── `metaos` (决策/免疫)、`eidos` (Schema约束)、`protocols-layer` (触发器规则)、`omo` (治理引擎)
*   **域 3：认知与推演 `bos://analysis`** ── `ontoderive` (推导)、`minerva` (深度研究)、`codeanalyze` (AST理解)
*   **域 4：人格与心智 `bos://persona`** ── `sot-bridge` (SharedBrain 桥接)
*   **域 5：能力与生态 `bos://forge`** ── `forge` (集市与注册表)、`runtime` (KEI 沙箱执行)

```
L4 自我层 ── ~/Documents/驾驶舱/CARDS/ (SQLite) + ~/Documents/学习进化/ (MD)
L3 入口层 ── cockpit (CLI 13 + MCP + Web) ── 终端消费 BOS URI
I0 织层   ── agora (动态反向代理 Mesh) ── 拦截并路由 bos:// 流量，触发 eidos 校验与 metaos 免疫
L2 引擎面 ── kairon 19 packages / gbrain / omo / metaos ── 以后台 Daemon 提供 MCP 资源
L1 运行时 ── runtime ── 受控沙箱，随 protocols 规则产生 Ephemeral Agents
L0 协议   ── ecos ── SSB 协议层，承载系统决策的 Immutable Log 上链与涌现计算
```

### 项目测试健康度

| 项目 | 总测试 | 通过 | 通过率 |
|------|--------|------|--------|
| agora | 1371 | 1165 | 85.0% |
| cockpit | 514 | 498 | 96.9% |
| kairon | 4199 | 4157 | 99.8% |
| runtime | 176 | 171 | 97.2% |
| omo | 530 | 302 | 57%* |
| metaos | 188 | 188 | 100% |
| ecos | 122 | 112 | 91.8% |
| gbrain | ~9,737 | ~9,700 | ~99.6% |

*OMO: 225 skipped (需要完整环境), 有效通过率 97.4%

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

Located at `tests/integration/` in root (4 active scripts, 简化为当前可运行集合):

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

GitHub Actions workflows — **19/20 子模块 + 根仓库全部 CI 覆盖** (spaces 为纯 YAML 配置仓，不包括测试):

**kairon (3)**: `ci.yml`, `ci.yml.bak`, `publish.yml`
**omo (2)**: `ci.yml`, `audit-baseline-monthly.yml`
**现有独立项目 CI (7)**: `cockpit-ci.yml`, `agora-ci.yml`, `ecos-ci.yml`, `metaos-ci.yml`, `runtime-ci.yml`, `gbrain-ci.yml` (4 文件), `aetherforge-ci.yml`
**新增 CI (2026-06-10 补齐)**: `l4-kernel/ci.yml`, `model-driven/ci.yml`, `llm-gateway/ci.yml`, `omo-debt/ci.yml`, `swarm-engine/ci.yml`, `compute-mesh/ci.yml`, `aetherforge-swarm-ext/ci.yml`, `family-hub/ci.yml`, `hermes-console/ci.yml`
**根仓库 (23)**: `workspace.yml`, `omostation-governance.yml`, 及其他跨项目工作流

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
9. **Pre-commit 已扩展至全项目** — pre-commit hook (~/.hermes/scripts/git-hooks/pre-commit) 现在覆盖 kairon/agora/cockpit/ecos/omo/metaos/runtime，仅检查本次提交的 Python 文件。
10. **快速差异测试: `make test-diff`** — 只测试自 HEAD 以来修改过的包，取代全量 `make test-fast`。修改单个包时用此命令。
11. **修改多项目时**: 优先用各项目的 `make test-diff`（kairon）或 `uv run pytest -k` 定向测试，而非全量 `make test`，节省 CI 时间和开发迭代周期。

12. **Agent 默认入口**: Agent 始终通过 **agora MCP :7431** 接入系统。`resolve_bos_uri()` 是唯一推荐的 MCP 调用方式。cockpit/l4-kernel/runtime 的独立 stdio MCP 入口已标记 deprecated，仅供向后兼容。

13. **三入口架构**: 人类用 `cockpit CLI`，Agent 用 `agora MCP :7431`，Web/API 用 `cockpit HTTP :8090`。不再使用其他入口。

14. **BOS URI 是跨层调用的唯一路径**: 所有跨项目、跨层调用必须通过 `bos://` URI 经由 Agora 路由。不要直接调用子进程或内部 MCP。

## 📋 子模块管理 (2026-06-10 确立)

### 子模块指针更新

```bash
# 1. 进入子模块，在子仓库中开发
cd projects/agora
git checkout main
git pull origin main
# ... 开发、测试、提交 ...

# 2. 更新根仓库指针
cd ~/Workspace
git add projects/agora
git commit -m "chore: bump agora to <short-sha> — <改了什么>"

# 3. 推送
git push origin main
```

### 指针管理原则

| 场景 | 做法 |
|:-----|:-----|
| **日常开发** | 在子模块内直接开发，提交到子模块→更新根指针→推送 |
| **同步最新** | `git submodule update --recursive --remote` 拉所有子模块最新 |
| **新人克隆** | `git clone --recursive` 一次拉取全部 |
| **新增子模块** | `git submodule add <url> projects/<name>` → 更新 AGENTS.md |
| **移除子模块** | `git submodule deinit -f projects/<name>` → `git rm -f projects/<name>` → 更新 AGENTS.md |
| **紧急修复** | 在子模块开 PR，给根仓库留 TODO 等 PR merge 后更新指针 |

### 关键约束

- **根仓库 `.gitmodules` 是 SSOT** — 20 个子模块的版本锁定在这里
- **子模块指针不自动推进** — 每次更新需手动 `git add + commit`，保证可追溯
- **推送顺序**：先推送子模块 → 再推送根仓库（否则别人看到的是指向不存在 commit 的指针）
- **子模块脏状态**：`git submodule status` 带 `+` 前缀表示指针已落后于实际 HEAD，需更新
- **启用 CI**：每个子模块在 `.github/workflows/ci.yml` 有独立 CI，推 GitHub 自动触发

## SSOT 铁律

> **同一事实不在多处写。知识面文档引用事实面数据时，必须使用相对路径指针，不得复制内容。**

| 数据 | 唯一读源 | 禁止行为 |
|------|---------|---------|
| 任务 | `.omo/tasks/active/` (YAML) | 从知识面文档读取任务状态 |
| 系统状态 | `.omo/state/system.yaml` | 从旧快照文件取状态 |
| 目标 | `.omo/goals/current.yaml` | 直接修改 goals (仅人类可改) |
| 标准 | `.omo/standards/` | 从计划文档读标准 |

## 路由规则

| 场景 | 路由 |
|------|------|
| 找知识/跨域搜索 | 优先用 KOS (`kos/`, `kairon/kos` 包) |
| 工作公文 | `~/Documents/公文/CLAUDE.md` |
| 借调事务 | `~/Documents/国转中心/CLAUDE.md` |
| 随手记录 | WPS Note，标签路由 |
| 涉及端口 | 先查 `protocols/port-registry.yaml` → 确认未占用 → 注册新端口 → 使用环境变量 `{SERVICE}_PORT` |

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
- `bin/` — Executable tools:
  - `bin/workspace` — Workspace CLI 入口
  - `bin/verify-omo.sh` — 治理验证链 (= `make governance-verify`)
  - `bin/omo-health.py` — OMO 健康检查
  - `bin/register-mcp.py` — MCP 服务注册
  - `bin/git-safe` — Git 安全操作包装
  - `bin/scan_hardcoded.sh` — 硬编码路径扫描
  - `bin/arcnode-validate` — ArcNode 验证
- `.github/workflows/` — CI configurations (20 workflows, 9/9 项目覆盖)
- `.hermes/` — Hermes-related scripts and adapters

## 🤖 Agentic Protocols & BOS URIs (eCOS v5 Mandatory Rules)

**All AI Agents operating in this workspace MUST follow these architectural constraints:**

1. **NO RAW CONFIG EDITS**: Do not manually edit configuration files in `.omo/` or database files to change system state.
2. **USE AGORA MESH**: All cross-layer operations must go through the Agora Service Mesh (`agora`).
3. **BOS URI ABSTRACTION**: State mutations and reads must use `bos://` URIs instead of direct file I/O where applicable.
4. **INTROSPECTION**: If you don't know what tools or resources are available, invoke `read_resource("bos://agora/registry")` to dump the current Mesh state.
5. **MUTATION**: To change the state of an object managed by the mesh, use the `mutate_resource(uri, payload, action)` tool instead of ad-hoc tools.
6. **COGNITIVE FRAMEWORKS**: MetaOS dynamically loads cognitive frameworks (like BDSK or Six Hats) from the L0 MOF model (`ecos/src/ecos/ssot/mof/m1/cognitive_framework/`). When executing complex planning, adhere strictly to the injected framework personas.
7. **MANDATORY ATOMIC COMMITS**: All agents MUST immediately run `git commit` after making logical changes, especially to documentation or `.omo` files. The system relies on Git post-commit hooks for knowledge extraction (`mof-extract`). Failing to commit will break the system's memory loop and is a critical failure.

## 🏛️ OMO 强制流程 (eCOS v5 Governance Mandatory)

**所有操作，无论入口 (Agent/MCP/CLI/Cron)，必须通过 OMO 治理机制:**

### 操作前 (Pre-operation)
1. **Phase 检查**: 确认操作与当前 Phase 目标对齐 (`omo state` 或 `l4_omo_phase_context`)
2. **CARDS 检查**: `cockpit cards --check` 或 `l4_cards_check` 确认无冲突
3. **约束检查**: 确认不违反 X1-X4 约束 (`l4_omo_pre_check`)

### 操作后 (Post-operation)
1. **Audit 记录**: 所有变更写入 OMO Audit 日志
2. **Task 同步**: 如涉及 CARDS, 同步 Task 状态
3. **Debt 注册**: 如发现异常/违规, 注册 OMO Debt (`l4_omo_debt_register`)
4. **Signal 发射**: 通过 l4-kernel SignalBus 发射操作信号

### 违规处理
- Schema violation → 立即修复 + Debt 注册
- 新鲜度告警 → 48h 内响应
- 信号 🔴 → 立即响应 + Debt 注册
- CARDS 阻塞 → 升级优先级 + 通知相关域

### 各层 OMO 职责
| 层 | Phase | Task | Debt | Audit |
|----|:---:|:---:|:---:|:---:|
| L4 l4-kernel + 21域 | ✅ | ✅ | ✅ | ✅ |
| L3 cockpit | ✅ | — | — | — |
| I0 agora | — | — | ✅ | ✅ |
| L2 kairon | ✅ | ✅ | ✅ | ✅ |
| L2 omo | 中枢 | 中枢 | 中枢 | 中枢 |
| L2 metaos | ✅ | — | ✅ | ✅ |
| L1 runtime | — | — | ✅ | ✅ |
| L0 ecos | — | — | ✅ | ✅ |

## Reading Before Working

- **For incoming AI Agents**: YOU MUST READ `projects/omo/CLAUDE.md` to understand how to interact with the OMO v4.0 Operating System. Do NOT manually edit `.omo` files. Use the Contract-based Dispatch workflow. AND adhere to the Agentic Protocols listed above.
- **For kairon work**: Read `projects/kairon/CLAUDE.md` + `projects/kairon/AGENTS.md` for monorepo conventions. Package structure in `projects/kairon/pyproject.toml`.
- **For gbrain work**: Read `projects/gbrain/AGENTS.md` + `projects/gbrain/CLAUDE.md`
- **For governance**: Read `.omo/standards/` for architectural standards
- **For integration tests**: Read individual test scripts in `tests/integration/`

## Panoramic View

- **Full feature map / architecture / core flows / module deps / user journeys / integration surfaces**: See [`docs/PANORAMA.md`](./docs/PANORAMA.md) (6-section overview with Mermaid diagrams, P58-P71 14 phase steady state snapshot).
