# Workspace 项目资产清单

> 生成: 2026-05-24 (Wave 1.2.B 审计后更新)
> 维护: `.omo/` 是工作区管理和维护的中心目录

---

## 概览

| 维度 | 数值 |
|------|------|
| Python 项目 | 14 |
| Node/TS 项目 | 2 |
| 文档/配置项目 | 3 |
| 总测试数 | 650+ |
| ruff 错误 | 0 |
| npm 漏洞 | 0 |
| 代码级耦合 | 2 处: minerva→sophia, iris→ssot-kernel |

---

## 一、Python 项目

### 1. SharedBrain — 数字化生命 OS

| 属性 | 值 |
|------|-----|
| **版本** | v10.0.0 |
| **状态** | Production/Stable |
| **Python** | 3.14 (uv, 2026-05-23 从 3.13 升级) |
| **入口** | `conductor` CLI |
| **目录** | `/Users/xiamingxing/Workspace/SharedBrain` |
| **体量** | 2.1G 总大小: .git 416M / organs 44M / nucleus 30M / data 85M / logs 16M |
| **测试** | `tests/unit/`, `tests/integration/` |
| **.venv** | ✅ 存在 |

---

### 2. Minerva — 本地优先深度研究系统

| 属性 | 值 |
|------|-----|
| **版本** | v0.11.0 |
| **状态** | Beta |
| **Python** | 3.14 |
| **入口** | `minerva research/cli/mcp/daemon/web` |
| **目录** | `/Users/xiamingxing/Workspace/minerva` |
| **测试** | **250 tests** |
| **MCP 工具** | 5 个 |
| **Web** | Dashboard `localhost:8765` |
| **依赖关系** | ← sophia (唯 1 处代码 import), → eCOS (被 CLI 调用) |
| **.venv** | ✅ 存在 |

---

### 3. Agora — MCP 服务融合 Hub

| 属性 | 值 |
|------|-----|
| **版本** | v1.4.0 |
| **状态** | Beta |
| **Python** | ≥3.11 |
| **入口** | `agora register/list/route/pipeline/discover/search/stats/watch/web/mcp` |
| **目录** | `/Users/xiamingxing/Workspace/agora` |
| **测试** | **58 tests** |
| **CLI 命令** | 20+ 子命令 (含新 `agora sync`) |
| **MCP 工具** | 9 个 |
| **关键特性** | Pipeline+EventBus 集成完成, agora sync 命令 |
| **状态** | v1.4 → v2.0 路线图中 |
| **.venv** | ✅ 存在 |

---

### 4. OntoDerive — 事实驱动知识工程引擎

| 属性 | 值 |
|------|-----|
| **版本** | v3.3.0 |
| **状态** | Beta |
| **Python** | ≥3.8 |
| **入口** | `ontoderive init/derive/check/toolforge/mcp` |
| **目录** | `/Users/xiamingxing/Workspace/ontoderive` |
| **测试** | **129 tests** (162 total with pipeline) |
| **核心** | 零外部依赖 |
| **依赖关系** | → pallas (CLI subprocess) |
| **.venv** | ✅ 存在 |

---

### 5. Pallas — 知识工程统一入口

| 属性 | 值 |
|------|-----|
| **版本** | v0.1.0 |
| **状态** | Alpha |
| **Python** | ≥3.10 |
| **入口** | `pallas match/derive/check/pipeline` |
| **目录** | `/Users/xiamingxing/Workspace/pallas` |
| **测试** | 有限 |
| **核心** | 零硬依赖, CLI subprocess 编排 |
| **.venv** | ✅ 存在 |

---

### 6. Sophia — 符号化研究范式引擎

| 属性 | 值 |
|------|-----|
| **版本** | v0.2.1 |
| **状态** | Alpha |
| **Python** | ≥3.10 |
| **入口** | `from sophia import compile_paradigm` |
| **目录** | `/Users/xiamingxing/Workspace/sophia` |
| **测试** | **27 tests** |
| **依赖关系** | → minerva (被 import), → pallas (pipeline 加载范式) |
| **.venv** | ✅ 存在 |

