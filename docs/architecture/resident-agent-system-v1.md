---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-26
title: Resident Agent System v1 (ADR-0396 DigitalAgent / WP-A~I)
type: doc
---

# Resident Agent System v1 (ADR-0396 DigitalAgent / WP-A~I)

> 文档 SSOT: 本文档是 resident 体系的**功能规格文档**（stable architecture contract）。
> 运行时事实（水位/事件数/角色投影）→ SSOT: `omo resident status`（`.omo/_delivery/resident-orchestrator/`）。
> 路由表（事件→action）→ `projects/omo/src/omo/resident/resident-routes.yaml`（schema `resident-routes/v1`）。
> MOF 元模型 → `projects/ecos/src/ecos/ssot/mof/m2/digital_agent.yaml`（DigitalAgent, ADR-0396）。
> 创建: 2026-08-23 · Owner: resident 领域

## 1. 定位

Resident Agent System（常驻智能体体系）是 eCOS 的**事件驱动常驻 agent 运行时**：
订阅 workflow-mesh 事件流，通过**规则级路由表**（WP-C）将事件分派给**五类常驻角色**
（心脏心跳/眼睛监控/大脑决策/记忆沉淀/手执行，M4.3），以**独立 projector + topic_filter**
（M4.2 领域隔离）并行推进各自水位，最终把知识沉淀到 `.omo/_knowledge/sediment/`。

生命周期里程碑：

| 里程碑 | 内容 | 落地 |
|--------|------|------|
| WP-A/D | personal-signals 输入通道 + byte-offset checkpoint 增量读取 | `omo resident signals` / daemon byte_offset 水位 |
| WP-C | rule-level subscription（YAML routes + conditions） | `resident-routes.yaml` (schema v1) |
| WP-E | alert-forwarder（observability events → channels） | `omo resident alert` |
| WP-F | decision-agent（event-driven proposals） | `omo resident decision` |
| WP-G | execution-adapter（Pi worker + 人工批准门） | `omo resident execute --yes` |
| WP-H/I | resident agent runtime（omo subpackage） | `projects/omo/src/omo/resident/` |
| M1 | daemon routing + cron scheduler | `omo resident daemon --once` + `install-resident-cron.sh` |
| M3.1 | signals 激活 cron | `CRON_SIGNALS` → `omo resident signals` |
| M4.3 | cron 角色化（五类角色独立调度） | `omo resident roles` + 每 2min 五类 daemon --once --role |
| M4.2 | 领域隔离（knowledge/system 归域） | `omo resident resources` |

## 2. 接口面

### 2.1 CLI — `omo resident <subcommand>`

```bash
uv run --directory projects/omo python -m omo.cli resident status      # 运行状态快照 (JSON)
uv run --directory projects/omo python -m omo.cli resident roles       # 五类角色配置
uv run --directory projects/omo python -m omo.cli resident daemon --once   # 单次 tick
uv run --directory projects/omo python -m omo.cli resident signals     # 个人信号输入
uv run --directory projects/omo python -m omo.cli resident inbox       # 感知文件夹轮询 (T10-15)
uv run --directory projects/omo python -m omo.cli resident decision    # 决策提案
uv run --directory projects/omo python -m omo.cli resident execute     # 执行 worker (批准门)
uv run --directory projects/omo python -m omo.cli resident alert       # 告警转发
uv run --directory projects/omo python -m omo.cli resident monitor     # 监控告警 (T10-16)
uv run --directory projects/omo python -m omo.cli resident heartbeat   # 活性台账 (T10-16)
uv run --directory projects/omo python -m omo.cli resident sediment    # 知识沉淀
uv run --directory projects/omo python -m omo.cli resident memory      # 记忆
uv run --directory projects/omo python -m omo.cli resident promote     # 场景升迁 (五问骨架, T10-17)
uv run --directory projects/omo python -m omo.cli resident resources   # 资源领域隔离
uv run --directory projects/omo python -m omo.cli resident ingest      # 事件摄入
```

兼容入口（bin/ssot wrapper）：`resident-orchestrator-daemon.py`、`decision-agent.py`、
`event-ingest-adapter.py`、`personal-signals-adapter.py`、`alert-forwarder.py`、`system-health-check.py`。

### 2.2 五类角色（M4.3, `omo resident roles`）

