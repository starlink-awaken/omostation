# AGENTS.md — projects/ Workspace Root

> Multi-project knowledge engineering & research workspace (eCOS v5).  
> 本文档面向 AI Coding Agent — 假设读者对本工作区一无所知。

---

## 1. Project Overview

`projects/` 是 eCOS v5 工作区的**项目容器目录**，采用 **5+3+1 分层架构**。  
目录本身不携带根级构建文件（无顶层 `pyproject.toml` / `package.json` / `Makefile`），所有源码与构建配置都下沉在各自子项目中。

当前包含 **16 个活跃项目** + `scripts/` + `_archived/` 归档区：

| 层级 | 项目 | 技术栈 | 核心职责 | 状态 |
|------|------|--------|----------|------|
| L3 | `cockpit` | Python (uv, pytest) | 统一入口 (CLI 18 + MCP 20 tools + Web) | 🟢 Active |
| I0 | `agora` | Python (uv, pytest) | MCP Hub · 服务发现/路由/代理/治理 | 🟢 Active |
| L2 | `kairon` | Python (uv, pytest) | 知识引擎 · 19 活跃包 (+ 6 archived) monorepo | 🟢 Active |
| L2 | `gbrain` | TypeScript (bun) | Postgres 知识数据库 · 67 MCP tools | 🟢 Active |
| L2 | `omo` | Python (uv, pytest) | 治理面 · Agent OS 内核 | 🟢 Active |
| L2 | `metaos` | Python (uv, pytest) | 编排引擎 · 决策门控/免疫/路由 | 🟢 Active |
| L1 | `runtime` | Python (uv/pytest) | 运行时 · 服务矩阵/调度/KEI 沙箱 | 🟢 Active |
| L0 | `ecos` | Python (uv, pytest) | SSB 协议层 · 签名链/涌现计算 | 🟢 Active |
| — | `aetherforge` | Python (uv, pytest) | 算力网格 + LLM 网关 + 群体智能 | 🟢 Active |
| — | `compute-mesh` | Python (uv, pytest) | 算力发现/聚合/调度/Worker 管理 | 🟢 Active |
| — | `swarm-engine` | Python (uv, pytest) | 多智能体任务编排 (拍卖/DAG/生命周期) | 🟢 Active |
| — | `omo-debt` | Python (uv, pytest) | 技术债务评分 CLI (Pattern 09 v2.1) | 🟢 Active |
| — | `family-hub` | TypeScript (bun, Vite, React) | 家庭中心 Web 应用 | 🟢 Active |
| — | `hermes-console` | TypeScript (bun, Vite, React) | 控制台 UI (待集成至 cockpit) | 🟡 待集成 |

**特殊目录：**

- `_archived/` — 归档项目（agentmesh、SharedBrain-original 等），**不应修改**。
- `scripts/` — 独立 git 仓库的治理自动化脚本。当前仅含 `omo` 一个入口脚本。
- `.omo` → `../.omo`（symlink）— 工作区治理状态，**禁止直接编辑**，必须通过 `omo` CLI 或合约流程修改。
- `spaces` → `../spaces`（symlink）— 用户空间/租户空间清单与准入边界。

---

## 2. Architecture

### 2.1 5+3+1 分层与 BOS URI 命名空间

```
L4 自我层 ── ~/Documents/驾驶舱/CARDS/ (SQLite) + ~/Documents/学习进化/ (MD)
L3 入口层 ── cockpit (CLI + MCP + Web)
I0 织层   ── agora (动态反向代理 Mesh) ── 拦截并路由 bos:// 流量
L2 引擎面 ── kairon / gbrain / omo / metaos / aetherforge ── 后台 Daemon 提供 MCP 资源
L1 运行时 ── runtime ── 受控沙箱，随 protocols 规则产生 Ephemeral Agents
L0 协议   ── ecos ── SSB 协议层，承载系统决策的 Immutable Log 上链与涌现计算
```

