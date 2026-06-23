---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 器官全面迁移融合 — 主任务池与执行计划

> 2026-06-02 · 10 器官 7 并行 agent 深度扫描 · 总计未提取 ~370+ 模块
>
> 扫描覆盖: D_Execution (275文件/55K行), D_Memory (133文件/42K行), D_Gateway (98文件/26K行),
> D_Harvest (110文件/29K行), D_Governance (131文件/27K行), D_Logos (51文件/16K行),
> D_Cloud (21文件/5K行), D_Intelligence (20文件/4K行), D_Continuity (15文件/4K行), D_Voice (11文件/2K行)

---

## 总览统计

| 器官 | 未提取模块数 | 零耦合 | 低耦合 | 中耦合 | 高耦合 | 预估行数 |
|------|:---------:|:-----:|:-----:|:-----:|:-----:|:------:|
| D_Execution | ~85 | 30 | 20 | 25 | 10 | ~22,000 |
| D_Memory | ~90 | 6 | 30 | 40 | 14 | ~35,000 |
| D_Gateway | ~76 | 7 | 25 | 29 | 15 | ~22,000 |
| D_Harvest | ~45 | 9 | 26 | 13 | 6 | ~14,000 |
| D_Governance | ~42 | 1 | 30 | 15 | 4 | ~14,000 |
| D_Logos | ~34 | 9 | 11 | 10 | 4 | ~12,000 |
| D_Intelligence | ~15 | 6 | 3 | 3 | 3 | ~3,600 |
| D_Continuity | ~10 | 0 | 5 | 4 | 1 | ~3,980 |
| D_Cloud | ~10 | 1 | 5 | 3 | 1 | ~2,400 |
| D_Voice | ~3 | 0 | 1 | 1 | 1 | ~1,460 |
| **总计** | **~410** | **69** | **156** | **143** | **59** | **~130K** |

---

## 四波执行策略

### Wave 1: P0 零耦合快速收获 (69 模块 · 目标 1-2 天)

直接复制 + 替换包路径 + 补测试即可，几乎不需要解耦工作。

#### L1: engine-core 补充 (D_Execution)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `organs/communication/role_message.py` | 120 | RoleMessage dataclass + MessageType/MessagePriority 枚举 | `engine-core/role_message.py` |
| `organs/communication/message_broker.py` | 142 | Pub/sub 消息代理 | `engine-core/message_broker.py` |
| `organs/engine/lifecycle/state_machine.py` | 156 | SwarmStateMachine 状态机 | `engine-core/lifecycle_state_machine.py` |
| `organs/engine/dispatch/domain_router.py` | 92 | DomainRouter 域路由注册 | `engine-core/domain_router.py` |
| `organs/engine/dispatch/handlers/agent.py` | 135 | Agent 命令处理器 | `engine-core/handlers/agent.py` |
| `organs/engine/dispatch/handlers/execution.py` | 321 | Execution 命令处理器 | `engine-core/handlers/execution.py` |
| `organs/engine/dispatch/handlers/economy.py` | 92 | Economy 命令处理器 | `engine-core/handlers/economy.py` |
| `organs/engine/dispatch/handlers/genesis.py` | 59 | Genesis 命令处理器 | `engine-core/handlers/genesis.py` |
| `organs/engine/dispatch/handlers/memory.py` | 73 | Memory 命令处理器 | `engine-core/handlers/memory.py` |
| `organs/engine/dispatch/handlers/tool.py` | 52 | Tool 命令处理器 | `engine-core/handlers/tool.py` |
| `organs/engine/cost_aware_dispatcher.py` | 148 | EU感知调度 | `engine-core/cost_aware_dispatcher.py` |
| `organs/engine/task_dependency_dag.py` | 200 | DAG任务依赖 | `engine-core/task_dependency_dag.py` |
| `organs/engine/session_context_store.py` | 143 | 会话上下文持久化 | `engine-core/session_context_store.py` |
| `organs/engine/slo_scheduler.py` | 156 | SLO感知调度 | `engine-core/slo_scheduler.py` |
| `organs/engine/economy_seed.py` | 99 | 初始能量单元 | `engine-core/economy_seed.py` |
| `organs/engine/mutation_validator.py` | 113 | 任务mutation校验 | `engine-core/mutation_validator.py` |
| `organs/engine/okr_framework.py` | 142 | OKR跟踪 | `engine-core/okr_framework.py` |
| `organs/engine/reranker.py` | 123 | 结果重排序 | `engine-core/reranker.py` |
| `organs/engine/goal_task_mapper.py` | 118 | 目标→任务映射 | `engine-core/goal_task_mapper.py` |
| `organs/engine/env_resolver.py` | 288 | 环境变量解析 | `engine-core/env_resolver.py` |
| `organs/engine/refinement_daemon.py` | 85 | 迭代精炼 | `engine-core/refinement_daemon.py` |
| `organs/engine/primordial_toolkit.py` | 239 | 引导工具集 | `engine-core/primordial_toolkit.py` |
| `organs/engine/burndown_engine.py` | 162 | Burndown跟踪 | `engine-core/burndown_engine.py` |
| `organs/engine/association_engine.py` | 157 | 任务-工作器关联 | `engine-core/association_engine.py` |
| `organs/engine/context_injector.py` | 107 | 上下文注入器 | `engine-core/context_injector.py` |
| `organs/security_utils.py` | 328 | 安全工具 | `engine-core/security_utils.py` |
| `organs/task_context.py` | 260 | 任务上下文 | `engine-core/task_context.py` |
| `organs/worker_profile.py` | 283 | Worker画像 | `engine-core/worker_profile.py` |
| `organs/worker_abstraction.py` | 204 | Worker抽象 | `engine-core/worker_abstraction.py` |
| `organs/conflict_resolver.py` | 43 | 冲突解决 | `engine-core/conflict_resolver.py` |
| `organs/bidder.py` | 147 | 投标器 | `engine-core/bidder.py` |
| `organs/semantic_matcher.py` | 46 | 语义匹配 | `engine-core/semantic_matcher.py` |

