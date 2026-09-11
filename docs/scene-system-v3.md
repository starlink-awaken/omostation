---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-11
---
# Scene System v3 — 场景系统全面体系化设计

> 版本：v3.2.0 | 日期：2026-09-11 | 状态：全链路落地
> 9 轮迭代 · 15+ PR · #3348 → #3592

## 0. 设计原则

**不新建系统，在现有架构上"长出来"：**

| 现有系统 | 场景系统融合方式 |
|---------|----------------|
| OMO | `omo scene` CLI + `scene_execute`/`scene_calibrate` MCP 工具 |
| Cockpit | `cockpit scene` CLI + `/api/scene-lifecycle/*` (9 端点) + 4 前端页面 |
| Agora BOS | `capability_refs` → `bos_router.resolve()` → MCP 工具 |
| MetaOS | 场景晋升决策 → `DecisionGate.evaluate()`；异常 → `ImmuneMonitor` |
| Runtime KEI | 场景执行在 KEI 沙箱中运行 |
| Event Bus | 场景事件走 Workflow Mesh + observability-events (告警面) |
| North Star | scene-outcome → Outcome.Human.v1 → event-ledger |

## 1. 核心组件

### 1.1 场景卡 (Scene Card) — v3 Schema

位置：`.omo/_truth/scenarios/v3/{scene_id}.yaml`

- `schema: scene-card/v3` — 版本标识
- `scene_id` — 必须匹配 `^scene-[a-z0-9-]+$`
- `lifecycle` — draft → shadow → assisted → supervised → routine
- `triggers` — 信号/定时/webhook/条件/手动 5 种
- `runtime.sandbox.capabilities` — BOS URI 能力引用
- `topology.upstream/downstream` — 场景间拓扑关系
- `quality.falsifier` — 降级规则

### 1.2 旅程引擎 (Journey Engine)

`bin/ssot/journey-engine.py`

- BOS URI 驱动的状态机执行
- Saga 补偿链（失败时逆序回滚）
- human_gate 人机介入门控
- 信号源触发（iris 邮件连接器轮询）
- 告警发射（escalated → critical → feishu/钉钉）
- BOS 真实调用（KOS search/ingest、LLM generate、scene-to-scene）

### 1.3 校准引擎 (Calibration Engine)

`bin/ssot/calibration-engine.py`

- 滑动窗口信任评分（30d SQLite WAL）
- 三周期：实时 / 每日 cron / 每周
- 升级/降级门控自动检查
- LLM 成本追踪（token_usage → llm_cost.jsonl，X3/K1）

### 1.4 场景图 (Scene Graph)

`bin/ssot/scene-graph.py`

- DAG 编排 + 完整 DFS 遍历
- 环检测 + 拓扑排序
- 事件驱动场景间通信（correlation_id）
- 并行执行（ThreadPoolExecutor）

### 1.5 防腐层 (Guardrail)

`bin/ssot/scene-v3-guardrail.py`

- Schema 校验 + lifecycle 一致性 + BOS 可达性
- cron `scene-guardrail-daily` (06:30)
- strict 模式 67/67 PASS

### 1.6 信号轮询器 (Signal Poller)

`bin/ssot/scene-signal-poller.py`

- 轮询 iris 连接器（netease_mailmaster + apple_mail）
- 水印去重（per scene+connector）
- 按 lifecycle 分级调度（assisted+ live, shadow dry-run）
- cron `scene-signal-poll` (工作日 9-18 点每 15 分钟)

### 1.7 人类裁决流

- escalated 场景 → 钉钉/飞书通知 → cockpit UI Accept/Reject
- `POST /api/scene-lifecycle/adjudicate` → scene-outcome-recorder
- 信任回路（MOSBeliefManager）+ 价值证据（value-evidence）+ North Star（Outcome.Human.v1）

## 2. 执行链路

```
信号轮询 (iris/邮件) → scene-signal-poller (水印去重)
  → journey-engine (BOS 驱动 + Saga 补偿 + human_gate)
    → escalated → 钉钉/飞书通知 (critical)
    → operator Accept/Reject (cockpit UI)
      → scene-outcome-recorder
        ├→ scene-outcomes.jsonl (信任回路 + BRIEF X3 行)
        ├→ value-evidence.jsonl (X3 价值)
        ├→ Outcome.Human.v1 → event-ledger (North Star)
        └→ MOSBeliefManager (能力校准)
  → llm_cost.jsonl (token_usage → X3/K1 成本追踪)
```

## 3. 场景卡生命周期

```
draft → shadow → assisted → supervised → routine
设计     观察     协作运行     受信运行     无人值守
```

