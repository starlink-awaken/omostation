---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-26
last_updated: 2026-08-26
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-16
type: ssot
last_updated: 2026-09-03
---

# Resident monitor/heartbeat 空转治理：角色私有 tick 接线

> 日期：2026-08-26
> 状态：accepted
> BET：BET-Y1Q3-T10-16
> 上游：resident 体系价值兑现优化轮（T6-14 复盘「接线完整、价值未兑现」后四项之一）
> 方向：Task #51 下一里程碑（用户选定「E monitor/heartbeat 空转治理」）

## 背景与问题

resident 五类角色（roles.py）中 sediment/decision/execute 已完整接线（handler 注册 + 规则路由 +
事件源），但 **monitor（眼睛）/ heartbeat（心脏）每 2min 纯空转**。三缺口叠加（代码实证）：

1. **注册缺口**：`daemon.py:_register_default_handlers()` 只注册 sediment/decision/execute 三元组。
   `alert.py` 是独立 CLI（无 `register_with_daemon` 契约），heartbeat 无模块 → monitor/heartbeat
   角色事件全部落 `_handler_placeholder`（仅日志）。
2. **路由缺口**：`resident-routes.yaml` 仅 15 条规则，action 全为
   `knowledge_sediment`/`decision_agent`/`execution_agent`；无 `alert`/`system.alive`/
   `system.health`/`governance:gate_failed` 事件类型规则。
3. **事件源缺口**：daemon 只读统一事件流 `.omo/_knowledge/workflow-mesh/events.jsonl`，其中无
   monitor/heartbeat 相关事件类型；observability 平面（456 条：258 critical/4 degraded/2 recovered）
   在独立文件 `.omo/_delivery/observability/events.jsonl`，从未进入事件流。

叠加效果：cron 每 2min 调五角色 daemon --once，monitor/heartbeat 因无 handler + 无规则 + 无事件
→ 全部落 placeholder 空转；alert cron 走 `--dry-run`（不推进水位、不真实外发）。

## 目标

把 monitor/heartbeat 从「被动路由空转」升级为「**角色私有 tick（publish → 路由 → 处理）**」，
完全复用 T10-15 inbox.py 的成熟模式（外部数据源 → 统一事件流 → daemon 按 routes 路由 → handler）：

1. **`omo.resident.heartbeat`（新建）**：`register_with_daemon` 注册 `heartbeat` handler（safe）；
   `publish_heartbeat()` 调 `status.snapshot()` 生成 `system.alive` 事件 → 追加统一事件流 →
   daemon heartbeat 角色下一 tick 路由 → 沉淀 `.omo/state/resident-heartbeat.jsonl`（活性台账）。
2. **`omo.resident.monitor`（新建）**：`register_with_daemon` 注册 `alert` handler（safe）；
   `publish_monitor()` 增量读 observability 平面（复用 alert.py 水位/读取逻辑）→
   severity∈{critical,degraded} → 生成 `alert` 事件 → 追加统一事件流 → daemon monitor 角色
   下一 tick 路由 → 调 alert-connectors deliver 外发（复用 T10-14 alert.py 交付）。
3. **`daemon.py`**：`_register_default_handlers` 增补两个模块；`run_daemon` 加 per-role publish
   hook（tick_once **之后** publish → 本 tick 消费上一 tick 发布、本 tick 发布下一 tick 消费，
   天然形成 2min 节律）。
4. **`resident-routes.yaml`**：新增 `alert`→alert、`system.alive`→heartbeat 两条规则（safe: true）。
5. **cron 收敛**：告警外发唯一路径 = daemon monitor 角色；`CRON_ALERT`（--dry-run）从 cron 移除，
   alert.py CLI 保留供手动/测试。
6. **真实外发挂账**：deliver 到 wecom/slack 依赖 `ALERT_WECOM_WEBHOOK`（T10-14 第 5 条挂账点），
   本次「先只接线不配 URL」——monitor 接线 + deliver 代码路径 + fail-closed 验证，外发激活待
   用户提供 webhook 后一键启用。

## 设计

### omo 侧（`projects/omo/src/omo/resident/`）