#### L1: symphony-protocol 补充 (D_Execution)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `organs/symphony/stage_manager.py` | 575 | 4阶段生命周期管理器 | `symphony-protocol/stage_manager.py` |
| `organs/symphony/thinking_bridge.py` | 147 | 思维模式桥接 | `symphony-protocol/thinking_bridge.py` |

#### L1: shared-lib 补充 (D_Harvest)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `utils/retry.py` | 153 | 指数退避重试 | `shared-lib/utils/retry.py` |
| `utils/concurrent.py` | 392 | 并发控制 | `shared-lib/utils/concurrent.py` |
| `utils/versioning.py` | 252 | 知识条目版本管理 | `shared-lib/utils/versioning.py` |
| `utils/rollback.py` | 261 | 回滚栈 | `shared-lib/utils/rollback.py` |
| `utils/error_handler.py` | 263 | 错误处理 | `shared-lib/utils/error_handler.py` |

#### L1: agora 补充 (D_Gateway 零/低耦合)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `organs/auth_models.py` | 301 | OAuth2/JWT 数据模型 | `agora/auth_models.py` |
| `organs/connection_pool.py` | 261 | 连接池管理 | `agora/connection_pool.py` |
| `organs/api_types.py` | 194 | API 类型定义 | `agora/api_types.py` |
| `organs/tools_template.py` | 116 | MCP工具模板 | `agora/tools_template.py` |
| `organs/unified_protocol_adapter.py` | 289 | 多协议适配器 | `agora/unified_protocol_adapter.py` |
| `organs/umbilical_protocol.py` | 272 | 父子实例协议 | `agora/umbilical_protocol.py` |
| `interfaces/tool_interface_contract.py` | 118 | 工具接口契约 | `agora/tool_contract.py` |
| `interfaces/base_tool.py` | 204 | BaseTool ABC | `agora/base_tool.py` |

