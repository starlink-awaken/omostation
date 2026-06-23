# CLAUDE.md — omostation Workspace

> Personal AI Operating System · Multi-project Knowledge Engineering Workspace
> 基于 omostation (starlink-awaken/omostation) 根仓库
> **version: v2.1** | 最后更新: 2026-06-19 · CI 治本机制 + M0/L0 模型驱动一致 + 硬编码清 + debt 全关

---

## §0 启动强制指令 (MANDATORY · 不可跳过 · 每次对话第一步)

**Agent 首次响应前必须执行以下任一步骤，获取当前上下文：**

1. **通过 MCP**: 连接 `cockpit` MCP server，调用 `workspace_context` 工具
   - 返回: 当前 Phase、活跃 P0 卡片、治理约束、下一步引导
2. **备选 (无 MCP 时)**: 读取 `.omo/_truth/goals/current.yaml` 获取当前阶段和目标
3. **治理宪章**: 所有 5+3+1 架构规范见 `.omo/_knowledge/management/governance-charter-v1.md`
4. **X 轴保障**: X1(审计)/X2(保鲜)/X3(价值)/X4(一致性) 原则见 `LAYER-INDEX.md`，实现见 `.omo/_knowledge/management/x-axis-implementation-registry.md`

**涉及端口时必须**: 先查 `protocols/port-registry.yaml` → 确认端口未被占用 → 注册新端口 → 使用环境变量 `{SERVICE}_PORT`。CI 和 Agora runtime 双重阻断端口冲突。
**强制闭环原则 (Mandatory Commits)**: Agent 修改任何文件后（尤其是 `.omo` 或文档），**必须立即执行 `git commit`**。Git post-commit 钩子承载着 L0 层知识萃取引擎的触发机制。不 commit 意味着你产生的知识将从系统的全局记忆中彻底丢失，这被视为严重故障。

**禁止**: 未获取上下文直接修改代码。禁止跳过 L4 约束检查直接操作 `.omo` 目录。

---

## 今日工作记录 (2026-06-12)

### 完成的工作

| 类别 | 工作项 | 数量 |
|------|--------|------|
| 债务治理 | 清理所有债务 | 9 项 |
| X1-X4 框架 | 治理体系化 | 8 个文件 |
| L0 治理模块 | 原语+检查器+引擎 | 8 个文件 |
| 能力地图 | 17 个项目 | 17 个文件 |
| 文档完善 | CHANGELOG/CONTRIBUTING/LICENSE | 51 个文件 |
| Git Hooks | 17 个项目配置 | 17 个 |
| 测试优化 | 新增测试 | 3 个 |
| KOS 修复 | 领域配置 | 10 域 |

### 当前状态

| 指标 | 值 |
|------|-----|
| debt_weight | 1.0 |
| debt_health | 100.0 |
| 测试文件 | 2,053 |
| 估算测试用例 | ~16,424 |
| 能力地图 | 17/17 (100%) |
| Git Hooks | 17/17 (100%) |

---

## 项目身份

这是 **omostation** 根仓库 —— 一个多项目融合工作区，整合了知识工程、数字生命 OS、Agent SDK 与知识脑四大子系统。**当前 Phase/健康分/任务状态以 `.omo/state/system.yaml` 为 SSOT**（勿在此硬编码易变数字，会漂移；会话启动第[5]步已读）。

---

## 架构总览 (5+4+1+1)

> ⚠️ 统一采用 5+4+1+1 表述，与 Documents 层架构一致。旧 4-layer (I0→L4) 视图已废弃。

```
L4  自我层     文档域 (纯文档)
L3  入口层     cockpit (CLI + MCP + Web)
L2  引擎面     omo(治理) + kairon(引擎) + gbrain(记忆) + metaos(编排)
L1  运行时     runtime + 健康监控 + KEI + 矩阵调度
L0  协议层     ecos — SSB + MOF + BOS URI（984 M1 节点）

I0  织层       agora — MCP Hub（43 MCP 工具 · 1200+ 测试）

X1-X4          审计 · 抗熵 · 价值栈 · 一致性

M0             model-driven — 7阶段引擎 · 12工具链 · 190测试
               （跨层消费，零内部依赖）
```

### 4-Plane 治理架构 (.omo/)

| 平面 | 路径 | 内容 |
|------|------|------|
| **控制面** | `.omo/_control/` | 目标、状态、蓝图 |
| **事实面** | `.omo/_truth/` | 任务、标准、注册表 |
| **知识面** | `.omo/_knowledge/` | 设计文档、复盘、审计 |
| **交付面** | `.omo/_delivery/` | 运行记录、测试、证据 |

### 数据流

```
Worker/User → SharedBrain (轻量数据持久层)
              ↓
           kairon/ (知识处理、推理、研究、治理)
              ↓
           gbrain/ (知识持久化)
```