> **L0 协议候选 (bus-foundation)**：bus-foundation 在 R57-R76 期间评估过 L0 协议层提升
> （ADR-0003），结论为 **Path C: Defer Indefinitely**。原因：L0 是 one-way ratchet，
> bus-foundation 8 backend + 56 tests + 7 internal eCOS consumers 证明 "the bus
> works"，但不证明 "the bus deserves L0 status"（需 external adoption 信号，
> 8 月审计 0/0/0）。详见 `projects/bus-foundation/docs/ADR-0003-no-l0-promotion.md`。
> 现状：bus-foundation 保持 standalone repo 状态（`projects/bus-foundation/`），
> 普通 feature work 节奏，未来 external adoption 出现可 supersede ADR-0003。

**五大 BOS URI 域**（所有跨层通信必须经 Agora Mesh 路由）：

| 域 | 命名空间 | 承载项目 |
|----|---------|---------|
| 记忆与事实源 | `bos://memory` | kos、kronos、gbrain、sot-bridge |
| 治理与律法 | `bos://omo` | metaos、eidos、protocols-layer、omo |
| 认知与推演 | `bos://analysis` | ontoderive、minerva、codeanalyze |
| 人格与心智 | `bos://persona` | sot-bridge (SharedBrain 桥接) |
| 能力与生态 | `bos://forge` | forge、runtime (KEI 沙箱执行) |

### 2.2 依赖流向原则

- **单向依赖**：上层可调用下层，下层不可反向依赖上层。
- **Mesh 强制**：所有跨层操作必须经过 `agora`（I0）进行服务发现与路由。
- **独立仓库**：每个子项目拥有独立的 git 仓库和 CI 配置。

---

## 3. Technology Stack

### 3.1 Python 项目（绝大多数）

| 工具 | 版本/说明 | 项目 |
|------|----------|------|
| Python | 3.13+（kairon/agora/metaos/omo 强制）；3.10+（runtime/ecos/omo-debt 兼容） | 全部 |
| 包管理器 | **uv**（强制，非 pip/poetry） | 全部 |
| 构建后端 | hatchling（主流）/ setuptools（runtime）/ uv_build（omo） | 视项目而定 |
| 格式化/Lint | **ruff**（target-version = py313, line-length = 120） | kairon, agora, metaos, aetherforge, ecos, omo |
| 测试框架 | pytest + pytest-asyncio | 全部 |
| MCP Server | fastmcp | agora, runtime, metaos, ecos, omo, aetherforge |
| Web 框架 | FastAPI + uvicorn | agora, runtime |
| 日志 | structlog | agora, metaos, compute-mesh |

### 3.2 TypeScript 项目

| 工具 | 版本/说明 | 项目 |
|------|----------|------|
| 运行时 | **Bun**（>=1.3.10），非 Node/npm | gbrain |
| 构建 | Vite + TypeScript ~5.6 / ~6.0 | family-hub, hermes-console, gbrain(admin) |
| 框架 | React 19 | family-hub, hermes-console |
| 测试 | bun test（内置）+ 自定义 shard 脚本 | gbrain |
| 类型检查 | tsc --noEmit | gbrain |

---

## 4. Build & Test Commands

> **通用规则**：没有根级统一构建命令。进入各子目录后使用对应工具链。

### 4.1 Python 项目通用流程

```bash
cd projects/<project>
uv sync                # 安装依赖（含 editable 本地包交叉引用）
uv run pytest tests/ -q  # 运行测试
uv run ruff check .    # lint（如项目配置了 ruff）
uv run ruff format .   # 格式化
```

### 4.2 按项目速查