---

### 7. MetaOS — 元操作系统引擎

| 属性 | 值 |
|------|-----|
| **版本** | v7.1 |
| **状态** | ✅ 活跃 |
| **Python** | 3.14 |
| **入口** | `metaos` CLI + `metaos-mcp` MCP server |
| **目录** | `/Users/xiamingxing/Workspace/MetaOS` |
| **测试** | 38/39 unit pass (1 fail: ollama ModuleNotFoundError); 8 场景测试就绪 |
| **核心** | 5630 LOC engine/ + 架构文档; 4 层架构 (S/M/D/H) |
| **MCP 工具** | 9 个 (morning/evening/review/gate/status/day/trace/ssot/health) |
| **外部依赖者** | 0 |
| **健康审计** | **KEEP** — 有完整 README + 架构文档 + 活跃贡献; 待修复 1 个测试 |
| **.venv** | ✅ 存在 |

---

### 8. SSOT — 单一真相源（配置/状态管理）

| 属性 | 值 |
|------|-----|
| **版本** | 开发版 |
| **状态** | ✅ 活跃 |
| **Python** | 3.14 |
| **入口** | `ssot-kernel` CLI |
| **目录** | `/Users/xiamingxing/Workspace/SSOT` |
| **核心** | 12419 LOC ssot-kernel (extractor/evolution/patterns/meta_model) |
| **测试** | 45/46 unit pass (1 fail: contradiction_triggers AssertionError) |
| **外部依赖者** | iris (optional import at `ssot_kernel.config_loader`) |
| **健康审计** | **KEEP** — 有外部消费者 + 活跃; 待修复 1 个测试; 缺顶层 pyproject.toml |
| **.venv** | ✅ 存在 (tool/ssot-kernel/) |

---

### 9. eCOS — 外化认知操作系统

| 属性 | 值 |
|------|-----|
| **版本** | v0.6.0 |
| **状态** | Alpha |
| **Python** | ≥3.10 |
| **入口** | 独立脚本 + `ecos-dashboard`, `ecos-scheduler` |
| **目录** | `/Users/xiamingxing/Workspace/eCOS` |
| **测试** | **98 tests** |
| **当前 Phase** | Phase 9 (主动服务层) |
| **安全评分** | 94% |
| **架构评分** | 95% |
| **.venv** | ✅ 存在 |

---

### 10. BOS-Skill-CLI — 技能发现与激活

| 属性 | 值 |
|------|-----|
| **版本** | v0.1.0 |
| **状态** | Alpha |
| **Python** | ≥3.11 |
| **入口** | `bos-skill list/search/activate/status/doctor/audit` |
| **目录** | `/Users/xiamingxing/Workspace/bos-skill-cli` |
| **测试** | 存在 |
| **.venv** | ✅ 存在 |

---

### 11. Iris — 个人知识平台连接器 Hub

| 属性 | 值 |
|------|-----|
| **版本** | v0.1.0 |
| **状态** | ✅ 活跃 |
| **Python** | ≥3.10 |
| **入口** | MCP server (stdio) |
| **目录** | `/Users/xiamingxing/Workspace/iris` |
| **测试** | **66 tests** |
| **依赖关系** | → ssot-kernel (optional import for SSOT domain loading) |
| **.venv** | ✅ 存在 |

---

### 12. Eidos — 元模型本体建模 / Schema 验证

| 属性 | 值 |
|------|-----|
| **版本** | 开发版 |
| **状态** | ✅ 活跃 |
| **Python** | 3.14 |
| **入口** | `eidos mcp-server` |
| **目录** | `/Users/xiamingxing/Workspace/eidos` |
| **测试** | 存在 |
| **.venv** | ✅ 存在 |

---

### 13. Kronos — 知识摄取管线

