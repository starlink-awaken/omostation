---
slug: omni-bus-phased-program
status: awaiting-approval
intent: clear
approach: phased-program
---

# Draft: omni-bus-phased-program

## Components (topology ledger)

| ID | Component | Path | Phase |
|----|-----------|------|-------|
| C1 | c2g knowledge publisher (producer) | projects/c2g/src/c2g/knowledge_publisher.py | P1 |
| C2 | cockpit knowledge indexer (consumer) | projects/cockpit/src/cockpit/web/knowledge_indexer.py | P1 (verification target, no change) |
| C3 | kairon-pipeline bus adapter | projects/kairon/packages/kairon-pipeline/src/kairon_pipeline/bus_adapter.py | P2 |
| C4 | bus-foundation event plane | projects/bus-foundation/src/bus_foundation/ | P2 base / P4 extension |
| C5 | bin/ root scripts + README | bin/*.py, bin/README.md | P3 |
| C6 | bin/gac/ subdirectory (already landed) | bin/gac/ | P3 (reference) |

## Open assumptions

1. 用户批准本 plan 后，执行由独立 worker 会话（`$start-work`）完成；本会话只产出计划。
2. P1 的消费者（C2）已双通道接受 canonical+legacy，无需改动；仅翻转 producer。
3. P2 保持 kairon-pipeline 零运行时依赖（bus-foundation 仅 dev 组）。
4. P3 的 gac 子目录化已落地（bin/gac/ 100+ 文件），本阶段只做 README 对齐 + 根级归类。
5. P4 只交付 bus-foundation Data/Control 平面的契约接口 + 最小实现，不做完整语义。

## Findings (cited)

- F1. `projects/c2g/src/c2g/knowledge_publisher.py` (~200L): Strategy1 = Agora `/v1/tools/call publish_event`，`event_type=bos://brain/events/card_updated`（legacy 通道）；Strategy2 = 降级 Cockpit HTTP `/api/knowledge/put`；离线降级 `degraded_offline` 不阻塞；两个发布函数 `publish_outcome_card` / `publish_predictive_card`；`AGORA_HTTP_ENDPOINT` 默认 127.0.0.1:7422。
- F2. `projects/c2g/tests/test_knowledge_publisher.py:74` 断言 legacy `event_type` —— P1 必须同步更新该断言。
- F3. `projects/cockpit/src/cockpit/web/knowledge_indexer.py`: callback 双通道接受 `{bos://memory/events/card_updated, bos://brain/events/card_updated}`（L71-74）；订阅双 pattern 含 legacy（L138-141）；非阻塞启动 + 5min keepalive + 5×指数退避重试；KOS HTTP PUT 优先、LanceDB 进程内降级；Agora 不可用不丢卡（文件已持久化）→ **P1 迁移安全网已确认：consumer 双接受，翻转 producer 不丢事件**。
- F4. `.omo/_knowledge/decisions/0372-memory-os-control-plane.md` §D: legacy→canonical 迁移规则 = 生产发新 URI + consumer 双接受 → 再删旧；release 须双 pattern 兼容。
- F5. `.omo/_knowledge/decisions/0296-c2g-predictive-outcomes-to-knowledge-graph.md`（Phase C 发布器来源）；`0294-knowledge-gateway-decoupling-and-event-pipeline.md`。
- F6. `projects/kairon/packages/kairon-pipeline/src/kairon_pipeline/bus_adapter.py` (~100L): D-Harvest 事件桥接；lazy import `bus_foundation.facade.event`；`emit_event` → `bus_event.publish(topic, payload, source_uri=bos://capability/pipeline/{source}, trace_id)`；publish 失败仅 log warning + return None（失败被吞）；事件类型: `kairon:source:ingested` / `kairon:extraction:completed` / `kairon:quality_gate:result` / `kairon:downstream:dispatched`；pipeline 零运行时依赖。
- F7. `projects/kairon/packages/kairon-pipeline/pyproject.toml`: `dependencies=[]`；bus-foundation 仅在 `[dependency-groups].dev`（path `../../../bus-foundation`）；`requires-python>=3.10`；version 0.4.0 → **P2 必须保留零运行时依赖设计**。
- F8. `projects/kairon/packages/kairon-pipeline/tests/test_bus_adapter.py`: `test_emit_source_ingested_dispatches_envelope`(:23-38)、`test_publish_failure_does_not_propagate`(:87-99)。
- F9. `bin/README.md` L156-178: README 本身即"子目录化低成本试验"；触发指标 = 脚本总数>100（当前 75）、README 域表行>200（~90）、单域>12（gac=15 ✅）、找不着>2/月；状态行称"阶段1 理域边界，阶段2 触发后再子目录化"。
- F10. `bin/gac/*.py` = 100+ 文件（glob 100 截断）—— **gac 子目录化已落地**，README 状态行（"总数 75 / gac=15"）已过期。
- F11. 根级 `bin/*.py` = 14 文件：submodule-gitlink-check.py、submodule-reachability-gate.py、ssot-watcher.py、migrate-port-env-var.py、layer-dependency-check.py、git-health-hook.py、cross_package_api_map.py、compass_radar.py、commit-assist.py、cockpit-readiness.py、agent-workflow.py（1319L，framework 入口）、classify_planned.py、check_health_ssot.py、change-lane-check.py。
- F12. `projects/bus-foundation/src/bus_foundation/` 13 模块：metrics_server/observability/topics/metrics/dlq_admin/__init__/envelope/schema/dlq_redaction/metrics_instrumentation/retry/dlq/router —— **全部为 event 平面，无 data/control 平面模块（P4 缺口实锤）**。
- F13. `projects/cockpit/src/cockpit/commands/bus.py` (~74L): Omni-Bus 入口 `cmd_bus`: status/topics/publish/metrics 四子命令；lazy import bus-foundation + facade.event + topics；ImportError → 红字报错 rc1；publish → `event_plane.publish(topic, data)`；metrics → `bus_foundation.metrics_snapshot()`。

## Decisions

- D1. 阶段顺序 P1→P2→P3→P4（爆炸半径递增；P1 独立小赢，P4 最大）。
- D2. P1 按 ADR-0372 §D：c2g producer 改为 emit canonical `bos://memory/events/card_updated`；consumer 已双接受，无需改动；同步更新测试断言；保留降级路径。
- D3. P2 保留零运行时依赖：bus-foundation 维持 dev-only；强化 = 失败可观测性（结构化 warn 携带 trace_id/topic + metrics 失败计数），不加重试/队列（事件丢失按设计可接受，下游可重建）。
- D4. P3 = 对齐 `bin/README.md` 域表与 bin/ 实际结构（gac 已子目录化、100+ 文件），根级 14 脚本归类到域，framework 入口（agent-workflow.py 等）保留根级，更新触发指标为实际值。
- D5. P4 = bus-foundation 新增 Data 平面（pull/query 契约）与 Control 平面（命令/管理契约）模块，沿用 event 平面模式（facade + envelope/schema + 最小实现 + 测试），并扩展 `cmd_bus` 子命令；保持 event 平面向后兼容。

## Scope IN

- P1: c2g knowledge_publisher 通道迁移 + 测试断言更新。
- P2: bus_adapter 失败可观测性（trace_id/topic 结构化日志 + metrics 计数）+ 测试。
- P3: bin/README.md 域表对齐 + 根级脚本归类 + 触发指标更新。
- P4: bus-foundation data/control 平面契约 + 最小实现 + cmd_bus 接线 + 测试。

## Scope OUT

- 不修改 agora bus 内部实现（仅经 bus-foundation facade 使用）。
- 不删除 legacy consumer 双接受（P1 仅翻转 producer；legacy 通道删除属 ADR-0372 后续工作）。
- P2 不加运行时依赖、不加重试/队列基础设施。
- P3 不动 bin/gac/ 既有 100+ 文件（已就位），仅 README + 根级归类。
- P4 只做契约 + 最小实现，不做完整 data/control 平面语义。
- 本计划不包含任何治理 workflow 运行（执行属 worker 会话）。

## Open questions

无阻塞性问题：主题已由用户决议（全部四项、分阶段）；测试策略默认 tests-after + 强制 QA 波（见审批简报）；P4 范围默认契约+最小实现。

## Approval gate

- 状态: `drafting` → **`awaiting-approval`**
- 等待用户显式 okay 后，将产出 `.omo/plans/omni-bus-phased-program.md` 完整计划（TL;DR / Scope / Verification strategy / Execution strategy / Todos 5-8 条 / Final verification wave F1-F4 / Commit strategy / Success criteria）。
- 批准只授权写计划，不授权实现。