| 项目 | 安装 | 全量测试 | 快速测试 | Lint |
|------|------|----------|----------|------|
| **kairon** | `uv sync` | `make test` | `make test-fast` / `make test-diff` | `make lint` |
| **agora** | `uv sync` | `uv run pytest tests/ -q` | `uv run pytest tests/ --ignore=tests/e2e -q` | `uv run ruff check src/` |
| **cockpit** | `uv sync` | `uv run pytest tests/ -q` | — | `uv run ruff check src/` |
| **runtime** | `uv pip install -e .` | `make test` | — | `make lint` |
| **ecos** | `uv sync` | `uv run pytest tests/ -q` | — | `uv run ruff check src/` |
| **metaos** | `uv sync` | `uv run pytest tests/ -q` | — | `uv run ruff check src/` |
| **omo** | `uv sync` | `uv run pytest tests/ -q` | `uv run pytest -m fast -q` | — |
| **aetherforge** | `uv sync` | `uv run pytest` | — | `uv run ruff check packages/ src/` |
| **omo-debt** | `uv sync` | `uv run pytest tests/unit/ -v` | — | `uv run ruff check .` |
| **compute-mesh** | `uv sync` | `uv run pytest tests/ -q` | — | — |
| **swarm-engine** | `uv sync` | `uv run pytest tests/ -q` | — | — |

### 4.3 TypeScript 项目

```bash
# gbrain
cd projects/gbrain
bun install
bun test                     # 并行单元测试
bun run verify               # 预提交门禁（privacy/checks/typecheck）
bun run ci:local             # 完整 Docker-backed CI
bun run ci:local:diff        # diff 感知的子集 CI

# family-hub / hermes-console
cd projects/<project>
bun install
bun run dev                  # Vite 开发服务器
bun run build                # tsc + vite build
bun run lint                 # eslint
```

---

## 5. Code Organization

### 5.1 Python 项目目录惯例

```
<project>/
├── src/<package_name>/        # 源码（PEP 420 namespace， hatchling 构建）
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口
│   ├── mcp_server.py          # MCP stdio server（如有）
│   └── ...
├── tests/                     # pytest 测试
├── pyproject.toml             # 项目配置 + uv 依赖 + ruff 配置
├── uv.lock                    # 锁定文件（必须提交）
├── README.md
└── INTERFACE.yaml             # 部分项目携带接口注册表（CLI/MCP/HTTP 端口声明）
```

**kairon monorepo 特例：**

```
kairon/
├── packages/                  # 19 活跃包（uv workspace members）
│   ├── eidos/                 # 知识建模
│   ├── kos/                   # 搜索索引
│   ├── minerva/               # 推理引擎
│   ├── ontoderive/            # 本体推导
│   ├── kronos/                # 摄取管线
│   ├── forge/                 # 工具集市
│   ├── codeanalyze/           # AST 理解
│   ├── core-models/           # 核心数据模型
│   ├── shared-lib/            # 共享库
│   └── ...
├── src/kairon/                # 顶层聚合包（轻量）
├── Makefile                   # 跨包 test / lint / test-diff
└── pyproject.toml             # workspace 配置 + 成员列表
```

**aetherforge monorepo 特例：**

```
aetherforge/
├── packages/
│   ├── gateway/               # LLM Provider 抽象与调度
│   ├── mesh/                  # 算力基础设施
│   └── swarm/                 # 群体智能编排
├── src/aetherforge/           # 聚合 CLI
└── docker-compose.yml         # 容器编排
```

### 5.2 TypeScript 项目目录惯例

```
gbrain/
├── src/
│   ├── core/                  # 引擎接口 (engine.ts)、操作 (operations.ts)、搜索、摄取
│   ├── cli.ts                 # CLI 入口
│   ├── mcp/server.ts          # MCP server
│   └── ...
├── tests/                     # *.test.ts
├── scripts/                   # 大量 bash 校验脚本（privacy/isolation/wasm/...）
├── skills/                    # Agent skill 路由与实现
├── package.json
└── bun.lock
```

---

## 6. Testing Strategy

### 6.1 测试健康度（最新基线）