#### L1: ontoderive 补充 (D_Logos)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `meta_validate_types.py` | 191 | 验证类型定义 | `ontoderive/engine/meta_validate_types.py` |
| `config_manager.py` | 420 | 治理配置管理 | `ontoderive/engine/config_manager.py` |
| `authority_graph.py` | 437 | 权威图分析器 | `ontoderive/engine/authority_graph.py` |
| `quality_probe.py` | 590 | 质量探针 | `ontoderive/engine/quality_probe.py` |
| `diff_analyzer.py` | 479 | 差异分析器 | `ontoderive/engine/diff_analyzer.py` |
| `plugin_system.py` | 774 | 插件系统 | `ontoderive/engine/plugin_system.py` |

#### L1: 新包 kairon-assistant (D_Intelligence)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `smart_assistant/command_parser.py` | 265 | NL命令解析 | `kairon-assistant/command_parser.py` |
| `smart_assistant/context_manager.py` | 252 | 对话上下文管理 | `kairon-assistant/context_manager.py` |
| `smart_assistant/session_manager.py` | 283 | 会话管理 | `kairon-assistant/session_manager.py` |
| `smart_assistant/types.py` | 36 | 类型定义 | `kairon-assistant/types.py` |

#### L1: kaironcloud 补充 (D_Cloud)

| 源文件 | 行数 | 功能 | 目标文件 |
|--------|:--:|------|------|
| `billing/bill_generator.py` | 379 | 月度账单生成 | `kaironcloud-billing/bill_generator.py` |
| `tenant/models.py` | 274 | 租户数据模型 | `kaironcloud-billing/tenant_models.py` |

---

### Wave 2: P1 低耦合模块 (156 模块 · 目标 3-5 天)

需要移除 BaseMembrane stub、替换包路径、添加接口抽象。

#### 主要批量：