---

## 子项目清单 (17 项目 · 5+4+1+1 架构, 全量见 `projects/`)

| 项目 | 层 | 位置 | 栈 | 测试 | 状态 |
|------|:---:|------|:---:|:----:|:----:|
| **cockpit** | L3 | `projects/cockpit/` | Python (uv, pytest) | 486 | 🟢 |
| **agora** | I0 | `projects/agora/` | Python (uv, pytest) | 1371 | 🟢 |
| **kairon** | L2 | `projects/kairon/` | Python 31 包 monorepo | ~4000 | 🟢 |
| **gbrain** | L2 | `projects/gbrain/` | TypeScript (bun) | ~9700 | 🟢 |
| **omo** | L2 | `projects/omo/` | Python (uv, pytest) | 100+ | 🟢 |
| **metaos** | L2 | `projects/metaos/` | Python (uv, pytest) | 189 | 🟢 |
| **runtime** | L1 | `projects/runtime/` | Python (uv, pytest) | 171 | 🟢 |
| **ecos** | L0 | `projects/ecos/` | Python (uv, pytest) | 195 | 🟢 |
| **protocols** | L0 | `protocols/` | YAML | — | 🟢 |
| **model-driven** | M0 | `projects/model-driven/` | Python | 190 | 🟢 |

---

## 会话启动流程

每次新会话按以下顺序执行：

```
[1] 读 Cowork MEMORY                         → 上次会话遗留
[2] 读 AGENTS.md                              → 项目边界
[3] 读 .omo/AGENT.md                          → 治理规范
[4] 读 .omo/INDEX.md                          → 治理知识库导航
[5] 读 .omo/state/system.yaml                 → 当前 Phase·健康分·活跃任务
[6] 读 .omo/goals/current.yaml                → 当前目标和 KPI
[7] 检查 .omo/tasks/active/                   → 可认领的活跃任务
```

---

## 核心命令速查

### 根仓库

```bash
make kairon-test         # 运行 kairon 全部测试
make kairon-lint         # ruff 检查所有包
make kairon-build        # uv sync 安装依赖
make governance-check    # 全量治理检查
```

### MOF 工具 (Agent 必须遵守)

```bash
# 修改前：查影响/状态/价值
bin/mof-enforce pre-check <node_id>

# 修改后：校验合规
bin/mof-enforce post-check

# 推理
bin/mof-reason.py impact <node_id>    # 影响分析
bin/mof-reason.py state <node_id>     # 状态推理
bin/mof-reason.py value <node_id>     # 价值推理

# 分析
bin/mof-analyze dashboard             # 系统仪表盘
bin/mof-analyze testing               # 测试覆盖

# 文档
bin/mof-export readme <project>       # 自动生成 README
bin/mof-export arch                   # 自动生成架构图
```

### kairon (Python monorepo)

```bash
cd projects/kairon && make test           # 全量测试
cd projects/kairon && make test-fast      # 仅单元测试
cd projects/kairon && make lint           # ruff 检查
cd projects/kairon && uv sync             # 安装依赖
cd projects/kairon && uv add <pkg>        # 添加依赖
```

### gbrain (TypeScript)

```bash
cd projects/gbrain && bun test
cd projects/gbrain && bun run ci:local
```

### 集成测试

```bash
bash tests/integration/run-all.sh
```

---

## 编码规范

### Python (kairon)

- **包管理器**: uv (非 pip/poetry)
- **格式化/检查**: ruff (`ruff format`, `ruff check`)
- **行宽**: 120
- **Python 版本**: 3.13+
- **Import 排序**: isort (通过 ruff 启用)

### TypeScript (gbrain)

- **运行时**: bun (非 Node/npm)
- **格式化**: `bun fmt` / `bun run lint:fix`
- **测试**: `bun test` / `bun run ci:local`

---

## SSOT 铁律

> **同一事实不在多处写。知识面文档引用事实面数据时，必须使用相对路径指针，不得复制内容。**

| 数据 | 唯一读源 | 禁止行为 |
|------|---------|---------|
| 任务 | `.omo/tasks/active/` (YAML) | 从知识面文档读取任务状态 |
| 系统状态 | `.omo/state/system.yaml` | 从旧快照文件取状态 |
| 目标 | `.omo/goals/current.yaml` | 直接修改 goals (仅人类可改) |
| 标准 | `.omo/standards/` | 从计划文档读标准 |

---

## 路由规则

> 文档域路由 → 全局系统级指令 `~/Documents/CLAUDE_GLOBAL.md` §A
> 全量路由表 → 异步引用只写了文档域R，未写RWorkspa（当前工作区直接操作）

