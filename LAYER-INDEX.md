# LAYER-INDEX.md — 项目分层索引

> 基于 omostation 4-Layer + 1 架构
> 更新: 2026-06-04 | P1/P2 修复 · agora 7430 确认监听 · L1 包列表 28 包

## I0 — Service Mesh / 路由层

| 项目 | 角色 | 端口 | 状态 |
|------|------|------|------|
| agora | MCP 服务发现 + 代理 + 断路器 | 7430 (HTTP), 7431 (SSE) | 🟢 运行中 |
| agora-mcp | Agora 内部 MCP 服务器入口（`pyproject.toml` 定义） | — | 🟢 已集成至 agora 包 |

## L1 — 知识工程层

| 项目 | 包路径 | 工具数 | 状态 |
|------|--------|--------|------|
| eidos | `kairon/packages/eidos` | 7 MCP tools | 🟢 format_version 已修复 |
| ontoderive | `kairon/packages/ontoderive` | 5 tools | 🟢 (含 1,920 JSON 推导日志) |
| kos | `kairon/packages/kos` | 26 tools | 🟢 |
| minerva | `kairon/packages/minerva` | 5 super-tools | 🟢 |
| sophia | `kairon/packages/sophia` | 8 tools | 🟢 |
| iris | `kairon/packages/iris` | 8 tools | 🟢 |
| ssot | `kairon/packages/ssot` | 6 tools | 🟢 |
| forge | `kairon/packages/forge` | 70 tools (JSON 注册表) | 🟡 无 MCP @tool |
| codeanalyze | `kairon/packages/codeanalyze` | 多种 | 🟢 |
| kronos | `kairon/packages/kronos` | 9 tools | 🟢 |
| metaos | `kairon/packages/metaos` | 基础 | 🟢 sys.path 已修复 |
| cron-service | `kairon/packages/cron-service` | 3 tools | 🟢 |
| shared-lib | `kairon/packages/shared-lib` | 共享库 | 🟢 |
| engine-core | `kairon/packages/engine-core` | — | 🟢 |
| core-models | `kairon/packages/core-models` | — | 🟢 |
| observability | `kairon/packages/observability` | — | 🟢 |
| gc-engine | `kairon/packages/gc-engine` | — | 🟢 |
| ecos | `kairon/packages/ecos` | — | 🟢 |
| llm-gateway | `kairon/packages/llm-gateway` | — | 🟢 |
| wksp | `kairon/packages/wksp` | — | 🟢 |
| eu-pricing | `kairon/packages/eu-pricing` | — | 🟢 |
| kaironcloud-billing | `kairon/packages/kaironcloud-billing` | — | 🟢 |
| kairon-assistant | `kairon/packages/kairon-assistant` | — | 🟢 |
| kairon-voice | `kairon/packages/kairon-voice` | — | 🟢 |
| symphony-protocol | `kairon/packages/symphony-protocol` | — | 🟢 |
| pontus | `kairon/packages/pontus` | — | 🟢 |
| sharedbrain-standalone | `kairon/packages/sharedbrain-standalone` | — | 🟢 |
| agent-hub | `kairon/packages/agent-hub` | — | 🟢 |

## L2 — 集成层

| 项目 | 角色 | 状态 |
|------|------|------|
| sharedbrain-bridge | kairon × SharedBrain 桥接（EU/免疫/同步） | 🟢 新建 |
| SharedBrain (D_Gateway) | 数字生命 OS MCP 网关 | ⚪ 源码已归档至 `projects/_archived/SharedBrain-code/` |

## L3 — Agent 层

| 项目 | 角色 | 状态 |
|------|------|------|
| kairon/agent-runtime | Agent 执行引擎（原 agentmesh Engine） | 🟢 |
| kairon/agent-hub | Agent 注册中心 | 🟢 |
| kairon/agora | MCP 服务发现 + 代理 + 断路器（6 核心 MCP handler + proxy） | 🟡 tests 收集错误 41 |
| kairon/llm-gateway | LLM 路由 + 配额管理（原 agentmesh Model-Orchestrator） | 🟢 |
| agentmesh | 已 100% 迁移到 kairon，残留壳已清理，归档至 `projects/_archived/` | ⚪ 已归档 |

## L4 — 知识存储层

| 项目 | 后端 | 状态 |
|------|------|------|
| gbrain | Postgres (TypeORM) + MCP | 🟢 |
| SharedBrain | SQLite 数据层，已迁至 `data/sharedbrain/` | ⚪ 仅数据持久，无业务代码 |

## 治理层

| 模块 | 角色 |
|------|------|
| .omo/ | 治理知识库（状态/架构/审计/标准/知识面） |
| .github/workflows/ | CI/CD 工作流 |
| scripts/ | OMO 治理自动化（`omo/` + `shell/`） |
| data/ | 数据层统一管理（`db/`, `kos/`, `sharedbrain/`） |

## 当前治理入口

| 入口 | 文件 |
|------|------|
| 当前目标 | `.omo/goals/current.yaml` |
| 可执行任务 | `.omo/tasks/active/*.yaml` |
| 主蓝图 | `.omo/MASTER-BLUEPRINT.md` |
| 交付/测试标准 | `.omo/standards/planning-blueprint-delivery-test-standard.md` |
