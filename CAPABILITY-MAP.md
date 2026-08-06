# Cockpit 能力地图

> 自动生成于 1970-01-01T00:00:00Z | 版本 1.0.0
> 源: `docs/generated/capability-registry.yaml` | 请勿手动编辑
> 生成器: `bin/cockpit/gen-help-docs.py`

## 概览

| 通道 | 数量 |
|------|------|
| CLI 命令 (含子命令) | 121 |
| MCP 工具 | 554 |
| MCP 服务器 | 28 |
| BOS 服务 | 202 |
| BOS 域 | 16 |

## MCP 服务器清单

| 服务器 | 层 | 工具数 | 传输 | 文件 |
|--------|-----|--------|------|------|
| `gbrain` | L2 | 75 | stdio | `projects/gbrain/src/core/operations/exports.ts` |
| `agora` | I0 | 65 | stdio/sse | `projects/agora/src/agora/server/mcp.py` |
| `l4-kernel` | L4 | 45 | stdio/http/sse | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `kos` | L2 | 44 | stdio | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 44 | stdio | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `ecos` | L0 | 28 | stdio | `projects/ecos/src/ecos/mcp_server.py` |
| `model-driven` | M0 | 28 | stdio | `projects/model-driven/src/model_driven/mcp_server.py` |
| `runtime` | L1 | 28 | stdio | `projects/runtime/src/runtime/mcp_server.py` |
| `ecos-integration` | L0 | 26 | stdio | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `codeanalyze` | L2 | 25 | stdio | `projects/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `metaos` | L2 | 24 | stdio | `projects/metaos/src/metaos/mcp_server.py` |
| `omo` | L2 | 22 | stdio | `projects/omo/src/omo/mcp_server.py` |
| `kronos` | L2 | 16 | stdio | `projects/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `aetherforge` | X | 10 | stdio | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `ecos-ssot` | L0 | 9 | stdio | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `iris` | L2 | 8 | stdio | `projects/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 8 | stdio | `projects/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `minerva` | L2 | 8 | stdio | `projects/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `forge` | L2 | 7 | stdio | `projects/kairon/packages/forge/src/mcp_server.py` |
| `ontoderive` | L2 | 7 | stdio | `projects/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `aetherforge-mesh` | X | 6 | stdio | `projects/aetherforge/packages/mesh/src/compute_mesh/api/mcp_server.py` |
| `family-hub` | X | 6 | stdio | `projects/family-hub/mcp_server.py` |
| `toolforge` | L2 | 5 | stdio | `projects/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
| `aetherforge-gateway` | X | 3 | stdio | `projects/aetherforge/packages/gateway/src/llm_gateway/mcp_server.py` |
| `c2g` | X | 3 | stdio | `projects/c2g/src/c2g/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 2 | stdio | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `agent-runtime` | L3 | 2 | stdio | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `cockpit-mcp` | L3 | 0 | stdio | `projects/cockpit/src/cockpit/scripts/cockpit_mcp.py` ⚠️未找到 |

## BOS 服务域分布

| 域 | 服务数 |
|-----|--------|
| `agora` | 3 |
| `analysis` | 28 |
| `capability` | 44 |
| `cockpit` | 3 |
| `compute` | 3 |
| `ecos` | 10 |
| `forge` | 1 |
| `governance` | 34 |
| `l4-kernel` | 1 |
| `memory` | 47 |
| `meta` | 1 |
| `omo` | 4 |
| `persona` | 10 |
| `runtime` | 1 |
| `swarm` | 1 |
| `system` | 11 |

## CLI 命令清单

> 完整命令参考见 [`CLI-REFERENCE.md`](CLI-REFERENCE.md)

