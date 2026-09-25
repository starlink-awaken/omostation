---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
created: 2026-09-17
bet_id: BET-Y3H1-T7-04
risk_level: L2
human_gate: true
value_indicator_policy: false
---


# BET-Y3H1-T7-04 — admin-notification-workflow 场景批量 routine 推进

## 1. 目标

将 admin-notification-workflow 驱动的 5 个 assisted 场景批量推进到 routine（经 supervised 中间态）。复用 BET-Y3H1-T7-02/T7-03 已验证的推进模式。

## 2. In scope

5 个场景卡 lifecycle 推进:
1. scene-admin-classify: assisted→supervised→routine
2. scene-admin-collect: assisted→supervised→routine
3. scene-admin-compile: assisted→supervised→routine
4. scene-admin-forward: assisted→supervised→routine
5. scene-admin-review: assisted→supervised→routine

## 3. Out of scope

- 不推进 scene-admin-inbox / scene-admin-submit（draft 级，需先 shadow→assisted）
- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不修改 admin-notification-workflow journey 定义
- 不推进非 admin-* 场景

## 4. 前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| BET-Y3H1-T7-02 done | ✅ | document-review assisted 升档完成 |
| BET-Y3H1-T7-03 done | ✅ | document-review routine 推进完成 |
| admin-notification-workflow 已验证 | ✅ | document-review 通过此 workflow E2E 3/3 |
| 5 场景卡 assisted/controlled | ✅ | 全部就绪 |

## 5. 执行路径

### Step 1: assisted → supervised (5 场景)

1. 写入 3 条新 trial records (mode=assisted) 为每个场景
2. 逐个 scene-card-lifecycle.py check + transition --tier supervised
3. 验证 5 场景全部 lifecycle=supervised, activation=monitored

### Step 2: supervised → routine (5 场景)

1. 写入 3 条新 trial records (mode=supervised) 为每个场景
2. 逐个 scene-card-lifecycle.py check + transition --tier routine
3. 验证 5 场景全部 lifecycle=routine, activation=allowed

### Step 3: Closeout

1. 更新台账 status → done
2. 补全 completion_evidence 三轴
3. 更新 retro

## 6. 风险与回退

| 风险 | 影响 | 缓解 |
|------|------|------|
| 批量推进发现问题 | 单场景回退不影响其他 | 逐个 transition，失败即停 |
| trial records 不足 | readiness 不过 | 每场景独立写入 |

## 7. 验收标准

- [ ] 5 场景卡 lifecycle = routine
- [ ] activation = allowed
- [ ] ≥ 30 条 trial records (5 场景 × 6 条)
- [ ] bet-ledger lint exit 0