| 角色 | projector | 事件子集 | handler | 职责 |
|------|-----------|----------|---------|------|
| sediment 记忆沉淀 | resident-sediment | WorkflowClosed/Succeeded/PersonalSignal | knowledge_sediment | 成功 → 知识草稿 |
| decision 大脑决策 | resident-decision | WorkflowFailed/StepFailed/StepTimeout | decision_agent | 失败 → 决策提案 |
| execute 手执行 | resident-execute | ExecutionRequested/WorkPacketDispatched | execution_agent | 执行请求 → pi-worker（非 safe, 批准门）|
| monitor 眼睛监控 | resident-monitor | system.health/governance:gate_failed/alert | alert | 可观测 → 告警通道 |
| heartbeat 心脏心跳 | resident-heartbeat | heartbeat/system.alive | heartbeat | 存活心跳（预留）|

### 2.3 运行状态（`omo resident status`）

输出 `resident.status` 事件：`daemon/events/sediment/alert/ledger` 五组件 + `health`（recovered/degraded）。
- **daemon**: byte_offset 水位新鲜度（cron --once 下以水位判活性，stale 阈值 30min）
- **events**: workflow-mesh 事件流规模
- **sediment**: 知识沉淀草稿计数（runs/failures）
- **alert**: 告警转发水位
- **ledger**: event-ledger 哈希链完整性

## 3. 治理接线

| 支撑面 | 入口 | 状态 |
|--------|------|------|
| MOF 元模型 | `mof/m2/digital_agent.yaml` (DigitalAgent, extends Agent, tier=resident) | 已注册 |
| L0 约束 | `L0-constraints.yaml` CR-RESIDENT-* | 已注册 |
| Cockpit CLI | `cockpit resident status/roles/daemon` | 已接线 |
| Agora MCP | `resident_status` / `resident_roles`（`projects/agora/src/agora/server/tools_resident.py`，委派 `omo resident status/roles`） | 已接线 |
| BOS URI | `bos://resident/core/status` / `bos://resident/core/roles` / `bos://resident/daemon/once` / `bos://resident/decision/run` | 已注册 |
| Makefile | `make resident-status` / `make resident-roles` | 已添加 |

## 3.1 Agent Cell 子系统（AGE-v2, 并发推进中）

`projects/omo/src/omo/resident/` 下另有一组 **AGE-v2 Dynamic Agent Cell** 实现（2026-08-24~25 由并发 agent
合入 omo main）：`cell.py` / `cell_pool.py` / `cell_handler.py` / `cell_config.py` / `cell_state.py` /
`cell_cartridge.py` / `cell_cli.py`（CLI 入口 `omo cell`）+ `executor.py` / `planner.py` / `governor.py` /
`pdp_pep.py` / `memory_pipeline.py` / `replay.py` / `swarm_custodian.py`。

> **状态**：这些模块**不进 resident-routes 路由表**（非 resident 五类角色事件流），由
> **BET-Y1Q3-T1-12（Exact Capability Binding）** 并发推进消费接线（omo gitlink AGE-v2 主线 320d4dca）。
> 决策（2026-08-26 方向 C）：**不归档**（避免破坏并发工作）、**不提前接线**（与 T1-12 重叠），
> 待 T1-12 合流后统一评估。executor.py 的 pi-worker 后端有完整实现（非死引用）。

## 4. 运维与监控

- 守护进程由 cron 驱动（每 2min 五类 daemon `--once --role`），**无常驻进程**——以 byte_offset 水位判断活性
- 安装 cron：`bash bin/ssot/install-resident-cron.sh`（含 CRON_PROMOTE 每 10min + CRON_PROPOSAL_ADR 每天 01:00）
- 健康监控：`omo resident status`（`resident.status` 事件被 `system-health-check` 消费）
- 数据面：`runtime/omo/event-ledger.sqlite3`（哈希链）、`.omo/_knowledge/workflow-mesh/events.jsonl`（事件流）、`.omo/_knowledge/sediment/`（沉淀）、`.omo/_knowledge/retros/resident/`（五问 retro + index.md）、`.omo/_knowledge/evolution-proposals/`（决策提案）

## 5. 相关

- ADR-0396（DigitalAgent 三层生态）· ADR-0199（Unified BOS/Cockpit）· ADR-0203（需求迭代 workflow）
- 路由表 SSOT: `projects/omo/src/omo/resident/resident-routes.yaml`
- 信号源注册: `.omo/_truth/registry/signal-sources.yaml` · 连接织网: `.omo/_truth/registry/external-connection-fabric.yaml`
