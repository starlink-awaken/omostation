---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y3H1-T5-02 specification
bet_id: BET-Y3H1-T5-02
status: accepted
lifecycle: spec
owner: "@xiamingxing"
last-reviewed: 2026-09-16
---


# BET-Y3H1-T5-02 超级个体数字分身高可信 Routine 自动受托托管引擎

> 日期：2026-09-16
> 状态：accepted
> BET：BET-Y3H1-T5-02
> 版本：v1.0.0

## 背景与问题

超级个体业务操作系统（omostation）已具备信号感知、价值循环、文风适配（T3-02 LoRA 矩阵）、卫健公文全周期闭环（T7-06）等能力。然而，日常 Routine 事务（例行会议排期、常规公文回执、已知健康与财务维保）仍需要夏明星逐字修改才能通过，修订率 > 0.10，无法达到 70% 自动托管的目标。

当前缺口：
1. 缺少统一的 Routine 状态机引擎，能根据预定义规则自动执行低风险例行事务
2. 缺少熔断机制：受托执行置信度低于 0.95 时无法自动回退到人工审批
3. 缺少 T3-02 LoRA 文风适配器与 Routing 执行链的集成，导致输出风格不一致
4. 缺少可观测性：无法追踪自动托管成功率、修订率等关键指标

## 架构选择

### 核心设计：三层 Routine 托管引擎

```
┌─────────────────────────────────────────┐
│  RoutineEngine (状态机核心)              │
│  - 任务分类：meeting / doc_reply / maint  │
│  - 置信度评估：规则 + 历史修订率           │
│  - 熔断：confidence < 0.95 → HITL       │
├─────────────────────────────────────────┤
│  LoRA Adapter Layer (文风适配)           │
│  - 复用 T3-02 LoRA 矩阵                  │
│  - 按领域自动选择适配器                   │
├─────────────────────────────────────────┤
│  Observability & Circuit Breaker        │
│  - 指标采集：auto_rate, revision_rate    │
│  - 秒级熔断 + 唤醒夏明星                  │
└─────────────────────────────────────────┘
```

### 决策依据

1. **复用 T3-02 LoRA 矩阵**：避免重复造轮子，直接引用 `spine.cognitive.lora_tone`
2. **复用 T7-06 公文场景包**：Routine 公文回执逻辑继承卫健公文闭环的成熟模式
3. **状态机模式**：Routine 事务天然适合状态机（pending → executing → verifying → done/hitl）
4. **熔断优先**：高可信要求（confidence ≥ 0.95）下，宁可回退人工也不冒进

### 替代方案（未采用）

| 方案 | 未采用原因 |
|------|-----------|
| 纯 LLM 端到端判断 | 不可审计，无法保证 0.95 置信度阈值 |
| 硬编码规则引擎 | 无法适应文风变化，维护成本高 |
| 完全独立模块 | 重复 T3-02/T7-06 已有能力 |

## 验收标准

1. **RoutineEngine 模块可实例化并加载配置**
   - 验证方式：`cd projects/spine && uv run python -c "from spine.orchestration.routine_engine import RoutineEngine; e = RoutineEngine(); print('OK')"`
   - 证据类型：标准输出包含 "OK"

2. **低风险 Routine 任务（confidence ≥ 0.95）可自动执行**
   - 验证方式：`cd projects/spine && uv run pytest src/spine/orchestration/test_routine_engine.py -v`
   - 证据类型：测试全部通过

3. **低置信度任务自动触发 HITL 回退**
   - 验证方式：同上测试套件（含熔断用例）
   - 证据类型：熔断用例测试通过

4. **gac-local-gate 通过**
   - 验证方式：`make gac-local-gate`
   - 证据类型：exit 0

## 反指标

本 spec **不追求**以下指标作为成功度量：
- 100% 自动托管率（目标 70%，剩余 30% 为高风险/例外事务）
- 零人工修订（允许 ≤ 0.10 修订率为正常波动）
- 跨领域通用托管（仅覆盖 meeting / doc_reply / maint 三类 Routine）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 新建模块 vs 扩展现有 cognitive/ | 新建 orchestration/ | 职责分离：cognitive 管文风，orchestration 管执行流 |
| 2 | 置信度阈值 0.90 vs 0.95 | 0.95 | ★旗舰级 BET，高可信要求，用户明确要求 0.95 熔断 |
| 3 | 同步执行 vs 异步队列 | 同步执行（MVP） | 最小闭环先验证核心状态机，异步为后续迭代 |
| 4 | 规则引擎 vs ML 分类 | 规则引擎 + 历史统计 | 可审计、可解释，ML 分类作为后续增强 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-09-16 | v1.0.0 accepted — 初始 spec | @xiamingxing |

## 依赖

- BET-Y2Q1-T7-06（卫健公文闭环）：status=done ✅
- BET-Y2Q2-T3-02（LoRA 文风矩阵）：status=done ✅