| 项目 | 总测试 | 通过 | 通过率 | 备注 |
|------|--------|------|--------|------|
| agora | 1200 | 1165 | 97.1% | 含 e2e（需网络，CI 忽略） |
| cockpit | 514 | 498 | 96.9% | |
| kairon | ~4199 | ~4157 | 99.8% | 19 包聚合 |
| runtime | 176 | 171 | 97.2% | |
| omo | 530 | 302 | 57%* | 225 skipped（需完整环境），有效 97.4% |
| metaos | 188 | 188 | 100% | |
| ecos | 122 | 112 | 91.8% | |
| gbrain | ~9737 | ~9700 | ~99.6% | 含 E2E（Docker-backed） |
| omo-debt | ~25 | 25 | 100% | 单元测试 |

### 6.2 测试标记与分级

- **kairon**: `make test-fast` 跳过 `tests/integration` 与 `tests/benchmarks`；`make test-diff` 仅测 git diff 中修改过的包。
- **agora**: `@pytest.mark.network` 标记需要访问 GitHub 的测试；运行加 `--ignore=tests/e2e`。
- **omo**: 注册 BOS URI markers — `pytest -m fast`（<10ms）、`-m bos_5domain`（~3s）、`-m bos_40`（全套）。
- **gbrain**: 并行 shard 测试（4 shards），serial 测试单线程运行；`bun run test:heavy` / `test:slow` / `test:e2e` 分级。

### 6.3 覆盖率

- **kairon**: `fail_under = 70`（pyproject.toml `[tool.coverage.report]`）。

---

## 7. Code Style Guidelines

### 7.1 Python（统一 ruff 配置）

- **Formatter**: ruff
- **Linter**: ruff
- **Line length**: 120
- **Target**: Python 3.13+
- **Quote**: double
- **Select**: `E, F, W, I, N, UP, S, PLE, RUF100`
- **常见 Ignore**: `S101, S603, S607, S108, S110, S314, S608, E402, E501, SIM115, N813, UP047`

> 运行方式：`uv run ruff check .` / `uv run ruff format .`  
> kairon 使用 `make lint` / `make format` 跨所有包执行。

### 7.2 TypeScript（gbrain）

- **Formatter/Fix**: bun fmt / bun run lint:fix（项目内部脚本）
- **类型检查**: `bun run typecheck`（`tsc --noEmit`）
- **测试命名**: 禁止真实人名/公司名出现在测试中（privacy 校验脚本强制）。

---

## 8. Development Conventions & Gotchas

1. **uv 强制**：所有 Python 项目使用 `uv sync` / `uv add <pkg>`。禁止 pip/poetry。
2. **Python 3.13+**：kairon/agora/metaos/aetherforge 目标版本为 3.13+，ruff 配置也指向 `py313`。
3. **gbrain 需要 bun**：不使用 npm。`bun install` / `bun test` / `bun run ci:local`。
4. **数据库路径被 gitignore**：`data/db/` 及各项目本地 DB 文件在 `.gitignore` 中，不提交。
5. **跨项目依赖通过 editable path**：如 kairon 的 `pyproject.toml` `[tool.uv.sources]` 声明 `kos = { path = "packages/kos", editable = true }`；agora 声明 `ecos = { path = "../ecos" }` 等。
6. **无根级测试命令**：测试按项目运行（通过各项目 Makefile 或 `uv run pytest`）。
7. **!!! 关键修改必须立即 git commit !!!**：kairon 历史中存在 `git reset` 操作会静默回滚未提交修改。AI Agent 每次修改文件后必须立即 commit。参见 FLOW-OMC-REVERT。
8. **Pre-commit 覆盖范围**：`~/.hermes/scripts/git-hooks/pre-commit` 现在覆盖 kairon/agora/cockpit/ecos/omo/metaos/runtime，仅检查本次提交的 Python 文件。
9. **BOS URI 抽象**：状态变更与读取优先使用 `bos://` URI，避免直接文件 I/O。不确定可用资源时，调用 `read_resource("bos://agora/registry")` 内省。
10. **OMO 合约流程**：禁止手动编辑 `.omo/` 或 `spaces/` 下的治理文件；修改必须通过 `omo` CLI 或合约化派发流程。
11. **差量测试优先**：在 kairon 修改单个包时，使用 `make test-diff` 取代全量 `make test-fast`。