**`heartbeat.py`（新建）**：
- `register_with_daemon(daemon_module)`：`daemon_module.register_handler("heartbeat", _heartbeat_handler, safe=True)`
- `_heartbeat_handler(event)`：把 system.alive 事件追加到 `.omo/state/resident-heartbeat.jsonl`
  （活性台账：ts/health/degraded_components/event_id）
- `publish_heartbeat()`：调 `status.snapshot()` → 构造 `system.alive` 事件
  （payload 带 health/degraded_components/components 摘要）→ `_append_to_events_jsonl`

**`monitor.py`（新建）**：
- `register_with_daemon(daemon_module)`：`daemon_module.register_handler("alert", _alert_handler, safe=True)`
- `_alert_handler(event)`：调 `alert.py` deliver 逻辑（复用 alert-connectors）外发 + 沉淀告警记录
- `publish_monitor()`：增量读 observability（复用 alert.py `_load_byte_offset`/`_read_incremental`/
  `ALERT_SEVERITIES`）→ severity∈{critical,degraded} 事件 → 构造 `alert` 事件
  （payload 带原始事件 id/type/severity/title/body）→ `_append_to_events_jsonl` → 推进水位

**`daemon.py`**：
- `_register_default_handlers()` 增补 `("omo.resident.monitor", "alert")` + `("omo.resident.heartbeat", "heartbeat")`
- `run_daemon()` 加 per-role publish hook：projector ∈ {resident-monitor, resident-heartbeat} 时
  tick_once 后调用对应 publish（依赖注入函数名，避免循环 import）

**`resident-routes.yaml`**：新增 2 条规则（event_type → action，safe: true）
- `alert` → `alert`（topic `mesh:observability:alert`）
- `system.alive` → `heartbeat`（topic `mesh:system:alive`）

**`roles.py`**：monitor/heartbeat 的 topic_filter 已含 `alert`/`system.alive`（无需改），
desc 更新（heartbeat 去「预留」标注）

**`cli.py`**：SUBCOMMANDS 已含 alert（T10-14）；新增 heartbeat/monitor 子命令（供手动 publish 调试）

### 主仓侧

**`bin/ssot/install-resident-cron.sh`**：移除 `CRON_ALERT`（--dry-run 空转），monitor/heartbeat
角色 cron 已覆盖 observability 消费

**测试**（仿 test_resident_signals.py 全链模式）：
- `test_resident_heartbeat.py`：publish → events.jsonl 出现 system.alive → daemon --role heartbeat
  路由 → resident-heartbeat.jsonl 沉淀（幂等）
- `test_resident_monitor.py`：publish（observability fixture critical/degraded）→ events.jsonl 出现
  alert → daemon --role monitor 路由 → deliver 调用（mock alert-connectors）
- `test_resident_roles.py`：monitor/heartbeat 角色 topic_filter 覆盖新事件类型

## 非目标

- 不配置 `ALERT_WECOM_WEBHOOK`（T10-14 第 5 条挂账点，用户决策「先只接线不配 URL」）
- 不接 alert-handler.py（OBS-02 governance-alerts 主动引擎，独立体系，后续评估）
- 不实现 monitor 对 governance:gate_failed 的主动探测（observability 有事件才转发）
- 不改 signal-poller.py / status.py 既有逻辑

## 验收

- [x] `heartbeat.publish_heartbeat` 实跑 → events.jsonl 出现 system.alive → `daemon --role heartbeat`
      → `.omo/state/resident-heartbeat.jsonl` 活性台账追加（幂等）
- [x] `monitor.publish_monitor` 实跑 → observability critical/degraded → events.jsonl 出现 alert →
      `daemon --role monitor` 路由 → deliver 调用（alert-connectors 契约，fail-closed）
- [x] `daemon --once --role monitor/heartbeat` 不再落 placeholder（cron-*.log 无 handler_placeholder）
- [x] `install-resident-cron.sh` 移除 CRON_ALERT，五角色循环覆盖 monitor/heartbeat 真实 tick
- [x] omo 单测 + 集成测试全绿；主仓 gac-local-gate 通过
