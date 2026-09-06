# Scene System v3 — 场景系统全面体系化设计

> 版本：v3.0.0 | 日期：2026-09-06 | 状态：已实现

## 0. 设计原则

**不新建系统，在现有架构上"长出来"：**

| 现有系统 | 场景系统融合方式 |
|---------|----------------|
| OMO | 新增 `task_type: scene_lifecycle`，复用任务门禁模型 |
| Cockpit | `cockpit scene {execute,calibrate,promote,demote,status,list,metrics}` |
| Agora BOS | `capability_refs` 走 `bos_router.resolve()` → `resolve_bos_uri()` |
| MetaOS | 场景晋升决策 → `DecisionGate.evaluate()` |
| Runtime KEI | 场景执行在 KEI 沙箱中运行 |
| Event Bus | 场景事件走现有 Workflow Mesh JSONL |

## 1. 核心组件

### 1.1 场景卡 (Scene Card) — v3 Schema

位置：`.omo/_truth/scenarios/v3/{scene_id}.yaml`

关键字段：
- `schema: scene-card/v3` — 版本标识
- `scene_id`, `name`, `description` — 基础元数据
- `scene_class` — business | governance | infra
- `scene_type` — inbound | outbound | cycle
- `domain` — work | health | research | knowledge | governance
- `lifecycle` — draft → shadow → assisted → supervised → routine
- `activation` — preview | controlled | active | allowed
- `runtime.journey_ref` — 绑定的旅程
- `runtime.sandbox.capability_refs` — BOS URI 能力引用
- `quality.calibration` — 校准配置
- `topology.upstream/downstream` — 场景间拓扑关系
- `human_in_the_loop` — 人机协同配置

### 1.2 旅程引擎 (Journey Engine)

位置：`bin/ssot/journey-engine.py`

BOS 驱动的状态机执行引擎：
- 加载场景卡 → 找到旅程规范 → 推进状态机
- 每个状态通过 BOS URI 调用能力
- Saga 补偿链（失败时逆序回滚）
- 人机介入门控（低置信度暂停等待审批）

### 1.3 校准引擎 (Calibration Engine)

位置：`bin/ssot/calibration-engine.py`

持续信任评分，滑动窗口：
- **实时**：每次执行后更新指标
- **每日**：`cron 0 2 * * *` 综合评分 + 升级/降级检查
- **每周**：`cron 0 3 * * 1` 趋势分析 + 进化建议

### 1.4 场景图 (Scene Graph)

位置：`bin/ssot/scene-graph.py`

DAG 编排 + 事件驱动：
- 从场景卡拓扑自动构建 DAG
- 拓扑排序 + 环检测
- 6 种编排模式（顺序/路由/并行/事件/监督/交接）
- 跨场景事件通信（correlation_id 追踪链）

### 1.5 OMO 融合

- `omo scene execute/calibrate/promote/demote/status/list/validate` CLI
- `scene_execute` / `scene_calibrate` MCP 工具
- `scene-lifecycle` / `scene-execution` workflow 注册

## 2. 执行链路

```
信号源 → scene-trigger (KEI校验+MetaOS门控)
       → OMO Workflow Mesh (planned→admitted→dispatched→running→succeeded→closed)
       → journey-engine (BOS驱动+Saga补偿)
       → Agora BOS Router (bos:// URI → MCP工具)
       → outcome-recorder + calibration-engine
       → Event Bus → 下游场景
```

## 3. 场景卡生命周期

```
draft → shadow → assisted → supervised → routine
  │         │          │             │           │
  │         │          │             │           │
设计      观察       协作运行       受信运行     无人值守
不执行    只记录     人审批低置信    人拦截高风险  仅异常告警
```

升级门控：
| 升级 | 自动条件 | 必须人工 |
|------|---------|---------|
| shadow → assisted | dry_run 3次 + 无关键错误 | approver 确认 |
| assisted → supervised | 30样本 + calibration≥0.6 + fp≤0.15 | approver 确认 |
| supervised → routine | 100样本 + calibration≥0.8 + 30天稳定 | **必须双人确认** |

降级自动触发（falsifier 规则）：
- calibration < 0.6 over 30d → shadow
- fp_rate > 0.2 → 降级一级
- owner_idle > 60d → draft

## 4. 快速开始

```bash
# 列出所有场景
python3 -m omo.cli scene list

# 执行场景（dry-run）
python3 -m omo.cli scene execute scene-inbox-to-decision --dry-run

# 查看校准分数
python3 -m omo.cli scene calibrate scene-inbox-to-decision

# 验证场景卡
python3 -m omo.cli scene validate scene-inbox-to-decision

# 构建场景图
python3 bin/ssot/scene-graph.py build

# 验证旅程
python3 bin/ssot/journey-engine.py validate journey-inbox-to-decision

# 迁移旧场景卡
python3 bin/ssot/journey-engine.py migrate --all
```

## 5. 存储结构

```
.omo/_truth/scenarios/v3/        — v3 场景卡
.omo/_truth/journeys/v3/         — v3 旅程规范
.omo/_truth/registry/agent-workflows/workflows/
  ├── scene-lifecycle.yaml       — 生命周期转换工作流
  └── scene-execution.yaml       — 场景执行工作流
bin/ssot/
  ├── journey-engine.py          — 执行引擎
  ├── calibration-engine.py      — 校准引擎
  ├── scene-graph.py             — 场景图 DAG
  └── scene-card-v3-schema.json  — JSON Schema
data/scene-metrics.db            — 校准指标 (SQLite)
```

## 6. 与现有标准的对齐

| 标准 | 对齐方式 |
|------|---------|
| scene-card-lifecycle.yaml | 5级模型不变，增强 gates + falsifier |
| task-gate-model.md | scene_lifecycle 作为 task_type 复用 |
| mcp-tool-and-transport-standard.md | 遵循返回格式标准 |
| doc-ssot-contract.md | 场景卡作为 SSOT 在 _truth/ 管理 |
| SFOP/DFSQ | 场景作为"术"层能力，不新增"器" |