| 属性 | 值 |
|------|-----|
| **版本** | 开发版 |
| **状态** | ✅ 活跃 (2026-05-24 纳入 Git 管理) |
| **Python** | 3.14 |
| **入口** | `kronos` |
| **目录** | `/Users/xiamingxing/Workspace/kronos` |
| **.venv** | ✅ 存在 |

---

### 14. Forge — 内部工具注册与发现

| 属性 | 值 |
|------|-----|
| **版本** | 开发版 |
| **状态** | ✅ 活跃 |
| **Python** | 3.14 |
| **入口** | `forge` |
| **目录** | `/Users/xiamingxing/Workspace/Forge` |
| **.venv** | ✅ 存在 |

---

### 15. CodeAnalyze — 代码与文档分析工具集

| 属性 | 值 |
|------|-----|
| **版本** | 开发版 |
| **状态** | ✅ 活跃 |
| **Python** | 3.14 |
| **入口** | `codeanalyze` |
| **目录** | `/Users/xiamingxing/Workspace/codeanalyze` |
| **.venv** | ✅ 存在 |

---

### 16. Gateway (Python) — Workspace MCP 统一入口

| 属性 | 值 |
|------|-----|
| **版本** | 0.1.0 |
| **用途** | 消除 Agent CLI MCP 配置中的绝对路径依赖 |
| **架构** | `bin/*-mcp` → 代理到各项目实际 MCP 服务器 |
| **.venv** | N/A (shell wrappers only) |

---

### 17. kos — 知识操作系统 CLI

| 属性 | 值 |
|------|-----|
| **版本** | 2.0.0 |
| **入口** | `kos help`, `kos-mcp-server` |
| **目录** | `/Users/xiamingxing/Workspace/kos` |
| **Python** | 3.14 |
| **MCP 工具** | 26 (13基础 + 13域: self=3 + collab=6 + consensus=4) |
| **新增模块** | `kos/self/` (L4), `kos/collab/` (L3), `kos/consensus/` (X3) — Phase 5 |
| **EntityType** | 15种 (Phase 5新增8种: ROLE/AXIOM/PRINCIPLE/THEORY/FRAMEWORK/SKILL/CONSENSUS/TASK) |
| **.venv** | ❌ 缺失 (待创建) |

---

## 二、Node/TypeScript 项目

### 18. AgentMesh — 多 Agent 网关+编排+能力 SDK (Monorepo)

| 属性 | 值 |
|------|-----|
| **版本** | v2.0.0 |
| **运行时** | bun |
| **入口** | `agentmesh` CLI, HTTP :3000, MCP stdio |
| **目录** | `/Users/xiamingxing/Workspace/agentmesh` |
| **包** | 7 packages: core-types, model-orchestrator, gateway, engine, toolkit, server, cli |
| **测试** | **45 tests** (155 个 test files) |
| **LOC** | 191,887 total |
| **端口** | HTTP 3000 |
| **编译错误** | 0 |
| **状态** | 🔥 最活跃 (多日连续提交) |
| **注意** | agent-toolkit 和 honeycomb 已物理删除, 代码已全部合入此 monorepo |
| **MCP Server** | 11 tools |

---

### 19. AggreResearch — 聚合搜索调研系统

| 属性 | 值 |
|------|-----|
| **运行时** | node |
| **入口** | `dist/index.js` |
| **目录** | `/Users/xiamingxing/Workspace/AggreResearch` |
| **状态** | 🗄️ 已归档 (2026-05-24) — 功能由 minerva 覆盖 |

---

## 三、文档/配置项目

### 20. DigitalBrainOS — 数字大脑 OS 规划

| 属性 | 值 |
|------|-----|
| **目录** | `/Users/xiamingxing/Workspace/DigitalBrainOS` |
| **内容** | 架构规划, 工作包, 报告, Agent 定义, 协调文档 |

### 21. Metacog — 元认知知识库

| 属性 | 值 |
|------|-----|
| **目录** | `/Users/xiamingxing/Workspace/metacog` |
| **结构** | `01-theories/`, `02-practices/`, `03-foundations/`, `04-applications/` |

