---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# Wave 1 执行计划: 零耦合模块快速收获 + 阻断修复

> 2026-06-02 · 69 零耦合模块 · 目标 1-2 天完成
> 策略: 多 subagent 并行提取 → 统一测试 → 交叉验证

---

## Phase 0: 阻断修复 (15min)

### Task 0.1: 修复 symphony-protocol 3个损坏stub
- `matcher.py` (2行) ← `D_Execution/organs/symphony/agent_matcher.py` (657行)
- `state_machine.py` (2行) ← `D_Execution/organs/symphony/state_machine.py` (409行)
- `triggers.py` (0行) ← `D_Execution/organs/symphony/trigger_engine.py` (364行)
- 同时补充 `stage_manager.py` (575行) 和 `thinking_bridge.py` (147行)

### Task 0.2: 补充 kaironcloud-billing bill_generator
- `bill_generator.py` ← `D_Cloud/organs/billing/bill_generator.py` (379行)

---

## Phase 1: 并行批量提取 (8 subagent 并行)

### Batch 1: engine-core 零耦合补充 (~22 files, ~3,500 lines)
**Agent 1** — 从 D_Execution 提取零耦合模块到 engine-core:
- role_message.py, message_broker.py, lifecycle/state_machine.py
- domain_router.py, routing.py
- handlers/{agent,execution,economy,genesis,memory,tool}.py
- cost_aware_dispatcher.py, task_dependency_dag.py
- session_context_store.py, slo_scheduler.py, economy_seed.py
- mutation_validator.py, okr_framework.py, reranker.py
- goal_task_mapper.py, env_resolver.py, refinement_daemon.py
- primordial_toolkit.py, burndown_engine.py, association_engine.py
- context_injector.py, security_utils.py

### Batch 2: engine-core 零耦合补充2 (~10 files, ~1,800 lines)
**Agent 2** — 从 D_Execution 提取 worker/task/conflict 模块:
- task_context.py, worker_profile.py, worker_abstraction.py
- conflict_resolver.py, conflict_resolution.py, bidder.py, auctioneer.py
- semantic_matcher.py, semantic_index.py, arbitrator.py

### Batch 3: shared-lib 零耦合补充 (~5 files, ~1,300 lines)
**Agent 3** — 从 D_Harvest 提取 utils:
- utils/retry.py, utils/concurrent.py, utils/versioning.py
- utils/rollback.py, utils/error_handler.py

### Batch 4: agora 零耦合补充 (~8 files, ~1,700 lines)
**Agent 4** — 从 D_Gateway 提取:
- auth_models.py, connection_pool.py, api_types.py
- tools_template.py, unified_protocol_adapter.py
- umbilical_protocol.py, tool_interface_contract.py, base_tool.py

### Batch 5: ontoderive 零耦合补充 (~6 files, ~2,900 lines)
**Agent 5** — 从 D_Logos 提取:
- meta_validate_types.py, config_manager.py, authority_graph.py
- quality_probe.py, diff_analyzer.py, plugin_system.py

### Batch 6: minerva 零耦合补充 (~8 files, ~2,000 lines)
**Agent 6** — 从 D_Harvest 提取:
- monitoring/metrics.py, sources/credentials.py
- sources/lock.py, sources/priority.py
- extractors/base.py, quality/gate.py, quality/rules.py

### Batch 7: eidos 零耦合补充 (~6 files, ~600 lines)
**Agent 7** — 从 D_Memory 提取:
- core/crdt.py, core/crdt_engine.py, vector_backends/base.py
- role_memory_model.py, services/prompts.py, utils/search_utils.py

### Batch 8: kairon-assistant 新包创建 (~5 files, ~1,100 lines)
**Agent 8** — 从 D_Intelligence 创建新包:
- smart_assistant/command_parser.py, context_manager.py
- session_manager.py, types.py, core.py

---

## Phase 2: 统一验证

1. `make test-fast` 确保全部通过
2. `ruff check` 无新增告警
3. 交叉审阅每个 agent 的输出

---

## 每个 Agent 的执行规范

1. 读取源文件，去除 BaseMembrane 继承和相关导入
2. 去除 `from nucleus.Z_Microkernel...` 和跨器官导入
3. 替换为 kairon 内部包路径
4. 保持原始逻辑完整，不删减功能
5. 写测试文件验证核心功能
6. 更新 `__init__.py` 导出