| 目标包 | 来源器官 | 模块数 | 说明 |
|--------|---------|:-----:|------|
| `engine-core` | D_Execution | ~20 | lifecycle events/governance, dispatch routing, result_bus, mapping/*, conflict/*, 14 engine workers |
| `shared-lib` | D_Governance | ~25 | execution_strategy, consensus_mechanism, governance_engine, audit_trail, xai_framework, voting, policy, risk, role/* |
| `agora` | D_Gateway | ~25 | mcp_protocol, mcp_transport, mcp_auth, oauth2_server, discovery/*, DHT系列, reputation_ledger |
| `minerva` | D_Harvest | ~20 | extractors, quality, sources, embeddings, storage, index, observability |
| `eidos` | D_Memory | ~25 | CRDT引擎, vector_backends, memory_gateway, lifecycle_engine, archiver, preference_store, pattern_miner |
| `ontoderive` | D_Logos | ~15 | document, doc_extractor, pipeline, alignment_engine, validation_steps |
| `kairon-assistant` | D_Intelligence | ~8 | smart_assistant core, recommendation_engine, system_handlers, reasoning_engine |

---

### Wave 3: P2 中耦合模块 (143 模块 · 目标 5-8 天)

需要接口解耦、依赖注入重构、事件总线替代。

#### 主要批量：

| 目标包 | 来源器官 | 模块数 | 关键挑战 |
|--------|---------|:-----:|------|
| `engine-core` | D_Execution | ~25 | lifecycle manager(991L), dispatch coordinator, result_bus, capability_matcher |
| `shared-lib` | D_Governance | ~15 | committee, auto_executor, cognitive_loop, approval, user_veto |
| `agora` | D_Gateway | ~30 | DHT federation, family_hive, ws_server, integrations, calendar_tool, mail_tool, growth/* |
| `minerva` | D_Harvest | ~13 | orchestrator, auto_indexer, harvest_scheduler, integration/* |
| `eidos` | D_Memory | ~30 | holo_memory, fact_graph, triple_store, query_engine, nks/*, cell_coordinator |
| `ontoderive` | D_Logos | ~10 | pipeline, context_compiler, auto_fix_engine, meta_validate, meta_evolve |

---

### Wave 4: P3 高耦合模块 (59 模块 · 目标 8-12 天)

需要架构级重构：事件总线替代跨organ import、接口协议定义、依赖注入容器。

#### 关键模块：

| 源文件 | 行数 | 器官 | 目标包 | 解耦策略 |
|--------|:--:|------|--------|------|
| `engine/hatcher/core.py` | 911 | D_Execution | agent-runtime | 抽IHatcher协议，依赖注入 |
| `lifecycle/manager.py` | 991 | D_Execution | agent-runtime | 拆分为生命周期hook+事件驱动 |
| `execution_scheduler.py` | 873 | D_Execution | agent-runtime | 队列抽象，Redis/Kafka后端 |
| `worker_dispatcher.py` | 748 | D_Execution | agent-runtime | 事件总线替代synchronous dispatch |
| `semantic_orchestrator.py` | 832 | D_Execution | intent-classifier | Pipeline抽象替代硬编码 |
| `knowledge_graph_engine.py` | 576 | D_Memory | eidos | 接口隔离，GraphEngine协议 |
| `unified_memory_api.py` | 679 | D_Memory | eidos | 门面模式+策略注入 |
| `cross_domain_analyzer.py` | 575 | D_Memory | eidos | 事件驱动替代ProjectPaths直调 |
| `api_gateway.py` | 461 | D_Gateway | agora | 中间件链替代5-way mixin |
| `nks_mcp_bridge.py` | 659 | D_Gateway | agora | 事件桥替代直接import |
| `_extension_market/_client.py` | 698 | D_Gateway | agora | PluginManager协议 |
| `governance_observability_bridge.py` | 377 | D_Governance | shared-lib | 可观测性事件收集器 |
| `family_hive.py` | 691 | D_Governance | shared-lib | 联邦协议+消息队列 |
| `harvest_scheduler.py` | 914 | D_Governance | shared-lib | Cron触发器抽象 |
| `evolution_metrics.py` | 371 | D_Governance | shared-lib | 自进化事件流 |

---

## 修复清单 (阻断项)

| 问题 | 文件 | 状态 |
|------|------|------|
| symphony-protocol matcher.py stub | `packages/symphony-protocol/src/symphony_protocol/matcher.py` (2行) | 入Wave1修复 |
| symphony-protocol state_machine.py stub | (2行) | 入Wave1修复 |
| symphony-protocol triggers.py stub | (0行) | 入Wave1修复 |
| D_Cloud bill_generator.py 遗漏 | (379行) | 入Wave1补充 |
| kaironcloud-billing 缺bill_generator | 源在D_Cloud/billing/bill_generator.py | 入Wave1补充 |

---

## 目标架构 (全部完成后)

```
kairon/packages/
├── core-models/          # 知识核心模型 (已有)
├── shared-lib/           # 共享库 (Wave1-3大幅扩充: governance/audit/xai/voting/cognitive)
├── engine-core/          # 引擎核心 (Wave1-3大幅扩充: +100 modules)
├── symphony-protocol/    # 舞台协议 (Wave1修复+补充)
├── llm-gateway/          # LLM网关 (已有)
├── kairon-voice/         # 语音IO (Wave1补充session manager)
├── kaironcloud-billing/  # 计费系统 (Wave1补充bill_generator)
├── kairon-assistant/     # [新] 智能助手 (Wave1-2)
├── agora/                # MCP网关 (Wave1-3大幅扩充: +70 modules)
├── minerva/              # 知识收割 (Wave1-3大幅扩充: +40 modules)
├── eidos/                # 记忆/CRDT (Wave1-3大幅扩充: +80 modules)
├── ontoderive/           # 本体推导 (Wave1-3扩充: +30 modules)
├── agent-runtime/        # Agent运行时 (Wave2-4新增: workers/hatcher/scheduler)
├── intent-classifier/    # [新] 意图分类 (Wave2-4)
├── kos/                  # 知识OS (已有)
├── metaos/               # 元OS (已有)
├── ... (其他不变)
```

---

## 验收标准 (每波)

```
Wave 1: 69 zero-coupling modules extracted, tests >= 70% coverage per module
Wave 2: 156 low-coupling modules extracted, BaseMembrane stubs removed
Wave 3: 143 medium-coupling modules extracted, cross-organ imports refactored
Wave 4: 59 high-coupling modules extracted, all SharedBrain-specific deps eliminated
Final:  make test-fast all green, ruff check clean, 0 SharedBrain organ imports
```

---

*维护: 2026-06-02 · 器官迁移主任务池 v1.0*
