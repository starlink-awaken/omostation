---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# 方向 2+3 方案规划 (2026-08-08)

> 覆盖: ② 能力市场采购授权记录 / ③ BET 推进恢复。
> 基于两路并行调研 (admit 现状 + BET 台账真实状态)。

## 一、② 能力市场采购授权记录

### 1.1 现状 (调研确认)
- P0 定价 + P1 发现 + P2 账单 已完成
- **缺口**: `bos_capability_admit` 只做鉴权 + catalog.add + register, **零采购记录**
  (无日志/无事件/无账单; caller_id 仅用于鉴权未落痕迹)

### 1.2 实现方案 (双写)
| 步骤 | 动作 | 落点 |
|------|------|------|
| A-1 | **admit 成功路径发采购事件** `send_alert(level="info", event="capability:admitted", force=True)` | 复用 agora_alerts (EventBus + JSONL 持久化) |
| A-2 | **metadata 记 admitted_by + admitted_at** | external_connections register_capability 的 metadata 字段加双字段 |
| A-3 | (可选) QuotaChecker.record 零成本记账 | 语义混调用账单, 不推荐主方案 |

### 1.3 效果
- 采购行为可审计 (谁在何时 admit 了哪个能力)
- 采购事件入告警日志 (AGORA_ALERT_LOG) 可查询
- metadata 持久化 (admission catalog 可追溯)

## 二、③ BET 推进恢复

### 2.1 现状 (调研修正)
- **台账真实状态**: 66 总 (candidate 43 / done 23) — 非记忆的"65/4"
- Y1Q1 14/17 + Y1Q2 9/17 已完成 (治理主线已推进)
- **14 个可认领** (★ human 4 个)
- 执行机制: agent-workflow `bet-execution` workflow (preflight→implement→verify→closeout)
- `bin/plan/bet-to-task.py` **不存在** (agent-workflow 是真实路径)

### 2.2 小而准候选 (按优先级)
| BET | appetite | 理由 |
|-----|----------|------|
| **T6-05 减法配额制门禁** | 3d P0 | 依赖 T6-01/02 已 done, 纯 governance-checks 增门禁, 最准 |
| **T1-02 model-driven 判定** | 1w ★ | 纯 ADR 产出, 文档类, 需 human_gate |
| **T7-01 dogfood shadow** | 1w | 场景卡 lifecycle=shadow, 依赖已 done |
| T6-06 技能结晶 | 3d | 联动 skill_creator, 中等 |
| 避开: T5-01/T8-01 (2w+前端), T6-09 (需 aetherforge infra) |

### 2.3 推进策略
- **执行 T6-05 → T1-02 → T7-01 三连** (均 ≤1w 无 multi-week 依赖)
- 每个走 bet-execution workflow (claim → implement → verify → closeout)
- 与治理主线协同 (T6-05 依赖 T6-01/02 已完成的减法基础)

## 三、分步推进路线

| 轮次 | 动作 | 验证 |
|------|------|------|
| 1 | ② A-1/A-2 (admit 采购事件 + metadata) | admit 后告警日志含 capability:admitted + metadata 含 admitted_by |
| 2 | ③ T6-05 (减法配额制门禁) | bet-ledger verify T6-05 + gac 门禁生效 |
| 3 | ③ T1-02 (model-driven 判定 ADR) | ADR 产出 + human_gate |
| 4 | ③ T7-01 (dogfood shadow) | 场景卡 shadow 生命周期 |

## 四、风险与缓解

| 风险 | 缓解 |
|------|------|
| admit 事件防抖吞采购 | send_alert force=True 绕过 300s 防抖 |
| metadata 字段破坏 catalog | 仅加字段不改结构, 向后兼容 |
| BET 执行撞并发 | 走 bet-execution claim + D0 铁律 |
| T1-02 human_gate 阻塞 | 产出 ADR 提案, 人工确认 |

## 五、结论

- **② 采购记录**: 双写 (send_alert + metadata), 轻量补全市场闭环
- **③ BET 推进**: 台账实际 23 done (治理主线已推进), 选 T6-05/T1-02/T7-01 三连恢复节奏
- 两者可并行 (② 是 agora 改动, ③ 是主仓治理)

## 落地状态 (2026-08-08 标注)

- **② 采购记录**: ✅ admit 发 capability:admitted 事件 + admitted_by
- **③ T6-05 减法门禁**: ✅ subtraction_quota (增 1 删 1)