| 场景 | 路由 |
|------|------|
| 找知识/跨域搜索 | KOS (`kairon/kos` 包) |
| 工程治理 | `.omo/_control/` |
| 运行 Worker | `.omo/workers/` 注册表 |
| 随手记录 | WPS Note |
| 深度研究 | `minerva` |

---

## 执行习惯

1. **3 步以上任务**先列 TodoList
2. **起草任何内容**需确认「主题+时间+接收对象+核心内容」
3. **完成后一句话汇报**，不确定标注「需确认」
4. **修改 .omo/ 内文件**需谨慎，遵循 AGENT.md 规范
5. **代码变更**前先读对应项目的 AGENTS.md / CLAUDE.md

---

## 重要上下文文件

| 文件 | 作用 |
|------|------|
| `README.md` | 项目总览、快速开始 |
| `AGENTS.md` | 开发者指南、命令、陷阱 |
| `LAYER-INDEX.md` | 分层架构索引（5+4+1+1） |
| `.omo/_knowledge/management/governance-charter-v1.md` | 5+3+1 治理宪章 |
| `.omo/INDEX.md` | 治理知识库导航 |
| `.omo/state/system.yaml` | 当前系统运行状态 |
| `.omo/goals/current.yaml` | 当前 Phase 目标 |
| `projects/ecos/src/ecos/ssot/mof/m3.yaml` | MOF M3 元元模型 |
| `projects/ecos/src/ecos/ssot/mof/m1/domain/` | 24 域实例模型 |

---

## Phase 上下文 (SSOT 指针, 勿硬编码易变值)

> 运行时数字 (Phase/健康分/任务数/活跃任务) 每会话变化, **禁止在本文件硬编码** — 以 `.omo/state/system.yaml` 为唯一真源, `goals/current.yaml` 为目标源。本段只保留稳定的架构原则 + 实测快照。

- **当前 Phase/健康分/任务状态**: 见 `.omo/state/system.yaml` (会话启动第[5]步已读; 实测 Phase 42 active, health 100, governance 100 A+, mof-version v0.0.40, 2026-06-23)
- **当前目标/Wave**: 见 `.omo/goals/current.yaml` (第[6]步; W1-W4 全 done)
- **稳定架构原则 (不随 phase 变)**: OMO MCP 化, agora 网关隔离固化, llm-gateway 统一算力调度, gbrain 图谱记忆, 5+4+1+1 分层

---

## 注意事项 / Gotchas

1. ✅ kairon 用 **uv**，不是 pip/poetry
2. ✅ Python 目标版本 **3.13+**
3. ✅ gbrain 用 **bun**，非 Node/npm
4. ✅ 数据库路径 (`data/db/`) 已 gitignore
5. ✅ `.omo/` 是治理核心
6. ❌ 不要从旧快照文件取状态 (HEALTH_DASHBOARD.md 不是 SSOT)
7. ❌ 不要复制事实到知识面文档 —— 用指针引用
8. ❌ 不要修改 goals/current.yaml（仅人类可改）
9. ❌ 不要删除旧的运行记录（仅可标记 archived）

## CI 治本机制 (v2.1, 2026-06-19)

- **子模块悬空根治**: `bin/sync-submodules-push.sh` + `.githooks/pre-push`(主仓 push 自动 sync 子模块, 防 gitlink 悬空 → CI 红). 新 clone 跑 `make install-hooks` 持久化.
- **private 子模块 CI 认证**: `CROSS_REPO_TOKEN` secret (用 OAuth `gh auth token`; **fine-grained PAT 对 submodule 有坑别用**). CI checkout `with: token: ${{ secrets.CROSS_REPO_TOKEN }}` + `submodules: recursive`.
- **端口 enforce baseline**: `scripts/check-vault-paths.py --check-ports` 自动读 `protocols/port-hardcode-baseline.yaml`(增量才 fail, `--baseline-init` 刷新, `--strict` 全景).
- **M0/L0 模型驱动**: `mof-validate` 0 错误 + `mof-audit` 0 漂移 + `mof-bridge-sync` Stage/Gate 完美 + `mof-derive` 7 阶段 0 风险 + SSB 765 events Integrity OK + X1-X4 0 错误.
- **硬编码清(相对脚本)**: ecos L0 9 工具(mof-*/l0_mcp_tools) + M0 `_paths` + SSB `CHAIN_CHECKPOINT` — 全 `Path(__file__).resolve().parents[N]`, CI 可移植.
- **debt 治理**: 24 items → 0 open(X3 数 open 不数 closed). `.omo/debt/` 在 .gitignore(本地治理状态).

---

*~Workspace 层网关 v2.1 · 2026-06-19 · CI 治本 + M0/L0 一致 + 硬编码清 + debt 0*
*全局入口 → ~/Documents/CLAUDE_GLOBAL.md*
