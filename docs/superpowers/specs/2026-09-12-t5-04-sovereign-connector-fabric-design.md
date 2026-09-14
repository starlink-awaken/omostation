---
schema_version: specification/v1
spec_version: 1.0.0
title: 主权连接器架构升级与 Kairon/Iris 外部数据源统一 BOS 网关化设计
bet_id: BET-Y1Q4-T5-04
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T5-04 — Sovereign Connector Fabric & 统一 BOS 网关设计

## 1. 问题

外部数据源接入点散落各处（spine 解析器、agora tools_bos 七个模块、
daemon、documents 域、kairon/gbrain/aetherforge/omlxc 服务面），无统一
登记：连接器发现靠口口相传，同步水位（watermark）无统一状态,
单连接器故障对调度的影响未建模。Resident Daemon 无连接器周期拉取入口。

## 2. 非目标（与 ledger non_goals 一致）

- 不重写各连接器底层协议解析（spine parsers / tools_bos 保持原样）。
- 不破坏 Kairon 现有离线批处理能力。

## 3. 设计

### 3.1 连接器清单（`.omo/_truth/registry/connector-manifest.yaml`）

`schema: connector-manifest/v1`。每个连接器一条元数据：

```
id / kind(ingress|knowledge|compute|documents) / uri / owner_project /
artifact(仓库内真实工件路径, 注册时核验存在) / watermark_key(可空) /
poll_interval_s(可空=事件驱动) / status(active) / description
```

首期登记 15 个有真实工件支撑的连接器：email、calendar、mail-draft、
inbox、im、voice、ocr、bdsk、spine-lecp、documents、kairon-graph、
web-reader、gbrain、aetherforge、omlxc。schema 允许后续增长,
`total_registered` 字段显式记录数量。

### 3.2 BOS 网关 facade（`projects/agora/src/agora/server/tools_connectors.py`）

- `connector_list(kind=None, status=None)`：加载 manifest, 过滤返回。
- `connector_sync(connector_id, watermark=None)`：对可轮询连接器记录
  同步事件并推进 watermark（状态文件 `.omo/state/connectors/watermarks.yaml`,
  原子写）; 不可轮询（watermark_key 空）返回 `not_pollable` 诚实失败。
- `bos-services.yaml` 注册 `bos://connectors/list` 与
  `bos://connectors/sync` 两条路由（MCP 工具 connector_list /
  connector_sync 经既有 registration 机制暴露）。

### 3.3 Resident 周期拉取（`projects/omo/src/omo/resident/connectors_poll.py`）

- `ConnectorPoller(schedule, fetch_fn, state_path)`：按 manifest 的
  poll_interval_s 调度; watermark 增量（上次成功水位 → 本次拉取）。
- **circuit breaker（ledger 铁律）**：单连接器拉取失败 → 记录失败计数 +
  降级跳过, 绝不阻断其他连接器调度（per-connector try/except 隔离,
  测试显式断言）。
- fetch_fn 注入式（daemon 接线时提供具体适配器; 模块本身零网络依赖,
  纯调度/水位/隔离逻辑）。

### 3.4 测试

- `projects/agora/tests/test_connectors_bos.py`：manifest 完整性
  （15 条、artifact 路径真实存在、schema 键全）、connector_list 过滤、
  connector_sync 水位推进与 not_pollable 诚实失败、bos-services 路由在册。
- `projects/omo/tests/unit/test_connectors_poll.py`：多连接器隔离
  （1 个失败不阻断其余）、watermark 增量推进、事件发射、降级跳过。

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| connector-manifest.yaml 登记 15+ 种 | §3.1（15 条, artifact 全核验） |
| bos://connectors/* 路由 + connector_list/sync MCP 工具 | §3.2 |
| Resident Daemon connector-fetch 周期任务（watermark 增量） | §3.3 |
| 单测覆盖发现/BOS 网关调用/增量事件发射 | §3.4 |

## 5. 风险与回滚

- manifest 为新增数据文件; facade/poller 为新增模块; 回滚 = revert 单 PR。
- 轮询默认不启用（daemon 接线为显式后续步骤）, 无运行时行为变更。