---

## 9. CI / CD

GitHub Actions 分布在各项目自己的 `.github/workflows/` 中，**无根级统一 CI**。

| 项目 | Workflow 文件 | 说明 |
|------|--------------|------|
| **kairon** | `ci.yml` | lint + codeanalyze 矩阵(3.10-3.13) + test-all |
| **agora** | 独立 CI（项目内） | pytest + ruff |
| **gbrain** | `test.yml` | 4-shard 并行 + gitleaks + `bun run verify` |
| **gbrain** | `e2e.yml`, `heavy-tests.yml` | Docker-backed E2E / 重测试 |
| **omo** | `ci.yml` | 治理检查 + OMO autopilot + constraint validation |

> 工作区根目录的 `.github/workflows/` 不存在；所有 CI 下沉到子项目仓库。

---

## 10. Security Considerations

- **密钥读取**：所有 API 密钥、Token 必须通过 `os.environ.get()` 读取，**禁止硬编码**。
- **Agora SSRF 防护**：`ssrf_guard.py` 对下游服务端点 URL 做严格校验。
- **gbrain Privacy Gate**：禁止在公开产物（测试、文档、日志）中提交真实人名/公司/基金名称；使用 generic placeholders（`alice-example`, `acme-example`）。`bun run verify` 中的 `check:privacy` / `check:proposal-pii` 会阻断提交。
- **Trust Boundary（gbrain）**：`OperationContext.remote` 区分可信本地 CLI 调用者与不可信 MCP Agent 调用者；远程调用时文件系统限制收紧。
- **无 eval / pickle**：Python 侧安全序列化，禁止反序列化不可信数据。
- **SSB 签名链（ecos）**：L0 层通过签名链保证事件不可篡改，用于系统决策的 Immutable Log。

---

## 11. How to Start Working

### 11.1 如果你是 Python Agent

```bash
# 1. 确认 uv 已安装
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 进入目标项目
cd projects/<project>
uv sync

# 3. 运行测试确认环境
uv run pytest tests/ -q

# 4. 修改代码 → 立即 git commit
# 5. 差量测试（kairon 用 make test-diff，其他用 uv run pytest）
```

### 11.2 如果你是 TypeScript Agent（gbrain / family-hub / hermes-console）

```bash
# 确认 bun 已安装
curl -fsSL https://bun.sh/install | bash

cd projects/gbrain
bun install
bun test
```

### 11.3 阅读顺序（按目标项目）

| 目标 | 必读文件 |
|------|---------|
| kairon | `projects/kairon/CLAUDE.md` + `AGENTS.md` |
| agora | `projects/agora/README.md` + `AGENTS.md` |
| gbrain | `projects/gbrain/CLAUDE.md` + `AGENTS.md` |
| omo | `projects/omo/CLAUDE.md` + `AGENTS.md` |
| cockpit | `projects/cockpit/README.md` |
| runtime | `projects/runtime/Makefile` |
| ecos | `projects/ecos/README.md` + `AGENTS.md` |
| metaos | `projects/metaos/README.md` |
| aetherforge | `projects/aetherforge/ARCHITECTURE.md` + `API.md` |

---

## 12. Key Files Index

| 路径 | 说明 |
|------|------|
| `projects/kairon/pyproject.toml` | kairon monorepo workspace 配置 |
| `projects/agora/pyproject.toml` | Agora MCP Hub 配置 |
| `projects/aetherforge/pyproject.toml` | AetherForge monorepo workspace |
| `projects/runtime/Makefile` | runtime 构建/测试/状态同步命令 |
| `projects/spaces/registry.yaml` | 工作区级空间注册表 |
| `projects/scripts/omo` | OMO CLI 入口脚本 |
| `projects/<project>/INTERFACE.yaml` | 部分项目携带的接口注册表（CLI/MCP/HTTP） |

---

*Last updated: 2026-06-07*  
*Architecture phase: eCOS v5 (5+3+1) · Phase 33*