### 22. AI-Tools — Shell 工具集

| 属性 | 值 |
|------|-----|
| **目录** | `/Users/xiamingxing/Workspace/ai-tools` |
| **内容** | CLI 工具, skills, 配置脚本, install.sh |

---

## 四、已合并 / 已归档

| 旧项目 | 命运 | 日期 |
|--------|------|------|
| **agent-toolkit** | 🗑️ 物理删除 — 代码合入 agentmesh/packages/toolkit | 2026-05-23 |
| **honeycomb** | 🗑️ 物理删除 — 代码合入 agentmesh/packages/engine | 2026-05-23 |
| **AggreResearch** | 🗄️ 归档至 `_archived/ecosystem/` | 2026-05-24 |
| **hermes-agent-self-evolution** | 🗄️ 归档至 `_archived/ecosystem/` | 2026-05-24 |
| **eCAS** | 🗑️ 已清理 — 仅 init, 无实质代码 | 2026-05-23 |
| **organs** | 🗑️ 已清理 — 仅 init, 无实质代码 | 2026-05-23 |
| **Gateway (Python) legacy 脚本** | 🗑️ 物理删除 (6 文件: diagnose/graph/insights/watch/restore/verify_skills) | 2026-05-24 |

---

## 五、交叉引用: 关键文档

| 文档 | 位置 | 内容 |
|------|------|------|
| 架构拓扑 | `ARCHITECTURE.md` | 跨项目桥接图 + 耦合矩阵 + God Nodes |
| 接口契约 | `CONTRACTS.md` | 所有 CLI JSON Schema 定义 |
| 对外能力 | `CAPABILITIES.md` | Skills / MCP / CLI / HTTP 全线能力 |
| 用户旅程 | `USER_JOURNEY.md` | 30 分钟上手 |
| 会话复盘 | `SESSION_RETRO.md` | 2026-05-18 大扫除复盘 |
| 项目治理 | `AGENTS.md` | 项目角色与治理边界 + 健康审计 |
| 知识图谱 | `graphify-out/GRAPH_REPORT.md` | 7192 nodes / 12074 edges |
| 任务池 | `.omo/TASK_POOL.md` | 共享任务池 (Phase 1-4) |

---

## 六、未完成任务列表 (Phase 2-4 backlog)

```
[ ] Agora Phase 3: 熔断器 + 多实例 LB + 流式 Pipeline
[ ] Agora v2.0: Web Dashboard + 多租户 + 工具市场
[ ] 跨项目集成测试
[ ] Docker Compose 统一编排
[ ] MetaOS: 修复 test_ollama_backend (ModuleNotFoundError)
[ ] SSOT: 修复 test_contradiction_triggers (AssertionError)
[ ] SSOT: 创建顶层 pyproject.toml
[ ] kos: 创建 .venv
```

---

## 七、目录规范

```
Workspace/
├── .omo/                    # 工作区管理中心
│   └── INVENTORY.md         # 本项目资产清单
├── <project>/
│   ├── .venv/               # 虚拟环境 (每个 Python 项目独立)
│   ├── .python-version      # Python 版本
│   ├── pyproject.toml       # 项目配置
│   ├── src/                 # 源码
│   ├── tests/               # 测试
│   ├── AGENTS.md            # AI Agent 入口 (关键项目有)
│   └── CLAUDE.md            # Claude 配置 (部分项目有)
├── ARCHITECTURE.md          # 架构拓扑
├── AGENTS.md                # 项目角色与治理边界
├── CONTRACTS.md             # JSON Schema 契约
├── CAPABILITIES.md          # 对外能力
├── USER_JOURNEY.md          # 用户旅程
├── SESSION_RETRO.md         # 会话复盘
└── CLAUDE.md                # 工作空间根配置
```

---

*维护者: Sisyphus / 夏同学*
*生成: 2026-05-24*