| 命令 | 描述 |
|------|------|
| `cockpit agent` | 🤖 Agent 治理控制入口 (bootstrap / status / start / claim / verify / closeout) |
| `cockpit agent-onboard` | 🤖 Agent 入职引导 checklist (profile + MCP + BOS + skills) |
| `cockpit agent-runtime` | 🤖 Agent Runtime 任务执行 / HTTP server (替代独立 agent-runtime 命令) |
| `cockpit agent-workflow` | 🤖 Agent 可执行治理流程 (委派 root bin/agent-workflow.py) |
| `cockpit agora` | Agora BOS 网关入口 (委派 agora CLI) |
| `cockpit analyze` | 运行全部分析工具 |
| `cockpit api` | 启动 API server |
| `cockpit archive` | 归档已处理完毕的 Inbox 待办文件 |
| `cockpit ask` | 向大脑提问（知识检索 + LLM 回答） |
| `cockpit assistant` | P5-F2 work-assistant: 1 真实工作 query → 结构化草稿 |
| `cockpit audit` | 🔍 6 维度全方位审计 (调 bin/workspace-audit) |
| `cockpit backends` | 列出 BOS 后端 |
| `cockpit bos` | BOS URI 查询与管理 |
| `cockpit bos-capability` | BOS capability / toolbox 外部能力 |
| `cockpit bos-inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit brain` | 个人数字大脑 — 知识检索 + 记忆 + 智能问答 |
| `cockpit brief` | 会话简报 |
| `cockpit bus` | Omni-Bus 三平面入口 |
| `cockpit c2g` | 🎯 C2G 战略罗盘 (status/pipeline) |
| `cockpit capability` | BOS capability 域 / toolbox 外部能力 |
| `cockpit cards` | 显示 CARDS 卡片状态 |
| `cockpit channels` | 🌐 External channels inventory (ECCP) — 生成/查看 external-channels.yaml |
| `cockpit code` | 代码库分析与审查 (基于 codeanalyze) |
| `cockpit compass` | 🧭 C2G 战略罗盘 (V2P -> C2G -> AGC 统一管理) |
| `cockpit compute` | 算力与 LLM 网关操作 (委派 aetherforge) |
| `cockpit consolidate` | sleep-time 巩固 (默认 dry-run) |
| `cockpit context` | 显示系统上下文 (Phase/CARDS/约束/引导) |
| `cockpit contracts` | 契约验证 |
| `cockpit daily` | 每日研究简报 |
| `cockpit dashboard` | 打开 Web Dashboard |
| `cockpit data` | 数据目录索引 / 类型注册 / TTL 清理 |
| `cockpit debt` | 债务评分 (omo-debt Pattern 09 v2.1) |
| `cockpit demo` | 快速演示 |
| `cockpit discover` | 发现可用功能和资源 |
| `cockpit domains` | 列出 L4 所有域及其状态 |
| `cockpit down` | 停止观测栈 |
| `cockpit event` | 导出事件封套 (EventEnvelope) |
| `cockpit events` | 实时查看 Agora SSE 事件流 (Phase 34 L3 Dashboard) |
| `cockpit events-watch` | 实时监听 SSE 事件流简便入口 |
| `cockpit export` | 导出契约封套 |
| `cockpit export-research` | 将研究对象导出为 WorkspaceObject JSON |
| `cockpit family-hub` | 家庭数字枢纽入口 |
| `cockpit finance` | 💰 个人财务门户引导 (场景/原则/入口, 委派 @个人 域) |
| `cockpit forget` | 遗忘传播 |
| `cockpit gac` | GaC 治理健康检查 (ADR-0106, 7 机制 + 115 规则 + drift) |
| `cockpit gbrain` | Postgres-native 知识库入口 (委派 gbrain CLI) |
| `cockpit gc` | 清理 data/tmp 过期文件 |
| `cockpit get` | 查 1 个 card |
| `cockpit gongwen` | 📄 公文写作门户引导 (文种/规范/入口, 委派 @公文 域) |
| `cockpit governance` | 架构治理 (委派 arcnode-*) |
| `cockpit graph` | 运行语义图谱分析 |
| `cockpit health` | 一键系统健康检查 |
| `cockpit help` | 查看产品地图与快速入门 (cockpit help <关键词> 模糊搜命令/工具/服务) |
| `cockpit history` | 查看对话历史 |
| `cockpit identity` | 导出身份封套 (IdentityEnvelope) |
| `cockpit impact` | 分析符号的变更影响面 |
| `cockpit import` | 导入外部内容 |
| `cockpit inbox` | BOS Inbox 多源私有知识神经网查询与操作 |
| `cockpit index` | 刷新 data/_index 元数据 |
| `cockpit init` | 🚀 初始化向导（同 quickstart） |
| `cockpit invoke` | 调用 capability 服务（执行 BOS YAML command） |
| `cockpit iterate` | ♻️ C2G 双擎迭代流 (MetaOS 发散 -> Model-Driven 桥接 -> OMO 门控执行) |
| `cockpit kairon` | kairon 知识引擎 monorepo 聚合入口 |
| `cockpit kems` | 🧬 KEMS 域治理 (domains/status/scan) |
| `cockpit knowledge` | 📚 KOS 知识检索 (search/status/stats) |
| `cockpit list` | 列债务项 (委派 omo debt) |
| `cockpit logs` | 查看日志 |
| `cockpit mcp` | 启动 MCP server 或列出工具 |
| `cockpit memory` | 🧠 Memory OS (status/recall/write/forget/consolidate/knowledge-ref) |
| `cockpit mesh` | omlx 算力网格路由入口 |
| `cockpit metrics` | 查看 bus metrics 快照 |
| `cockpit model-driven` | 模型驱动生命周期入口 (委派 model-driven CLI) |
| `cockpit mof` | MOF 元模型操作 (委派 mof CLI) |
| `cockpit monitor` | 📊 实时终端大盘 (C2G Pipeline 监控仪, 实时刷新 Ctrl+C 退出) |
| `cockpit mutate` | 通过 agora 统一 BOS URI 写协议修改资源 |
| `cockpit nodes` | 列出 KOS 中注册的算力节点 |
| `cockpit observe` | 可观测性栈（Langfuse）入口 |
| `cockpit omo` | OMO CLI 委派 (debt/state/governance/lint/...) |
| `cockpit onboarding` | 为 AI 构建项目全貌上下文 |
| `cockpit pack` | 将代码库打包为 LLM 友好格式 |
| `cockpit pending` | 查看未决待办快照预览 |
| `cockpit pipeline` | pipeline 概览 |
| `cockpit product-health` | 产品健康度检测 |
| `cockpit profile` | 查看/编辑身份档案 (L4 入口) |
| `cockpit publish` | 发布事件 |
| `cockpit quickstart` | 🚀 新用户快速上手向导（环境核验 + 上手指引） |
| `cockpit quickstart-check` | 快速检查新用户环境核验状态 |
| `cockpit radar` | P5-F1 technical-radar: 扫描研究活动, 产出 ≥3 upgrade candidates |
| `cockpit read` | 通过 BOS 网关统一读取指定 URI 资源 |
| `cockpit readiness` | P66: governance readiness dashboard 摘要 (4 卡片: summary/dimensions/alerts/history) |
| `cockpit recall` | 意图路由召回（neo4j/temporal 支持 --as-of） |
| `cockpit register` | 注册 BOS 服务 |
| `cockpit reload` | 重载 BOS 配置/M1 |
| `cockpit remember` | 手动存入偏好/事实 |
| `cockpit research` | 深度研究 |
| `cockpit resolve` | 统一 BOS URI 路由解析与目标元数据提取 |
| `cockpit route` | 为模型选择最优节点 |
| `cockpit runtime` | runtime CLI 委派 (Matrix/Scheduler/KEI 沙箱) |
| `cockpit scan` | 平面扫描 |
| `cockpit scenario` | P5 统一 scenario 入口 (radar/assistant/health) |
| `cockpit score` | 评分债务项 |
| `cockpit search` | 全文搜 CARDS |
| `cockpit serve` | stdio JSON-RPC serve mode |
| `cockpit skill` | 运行 L4 定时技能 |
| `cockpit ssb` | SSB 签名链操作 (委派 ecos-ssb) |
| `cockpit stats` | 索引统计 |
| `cockpit status` | 系统健康 |
| `cockpit summary` | 债务摘要 (委派 omo debt) |
| `cockpit swarm` | 🤖 多 agent 实时活动监控 (active runs/locks/worktree/claims/子模块 dirty/冲突) |
| `cockpit topics` | 列出已注册 topic |
| `cockpit tui` | 极客终端交互控制台 (Textual 全屏 TUI) |
| `cockpit types` | 查看已注册的数据类型 |
| `cockpit up` | 启动观测栈 |
| `cockpit url` | 打印 Langfuse Web URL |
| `cockpit validate` | 验证 Workspace 契约 |
| `cockpit vault` | 搜索 L4 Vault 知识库 |
| `cockpit version` | 版本信息 |
| `cockpit watch` | 监听 BOS Inbox 紧急待办与提醒快照 (Event-Driven Watcher) |
| `cockpit wave2` | 📈 Wave2 预测治理面板 (dashboard/proposals/predictive JSON) |
| `cockpit workflow` | BOS workflow 相关 |
| `cockpit write` | 双轨写入 (+ Neo4j FACT 若配置) |

---
*由 `bin/cockpit/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*