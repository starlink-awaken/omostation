# AGENTS.md — Workspace Development Guide

> Multi-project knowledge engineering & research workspace (root directory).
> 最后更新: 2026-06-17

> **运行时 SSOT**: `.omo/state/system.yaml` · `.omo/goals/current.yaml`
> **治理面 SSOT**: `.omo/standards/omo-governance-surfaces.md` · `.omo/_truth/registry/omo-governance-surfaces.yaml`
> **L0/X1-X4 SSOT**: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` · `.omo/_truth/x1-governance-policies.yaml` · `.omo/_truth/x2-freshness-rules.yaml` · `.omo/_truth/x3-value-stack.yaml` · `.omo/_truth/x4-consistency-rules.yaml`
> **项目架构文档契约**: `projects/*/ARCHITECTURE.md` / `CALLCHAIN.md` / `BOUNDARY.md` 只保留骨架、入口、边界与 SSOT 指针，不回填运行时快照

## 架构总览 (5+4+1+1)

> 说明: 本节只保留稳定分层骨架，不维护易漂移的路由数、测试数、健康分、phase 值。
> 变动事实以 `.omo/state/system.yaml`、`.omo/_truth/*`、`docs/PANORAMA.md` 为准。

```
L4 自我层  ── l4-kernel
L3 入口层  ── cockpit (唯一人类 CLI / Web 入口)
              hermes-console (挂载到 cockpit /hermes/*)
              dashboard_server (挂载到 cockpit /dash/*)
I0 织层    ── agora (BOS URI 路由与 MCP Hub)
L2 引擎面  ── kairon + gbrain + omo + metaos
L1 运行时  ── runtime
L0 协议层  ── ecos
X 横切框架 ── aetherforge + model-driven + c2g + bus-foundation + omo-debt + observability + spaces + family-hub
归档能力    ── llm-gateway / compute-mesh / swarm-engine / aetherforge-swarm-ext（能力已并入现有框架）
```

### BOS URI 5 域

```
bos://memory/     ← kos/kronos/gbrain/vault       — 记忆与事实源
bos://governance/ ← omo/metaos/eidos/cockpit       — 治理与律法
bos://analysis/   ← minerva/ontoderive/codeanalyze — 认知与推演
bos://persona/    ← core-models/sot-bridge         — 人格与心智
bos://capability/ ← forge/runtime                  — 能力与生态
```

**BOS 路由定义位置**: `projects/agora/etc/bos-services.yaml` (声明式 YAML 注册表, 71 条目)
**BOS URI 解析器**: `projects/agora/src/agora/mcp/resolver/` (6 模块: services/bos_registry/pool/adapter/api/__init__)

### 架构决策

| 决策 | 结论 |
|:----|:-----|
| L3 收敛 | cockpit 是唯一 Web 入口；agora-dashboard 独立入口已收敛，仓库仅保留历史快照；hermes-console 与 dashboard_server 作为子应用挂载。 |
| CLI 收敛 | cockpit = 唯一人类 CLI 入口。其他 CLI (agora/runtime/ecos-ssb/omo/metaos) 保留为程序接口 |
| 子模块 | 18 子模块，各自独立 git 仓库。根仓库只追踪元配置和子模块指针 |
| 治理收敛 | `.omo/` = state plane；`projects/omo/` = governance kernel；`projects/c2g/` = strategic ingress |

### 治理写入收敛

- `.omo/` 只承载状态、证据、知识与交付，不承载新的治理执行逻辑。
- 持久化写入必须优先走 `projects/omo` 内核能力或 `projects/c2g` 战略入口；脚本层只负责编排，不再直接落盘 `.omo/`。
- `omo lint direct-omo-io` 是 `.omo` / `spaces` 直写拦截门；当前 `.omo/_truth/registry/direct-io-baseline.yaml` 已清零，必须持续保持 `entries: []`。
- broker 写入入口、worker/internal 写路径、task policy 机器注册表分别收敛到:
  - `.omo/_truth/registry/mutation-surfaces.yaml`
  - `.omo/_truth/registry/internal-write-profiles.yaml`
  - `.omo/_truth/registry/task-policies.yaml`
- 新增治理写面时，必须同时补 runtime 实现、truth registry、lint/CI 门禁；只改文档不算落地。

### X1-X4 SSOT 链

| 维度 | 权威读源 | 派生消费文档 |
|:----|:---------|:-------------|
| X1 Audit / Boundary | `.omo/_truth/x1-governance-policies.yaml` | `AGENTS.md`, `.omo/INDEX.md`, `.omo/standards/omo-governance-surfaces.md` |
| X2 Freshness | `.omo/_truth/x2-freshness-rules.yaml` | `AGENTS.md`, `.omo/_truth/INDEX.md` |
| X3 Value / Cost | `.omo/_truth/x3-value-stack.yaml` | `AGENTS.md`, `docs/PANORAMA.md` |
| X4 Consistency | `.omo/_truth/x4-consistency-rules.yaml` | `AGENTS.md`, `.omo/standards/omo-governance-surfaces.md` |
| L0 Enforcement | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 所有上层文档只引用，不复制规则正文 |

## Project Overview

> 本节是工作区清单，不是运行时事实源。项目测试数、路由数、工具数若与实际不一致，
> 以各子项目自身 README / pyproject / CI / 运行时探针为准。

This root directory is a **multi-project workspace** organized in the 5+4+1+1 (eCOS v6) architecture:

| Layer | Project | Stack | Location | Status |
|-------|---------|-------|----------|--------|
| L4 | `l4-kernel` | Python (uv, pytest) | `projects/l4-kernel/` | 🟢 Active — 自我层管理面 |
| L3 | `cockpit` | Python (uv, pytest) | `projects/cockpit/` | 🟢 Active — 统一入口 |
| I0 | `agora` | Python (uv, pytest) | `projects/agora/` | 🟢 Active — MCP Hub · BOS 路由 |
| L2 | `kairon` | Python (uv, pytest) | `projects/kairon/` | 🟢 Active — 知识引擎 |
| L2 | `gbrain` | TypeScript (bun) | `projects/gbrain/` | 🟢 Active — 知识数据库 |
| L2 | `omo` | Python (uv, pytest) | `projects/omo/` | 🟢 Active — 治理面 |
| L2 | `metaos` | Python (uv, pytest) | `projects/metaos/` | 🟢 Active — 编排引擎 |
| L1 | `runtime` | Python (uv, pytest) | `projects/runtime/` | 🟢 Active — 运行时 |
| L0 | `ecos` | Python (uv, pytest) | `projects/ecos/` | 🟢 Active — 协议层 |
| X | `aetherforge` | Python (uv, pytest) | `projects/aetherforge/` | 🟢 Active — 能力与算力框架 |
| X | `model-driven` | Python (uv, pytest) | `projects/model-driven/` | 🟢 Active — 全生命周期模型驱动 |
| X | `c2g` | Python (uv) | `projects/c2g/` | 🟢 Active — 战略需求引擎 (V2P → C2G) |
| X | `bus-foundation` | Python (uv, pytest) | `projects/bus-foundation/` | 🟢 Active — Omni-Bus (Data/Event/Control) |
| X | `omo-debt` | Python (uv, pytest) | `projects/omo-debt/` | 🟢 Active — 技术债务评分 CLI |
| X | `observability` | Docker | `projects/observability/` | 🟢 Active — Langfuse 可观测性 |
| X | `family-hub` | Python (FastMCP) | `projects/family-hub/` | 🟢 Active — 家庭数字枢纽 |
| X | `hermes-console` | TypeScript (Vite) | `projects/hermes-console/` | 🟢 Active — 已挂载至 cockpit `/hermes/*` |
| X | `spaces` | YAML | `projects/spaces/` | 🟢 Active — 空间配置 |

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
cd projects/agora && uv run pytest tests/ -q
cd projects/agora && uv run pytest tests/ -k "keyword" -q

# cockpit (projects/cockpit/)
cd projects/cockpit && uv run pytest tests/ -q
cd projects/cockpit && uv run pytest tests/ -k "keyword" -q

# workspace iterate (C2G 双擎编排流宏入口)
# 用于将 MetaOS 发散期的创意安全降维并导入 OMO CARDS
workspace iterate "设计缓存层"
workspace iterate "测试隔离区" --mock

# runtime (projects/runtime/)
cd projects/runtime && uv run pytest tests/ -q
cd projects/runtime && make sync-state                  # 同步状态到 ~/runtime/
cd projects/runtime && make shellcheck                  # Shell 脚本检查
cd projects/runtime && make fmt                         # Ruff format

# omo (projects/omo/)
cd projects/omo && uv run pytest tests/ -q

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
cd projects/metaos && uv run pytest tests/ -q

# ecos (projects/ecos/)
cd projects/ecos && uv run pytest tests/ -q

# gbrain (projects/gbrain/)
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local
```

## Architecture

### BOS URI 挂载骨架

> 这里只保留稳定域划分。具体服务映射以 `projects/agora/src/agora/mcp/resolver/services.py`
> 与 `docs/PANORAMA.md` 为准。

*   **域 1：记忆与事实源 `bos://memory`** ── `kos` (跨域搜索)、`kronos` (摄取管线)、`gbrain` (TS知识库)、`sot-bridge` (SSOT 桥接)
*   **域 2：治理与律法 `bos://governance`** ── `omo`、`metaos`、`eidos`、`cockpit`
*   **域 3：认知与推演 `bos://analysis`** ── `ontoderive` (推导)、`minerva` (深度研究)、`codeanalyze` (AST理解)
*   **域 4：人格与心智 `bos://persona`** ── `sot-bridge` (SharedBrain 桥接)
*   **域 5：能力与生态 `bos://capability`** ── `aetherforge`、`runtime`、`bus` (Omni-Bus: data/event/control)

```
L4 自我层 ── l4-kernel
L3 入口层 ── cockpit
I0 织层   ── agora
L2 引擎面 ── kairon / gbrain / omo / metaos
L1 运行时 ── runtime
L0 协议   ── ecos
```

### 项目测试状态

> 测试数量与通过率高度漂移，不在此处维护。
> 以各项目本地 `pytest` / `bun test` / CI 结果为准。

### 对外接入能力

| 项目 | CLI 入口 | MCP 工具 | HTTP 端口 | 依赖 |
|------|---------|---------|-----------|------|
| agora | `agora` | MCP Hub | `:7422/:7431/:8080` | fastmcp, httpx, aiohttp |
| cockpit | `cockpit`, `workspace` | 统一入口 | stdlib http | runtime |
| runtime | `runtime`, `ecos-matrix-scheduler` | runtime MCP | FastAPI | fastmcp, apscheduler |
| omo | `omo`, `cards`, `omo-debt` | governance CLI | — | httpx, pyyaml |
| metaos | `metaos` | orchestration CLI | — | structlog |
| ecos | `ecos-ssb`, `ecos-dashboard` | protocol tooling | — | requests, jinja2 |
| gbrain | `gbrain` | knowledge database MCP | — | bun |

### Key Dependencies

- **I0 agora** provides MCP service discovery / routing / proxy (all cross-layer communication)
- **L1 runtime** provides service registry, health monitoring, KEI sandbox
- **L2 kairon** provides knowledge engineering pipeline (eidos/kos/minerva/...)
- **L2 gbrain** provides Postgres knowledge database (67 MCP tools)
- **L2 omo** provides governance CLI, debt registry, task management

## Testing Pattern

### Integration Tests

Located at `tests/integration/` in root:

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

> CI 覆盖范围会持续变化，不在此处维护数量快照。
> 以 `.github/workflows/` 与各子项目仓库自身 workflow 为准。

- 根仓库工作流入口: `.github/workflows/`
- 子模块 CI: 各项目仓库内 `.github/workflows/ci.yml` 及同类 workflow
- 治理门禁: `governance-check.yml`, `quality.yml`, `workspace.yml`

### MOF 工具集 (Model-Driven Framework)

> MOF 是 eCOS 的"活 DNA" — 机器可读的系统描述，每次变更都必须更新、每次提交都自动校验。

**Agent 约束强制:**
```bash
# 修改前：查影响/状态/价值
bin/mof-enforce pre-check COMP-WS-agora

# 修改后：校验合规
bin/mof-enforce post-check
```

**推理工具:**
```bash
bin/mof-reason.py impact <node_id>    # 影响分析
bin/mof-reason.py state <node_id>     # 状态推理
bin/mof-reason.py value <node_id>     # 价值推理
```

**分析工具:**
```bash
bin/mof-analyze dashboard             # 系统仪表盘
bin/mof-analyze testing               # 测试覆盖分析
bin/mof-analyze quality               # 代码质量分析
bin/mof-analyze cost                  # 成本分析
```

**文档生成:**
```bash
bin/mof-export readme <project>       # 自动生成 README
bin/mof-export api <project>          # 自动生成 API 文档
bin/mof-export arch                   # 自动生成 Mermaid 架构图
```

**漂移检测:**
```bash
bin/mof-drift                         # 检测架构漂移
bin/mof-scan                          # 安全扫描
bin/mof-graph                         # 依赖图生成
bin/mof-graph cycles                  # 循环依赖检测
```

**团队协作:**
```bash
bin/mof-assign <domain>               # 团队任务分配
bin/mof-evolution <project>           # 系统演化追踪
```

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

- **根仓库 `.gitmodules` 是 SSOT** — 子模块版本锁定在这里
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
| X1-X4 规则 | `.omo/_truth/x1-*.yaml` ~ `x4-*.yaml` | 在 `AGENTS.md`、README、计划文档里复制规则正文 |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 在上层文档里另写一套 gate/constraint |

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
- `_archived/` — Archived project snapshots (e.g. `SharedBrain-original`)
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
- `.github/workflows/` — CI configurations
- `.hermes/` — Hermes-related scripts and adapters

## 🤖 Agentic Protocols & BOS URIs (eCOS v5 Mandatory Rules)

**All AI Agents operating in this workspace MUST follow these architectural constraints:**

1. **NO RAW STATE MUTATION**: 不要绕过 broker 直接改写 `.omo/` 或 `spaces/`。治理状态写入必须走 `projects/omo`、`projects/c2g` 或受审计入口。
2. **USE AGORA MESH**: All cross-layer operations must go through the Agora Service Mesh (`agora`).
3. **BOS URI ABSTRACTION**: State mutations and reads must use `bos://` URIs instead of direct file I/O where applicable.
4. **INTROSPECTION**: If you don't know what tools or resources are available, invoke `read_resource("bos://agora/registry")` to dump the current Mesh state.
5. **MUTATION**: To change governed state, 优先走 `bos://` 资源入口；涉及 `.omo` 落盘时，优先走 `omo CLI` / `projects/omo` / `projects/c2g` broker，而不是 ad-hoc file I/O。
6. **COGNITIVE FRAMEWORKS**: MetaOS dynamically loads cognitive frameworks (like BDSK or Six Hats) from the L0 MOF model (`ecos/src/ecos/ssot/mof/m1/cognitive_framework/`). When executing complex planning, adhere strictly to the injected framework personas.
7. **MANDATORY ATOMIC COMMITS**: All agents MUST immediately run `git commit` after making logical changes, especially to documentation or `.omo` files. The system relies on Git post-commit hooks for knowledge extraction (`mof-extract`). Failing to commit will break the system's memory loop and is a critical failure.
8. **DIRECT-IO BASELINE MUST STAY EMPTY**: `.omo/_truth/registry/direct-io-baseline.yaml` 只能是空基线；任何新增 entry 都视为治理回退，必须先修代码，再过 lint / CI。

### `.omo` 三层治理边界

| 平面 | 位置 | 规则 |
|:----|:-----|:-----|
| state_plane | `.omo/` | 只承载治理状态、证据、知识、交付，不承载长期执行代码 |
| kernel_plane | `projects/omo/` | 唯一治理执行内核，负责 schema、audit、sync、promotion、truth mutation |
| ingress_plane | `projects/c2g/` | 唯一战略入口，只能向 `.omo/tasks/planned/` 和 `goals/current.yaml` 物化 |

唯一标准: `.omo/standards/omo-governance-surfaces.md`  
唯一注册表: `.omo/_truth/registry/omo-governance-surfaces.yaml`

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

## 🛡️ OPC Self-Correction Discipline (2026-06-13 确立)

OPC 路线图 P5-P7 收口阶段建立的 self-correction 闭环, 任何 Phase / Sub-gate / Self-correction 报告必须按此标准产出。

> 说明: 本节是历史收口阶段沉淀下来的治理规范与红线，不是当前运行时状态面。
> 其中出现的阶段编号、轮次、样例报告、收口数据，只作为规范来源和审计证据，不作为实时事实源。

### SSOT 引用链

| 层级 | 路径 | 用途 |
|------|------|------|
| 配置 SSOT | `.omo/_control/evolution/config.yaml` | cron wrapper 路径 / 5repos fallback 链 / OPC_MODE/OPC_GENERATED_AT/OPC_TODAY env 默认值 / fcntl 锁路径 / 5 红线 |
| 模板 | `.omo/standards/opc-review-template.md` | 8 字段 review template (Phase/Subgate/Objective/Files/Commands/Runtime/Doc-writeback/Risks/Verdict) |
| 模板 | `.omo/standards/task-yaml-rules.md` (规则 5/6/7) | plan.yaml gate_status 单一字段 / fallback 禁硬编码 mode / multi-mode 副本单 owner |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml:opc_cadence_constraints` | 7 条治理约束 (CR-CADENCE-01 / CR-INDEX-LOCK-01 / CR-MODE-ENV-01 / CR-TIME-ENV-01 / CR-MODE-COPY-01 / CR-DRIFT-LOOP-01 / CR-AUDIT-5REPOS-01) |
| X4 一致性 | `projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-X4-CONSISTENCY.yaml:rules` | CS-06 gate 字段 / CS-07 路径唯一 / CS-08 cron 触发窗口 |
| L0 子模型 | `projects/ecos/src/ecos/ssot/mof/m1/omo_layer/OMO-SELF-CORRECTION-PATTERN.yaml` | 8 段硬结构 + 5 红线 + 6 遗留争议 M1 节点 |
| l4-kernel 域 | `projects/l4-kernel/src/l4_kernel/registry.py:opc` | 9 个 capability (含 7 新增 self-correction) |
| Closeout 报告 | `.omo/_knowledge/audits/2026-06-13-opc-p5-p7-self-correction-closeout.md` | 8 阶段演练 4 反模式全闭环范本 |

### 5 红线 (任一违反 → request changes)

1. `gate_status` 一律维持 `not_yet_passed`, 不得改为 `passed`
2. `planned/` 任务不得推 `active/`, 必须经人工审批
3. manual 演练仅限 1 次 (单测 / wrapper 探针 / 冒烟), evidence 必须真 cron
4. 子仓指针不自动 bump, 根仓只 commit 元数据 (plan/doc/evidence)
5. 无 §17 证据 / 无 5repos.json / 无 audit 报告 → 不得宣称 `passed`

### Closeout 报告 8 段 (缺一即 request changes)

1. 诚实话语前置 (Reader-Disambiguation)
2. 精确命令段 (含实测输出, 不写"已验证")
3. 工作区状态分区域表 (根仓 .omo/ docs/ yaml + 子仓指针 + mof-extract hook 产物)
4. 次优解承认段 (第三方强建议未执行时显式承认)
5. 反模式修复轨迹表 (4 反模式 → 修复 commit → 修复方式)
6. Self-Correction Trajectory (commit 序号 + 内容 + 类别)
7. 显式遗留争议 (Next-Action, 6 处标 P0-P3 红黄绿)
8. Redline Audit (5/5 守住状态)

### 关键 memory 引用

- `feedback_opc_closeout_reviewer_acceptable_20260613.md` — 8 段硬结构必含
- `feedback_no_standard_weakening_20260612.md` — 禁止降标过关
- `feedback_real_cron_window_stop_manual_practice_20260612.md` — 停止 manual 刷 evidence
- `feedback_opc_cron_wrapper_trigger_injection_20260612.md` — INVOCATION_ID+OPC_TRIGGER 显式
- `feedback_p6_self_evolution_planned_only.md` — self-evolution 永不入 active/
- `feedback_submodule_state_decoupling_20260612.md` — 子仓指针不自动 bump
- `feedback_8field_review_template_20260612.md` — review template 8 字段
- `feedback_release_notes_three_piece_20260612.md` — release notes 三件套 (summary/validation/debt)

## 🧬 Model-Driven Bridge (2026-06-14 确立)

> `projects/model-driven` 是 eCOS v5 的**横切面框架 (Cross-Cutting Framework)**, 被 L0/L2/L3/L4 四层消费, 零内部依赖。
> 通过 M3→M2→M1 链路把"模型驱动"理念物化到 SSOT, 任何新增阶段/门禁都必须双向追溯。

### 桥接 SSOT 链

| 层级 | 路径 | 用途 |
|------|------|------|
| M3 标准定义 | `projects/model-driven/src/model_driven/mof/m3_extended.py:STANDARD_STAGES` | 7 阶段 + 4 门禁 + 3 PipelinePhase 单一来源 |
| M3 流水线 | `projects/model-driven/src/model_driven/lifecycle/pipeline.py:PipelinePhase` | 3 阶段宏观流水线 (COLD_START/EVOLUTION/HARDENING) |
| M2 schema | `projects/ecos/src/ecos/ssot/mof/m2/omo_task.yaml` 等 45 个 YAML | 建模契约: required/optional/stateMachine/validationRules |
| M1 实例节点 | `projects/ecos/src/ecos/ssot/mof/m1/**` 946 个 YAML | 真实实例, 每个含 `m3_parent` + `model_driven_refs` 双向引用 |
| 校验 | `projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py` | 4 flags (--strict/--check-types/--check-transitions/--check-refs) |
| 推理 | `projects/ecos/src/ecos/ssot/tools/mof-derive.py` v2 | 7 阶段 + 4 门禁 + 3 Phase 跨仓推理 (真实导入 model-driven 11 字段) |
| 同步 | `projects/ecos/src/ecos/ssot/tools/mof-bridge-sync.py` B.3 | model-driven ↔ M1 lifecycle 增量 diff/sync (按 stage key + transition 匹配) |

### 桥接铁律

1. **M3 是 SSOT** — `model-driven/m3_extended.py:STANDARD_STAGES/...` 不得在别处复制定义
2. **M1 必含双向引用** — 每个 M1 节点必须有 `m3_parent` (指向 M3 类型) + `model_driven_refs` (反向追溯 model-driven 源文件/类)
3. **M2 schema 必含 validationRules** — 不只是声明字段, 必须有 `gate_status=passed implies evidence>=1` 等硬约束
4. **任何新增阶段/门禁** 必须同时落: model-driven 源 + M2 schema + M1 节点 + schema-validate 校验 + mof-derive 验证 + mof-bridge-sync 同步
5. **pre-commit hook 强制** — 任何 M1 YAML 改动触发 `mof-schema-validate.py --staged --strict`, 失败即拒绝提交
6. **跨仓 import 真实字段数 ≥ 期望** — 任何 `from model_driven.X import Y` 必须实测 `Y` 字段数 ≥ 真实期望, 避免 fallback 替跑 (mof-derive v1 隐藏 bug 范式)
7. **M2 schema 必有 ≥1 M1 实例** — M2 type 不应孤儿, 孤儿治理必须显式决策 (补 M1 / 裁 M2 / 标 deprecated)
8. **L0 治理规则登记** — 任何新校验工具/规则必须同步登记到 `L0-constraints.yaml` 4-字段硬约束 (id/name/description/rule/type/severity/enforcement)
9. **OMOTask 双向配对 m1_only=0** — 任何 M1 OMOTASK-*.yaml 改动必跑 mof-state-bridge --strict, 失同步即拒
10. **alias 模糊匹配 (status/title)** — M1 name 与 .omo title, status done/completed 视为一致, 不虚报漂移
11. **pre-commit venv python 优先** — 用 `.venv/bin/python3` 而非 `uv run --with pyyaml`, 启动 0.55s 远低于 5s
12. **priority/domain default 兼容** — M1 OMOTask 字段 None 视同 P2/opc default, 不虚报漂移
13. **cron wrapper 集成 mof-state-bridge** — 任何 OPC cron 跑完后必跑 mof-state-bridge --strict, 5repos 实时写
14. **OMOTask 字段完整性 1 步到位** — omo-fields-completeness-check 校验硬约束 (state machine/required) + RoadmapPhase 推荐
15. **OMOTask status 硬约束** — status 必在 M2 stateMachine {proposed/in_progress/review/done/blocked/archived}, 大写 DONE/pending 等不在
16. **m3_parent 必填** — M1 OMOTask 必含 m3_parent 反向追溯 (桥接铁律 2), 缺失即 warning
17. **signals 业务信号补全** — Task 节点 signals 必填默认 (task-{id}-running), RoadmapPhase 业务信号不虚报

### 当前桥接状态 (2026-06-15 收口)

> 说明: 以下是 model-driven bridge 收口时的历史证据快照。
> 当前真实状态若需确认，以对应工具实跑、M1/M2/M3 实际文件和最新 audit 为准。

- 1031 M1 节点 / 45 M2 schema / 100% type coverage / 0 orphan
- 83/83 OMOTask 配对成功 (m1_only=0, 字段漂移 0)
- 6 工具综合 (validate/derive/bridge-sync/state-bridge/fields-completeness + auto-backfill-v2)
- 5 工具 strict 模式 全部退出码 0
- 字段完整性: 0 error / 230 warning / 17 info (Task signals 100% 补全, RoadmapPhase 17 留空)
- 7/7 阶段实例化 (was 1/7) / 4/4 门禁实例化 (was 1/4) / 5/5 MODEL-* 节点反向追溯
- 25/25 gap 全部闭环 (P0(3)+P1(3)+P2(3)+P3(3)+P4(4)+P5(3)+P6(3)+P7(3))
- 3 OMOTASK-OPC-P5/P6/P7 节点全部 status=done + evidence>=1
- 0 drift / 0 missing / 0 sm_invalid / 0 lint
- 收口报告: `.omo/_knowledge/audits/2026-06-14-model-driven-bridge-closeout.md`

### 关键 memory 引用

- `project_model_driven_layer_positioning_20260609.md` — model-driven 是横切面框架, 非 L4
- `project_model_driven_debt_fix_p0_p1_20260609.md` — 34 源文件, 0 lint, 29/29 验证通过
- `feedback_mof_schema_governance_rule_registration_20260613.md` — 校验纳入 L0 治理规则 3 步法

## 🌀 P43 Closed-Loop Pattern (2026-06-21 确立)

> P43 是 eCOS 历史上首次完整跑通 c2g → omo → mof 三层联动闭环的阶段。
> 该模式可作为后续 P44+ 的可复用范式。

### 闭环路径

```
c2g brainstorm (V2P)                      # 需求侧建模
   ↓ Pitch (Upstream + Appetite)
omo governance ingress-task (broker)      # 任务物化
   ↓ TASK-*.yaml (planned → pending)
omo governance ingress-debt (broker)      # 债务闭环 (修复型)
   ↓ DEBT-*.yaml (upsert + audit + history)
bin/mof-version record '<desc>'           # MOF 版本登记
   ↓ v0.0.X → v0.0.X+1
omo governance 重跑 + mof-enforce post-check  # 验证
   ↓ score 85 → 100 A+ + 0 drift
git commit + submodule pointer bump       # 落地
```

### P43 关键产物 (5 Rounds · 12 commits)

| Round | 主题 | 提交 | 治理影响 |
|-------|------|------|---------|
| R1 | 5 debt evidence closure | 1 | governance 85 → 88 |
| R2 | kairon 18 F821 + v0.0.7/8 | 4 | governance 88 → 100 |
| R3 | c2g +41 tests + SUBSYSTEM_MAP | 2 | c2g ratio 0.02 → 0.07 |
| R4 | 4 子项目 lint cleanup | 4 | 全 9 子项目 lint=0 |
| R5 | 3 子项目 + 跨闭环 | 5 | governance 100 A+ + v0.0.12 |

### 模式可复用度

| 环节 | 可复用度 | 复用条件 |
|------|---------|---------|
| `c2g brainstorm` | **高** | 任意需求点, 补 Upstream/Appetite |
| `omo ingress-task` | **高** | broker + fcntl lock 自动 |
| `omo ingress-debt` | **高** | 任何 debt 项修复/关闭/延期 |
| `mof-version record` | **高** | 每次 P 阶段完成必跑 |
| `omo governance` 验证 | **高** | 6 项检查 + score 闭环 |
| `mof-enforce post-check` | **高** | 0 drift 必保 |

详细模式文档: `.omo/_knowledge/patterns/p43-closed-loop-pattern.md`

## Panoramic View

- **Full feature map / architecture / core flows / module deps / user journeys / integration surfaces**: See [`docs/PANORAMA.md`](./docs/PANORAMA.md) for the current panorama skeleton and authoritative links.