| 升级 | 自动条件 | 必须人工 |
|------|---------|---------|
| shadow → assisted | dry_run 3次 + 无关键错误 | approver 确认 |
| assisted → supervised | 30样本 + calibration≥0.6 + fp≤0.15 | approver 确认 |
| supervised → routine | 100样本 + calibration≥0.8 + 30天稳定 | **双人确认** |

## 4. 快速开始

### OMO CLI

```bash
PYTHONPATH=projects/omo/src python3 -m omo.cli scene list
PYTHONPATH=projects/omo/src python3 -m omo.cli scene execute scene-inbox-to-decision --dry-run
PYTHONPATH=projects/omo/src python3 -m omo.cli scene calibrate scene-inbox-to-decision
PYTHONPATH=projects/omo/src python3 -m omo.cli scene promote scene-inbox-to-decision --to supervised
```

### Cockpit CLI

```bash
cockpit scene lifecycle list
cockpit scene execute scene-inbox-to-decision --dry-run
cockpit scene calibrate scene-inbox-to-decision
cockpit scene graph
cockpit scene lifecycle status --scene-id scene-inbox-to-decision
```

### 信号轮询

```bash
python3 bin/ssot/scene-signal-poller.py poll
python3 bin/ssot/scene-signal-poller.py status
# cron: */15 9-18 * * 1-5
```

### 防腐校验

```bash
python3 bin/ssot/scene-v3-guardrail.py validate-all --allow-forward-refs
```

## 5. Cockpit Web API

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/scene-lifecycle/list` | 列出所有场景 |
| GET | `/api/scene-lifecycle/status/{scene_id}` | 场景详情 |
| POST | `/api/scene-lifecycle/execute` | 执行场景 |
| POST | `/api/scene-lifecycle/promote` | 晋升场景 |
| POST | `/api/scene-lifecycle/demote` | 降级场景 |
| GET | `/api/scene-lifecycle/graph` | 场景图 |
| GET | `/api/scene-lifecycle/metrics/{scene_id}` | 校准指标 |
| GET | `/api/scene-lifecycle/escalations` | 升级队列（待裁决） |
| POST | `/api/scene-lifecycle/adjudicate` | 人工裁决 |

### 前端页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 场景总览 | `/scenes` | 卡片网格 + 生命周期分布 + 升级横幅 |
| 场景详情 | `/scenes/{id}` | 校准曲线 + 裁决面板 + 操作 |
| 场景图 | `/scene-graph` | DAG 拓扑可视化 |
| 校准中心 | `/calibration` | 分数表格 + 升级队列 |

## 6. 存储结构

```
.omo/_truth/scenarios/v3/        — v3 场景卡 (67 张)
.omo/_truth/journeys/v3/         — v3 旅程规范 (58 个)
.omo/_truth/registry/agent-workflows/workflows/
  ├── scene-lifecycle.yaml       — 生命周期转换工作流
  └── scene-execution.yaml       — 场景执行工作流
bin/ssot/
  ├── journey-engine.py          — 执行引擎
  ├── calibration-engine.py      — 校准引擎
  ├── scene-graph.py             — 场景图 DAG
  ├── scene-v3-guardrail.py      — 防腐层
  ├── scene-signal-poller.py     — 信号轮询器
  ├── scene-v3-registry.py       — 注册表生成
  ├── scene-batch-execute.py     — 批量执行
  ├── scene-journey-autogen.py   — 旅程自动生成
  └── scene-card-v3-schema.json  — JSON Schema
data/scene-metrics.db            — 校准指标 (SQLite)
~/runtime/data/llm_cost.jsonl    — LLM 成本 (X3/K1)
.omo/_delivery/ingress/value-evidence.jsonl — 价值证据
.omo/_delivery/observability/events.jsonl   — 告警事件面
runtime/omo/event-ledger.sqlite3 — North Star 事件账本
```

## 7. cron 任务

| 任务 | 周期 | 状态 |
|------|------|------|
| scene-signal-poll | 工作日 9-18 点每 15 分钟 | proposed |
| scene-guardrail-daily | 每日 06:30 | proposed |
| scene-calibration-weekly | 每周一 06:00 | proposed |
| scene-registry-sync-daily | 每日 06:15 | proposed |

> 注：所有 cron 当前为 `proposed` 状态。启用需人工确认并安装到真实 crontab。

## 8. 与现有标准的对齐

| 标准 | 对齐方式 |
|------|---------|
| scene-card-lifecycle.yaml | 5级模型不变，增强 gates + falsifier |
| task-gate-model.md | scene_lifecycle 作为 task_type 复用 |
| mcp-tool-and-transport-standard.md | 遵循返回格式标准 |
| doc-ssot-contract.md | 场景卡作为 SSOT 在 _truth/ 管理 |
| SFOP/DFSQ | 场景作为"术"层能力，不新增"器" |
| x-axis-registry.yaml | X3/K1 (llm_cost) + X3 工作交付 (scene-outcomes) |
