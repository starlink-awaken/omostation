---
schema_version: specification/v1
spec_version: 1.0.0
title: 常驻 Agent 2.0 决策因果图化与多 Agent 先例仲裁引擎设计
bet_id: BET-Y1Q4-T5-05
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
value_indicator_policy: false
---

# T5-05 — Resident 因果决策图 + 先例仲裁设计

## 1. 问题

Resident Daemon 的巡检与自愈动作只留文本日志: 决策之间无因果连线,
无法回答"这个动作由什么触发、影响了哪些下游"; 多 Agent 对同一冲突各执
先例时没有确定性仲裁; 审计导出不符合开放标准。

## 2. 非目标（与 ledger non_goals 一致）

- 不改变现有 8 阶段 Harness DAG 主控状态机。
- 不影响人类夏明星的最终一票否决权（HITL）。

## 3. 设计（确定性算法, 零模型调用）

### 3.1 因果决策图（`projects/omo/src/omo/resident/decision_bridge.py`）

- `DecisionNode`: node_id / kind(patrol|healing|decision) / actor / action /
  ts / context(引用)。
- `CausalEdge`: src→dst, relation ∈ {CAUSED, INFLUENCED}。
- `DecisionGraph`: append-only 存储 + 查询——
  `record_patrol(...)` / `record_healing(...)` 生成节点与因果连线
  （巡检节点 CAUSED 自愈节点; 自愈动作 INFLUENCED 受影响实体）;
  `ancestors(node_id)` 返回完整因果祖先链, `downstream(node_id)`
  返回下游影响面拓扑（BFS 层级）。
- 持久化: `.omo/state/decision-graph/graph.jsonl`（追加式, 每行一节点
  或一边）——Cockpit handler 与本模块以文件契约解耦, 不互相 import。

### 3.2 多 Agent 先例仲裁（`projects/omo/src/omo/resident/arbitration.py`）

- `Precedent`: signature(冲突签名) / resolution / confidence / outcome。
- `PrecedentArbiter.arbitrate(conflict, precedents)`: 按签名相似度
  检索先例, 多数一致性 + 先例置信度合成裁决置信度, 输出
  `{resolution, confidence, basis: [precedent_ids]}`。
- **circuit breaker（ledger 铁律）**: 置信度 < 0.85 → 自动升级人类待办
  (`escalate_hitl`), 严禁低置信度盲目合并; 测试显式断言。
- 仿真评测: 构造已知正确解的冲突场景集, 仲裁命中 100%。

### 3.3 Cockpit 呈现（`projects/cockpit/src/cockpit/handlers/decision_graph.py`）

纯函数聚合层（同 T7-05 scene_lifecycle 先例, 不新增路由）:
读 graph.jsonl → `decision_graph_summary()`（节点/边统计 + 指定节点的
祖先链与下游影响面）。cockpit-ui `DecisionGraphViewer.tsx` 渲染祖先链
（层级列表 + 边标签 + 影响面计数）, 配 vitest 单测。

### 3.4 W3C PROV-O 审计导出（decision_bridge 内）

`export_provo(path, fmt)`：
- `turtle`: PROV-O 核心词表（Entity/Activity/Agent + wasGeneratedBy /
  used / wasInfluencedBy）, 固定形状模板输出合法 Turtle;
- `jsonld`: 同一映射的 JSON-LD（@context 指 prov 命名空间）。

### 3.5 测试

`projects/omo/tests/unit/test_resident_causal_decision.py`：
巡检/自愈建图与连线、祖先链与下游拓扑查询、仲裁仿真评测命中 100%、
低置信 HITL 升级、PROV-O 双格式导出形状断言。
cockpit-ui `DecisionGraphViewer.test.tsx`：渲染含祖先链与影响面计数。

## 4. 完成判据映射

| done_when | 落点 |
|---|---|
| 巡检/自愈生成图原生决策节点与因果连线 | §3.1 |
| 多 Agent 先例仲裁算法 + 仿真冲突评测 | §3.2 |
| Cockpit 展示完整因果祖先链与下游影响面拓扑 | §3.3 |
| W3C PROV-O Turtle/JSON-LD 审计导出 | §3.4 |

## 5. 风险与回滚

全部为新增模块/组件 + ledger 条目; 回滚 = revert 单 PR（含双子仓 bump）。
