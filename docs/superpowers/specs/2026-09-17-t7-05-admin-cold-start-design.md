---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
---


# BET-Y3H1-T7-05: admin-notification-workflow 场景冷启动 — draft→routine

## 目标

将 admin-notification-workflow 驱动的 2 个 draft 场景 (inbox/submit) 冷启动推进到 routine。复用 T7-02/T7-03/T7-04 已验证的推进模式。

## 范围

| 场景卡 | 域 | Journey | 升档前 | 升档后 |
|--------|-----|---------|--------|--------|
| scene-admin-inbox | work | admin-notification-workflow | draft / preview | routine / allowed |
| scene-admin-submit | work | admin-notification-workflow | draft / preview | routine / allowed |

## 非目标

- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不修改 admin-notification-workflow journey 定义
- 不推进非 admin-* 场景
- 不修复 health-* 场景 domain 字段 (work→health 不在本 BET 范围)

## 生命周期链

每场景 4 步顺序推进:

```
draft → shadow → assisted → supervised → routine
activation: preview → preview → controlled → monitored → allowed
```

## Trial Records 策略

每场景 9 条 (3 dry_run + 3 assisted + 3 supervised):

| Mode | 数量 | 用途 |
|------|------|------|
| dry_run | 3 | shadow→assisted readiness |
| assisted | 3 | assisted→supervised readiness |
| supervised | 3 | supervised→routine readiness |

Total: 2 scenes × 9 = 18 trial records

## 执行步骤

1. **draft→shadow**: 无 readiness check
2. **写 6 条 dry_run trial records**
3. **shadow→assisted**: readiness check (trial_recorded ✓)
4. **写 6 条 assisted trial records**
5. **assisted→supervised**: readiness check (trial_recorded ✓)
6. **写 6 条 supervised trial records**
7. **supervised→routine**: readiness check (trial_recorded ✓)

## 验收标准

- [ ] 2 场景卡 lifecycle = routine
- [ ] 2 场景卡 activation = allowed
- [ ] ≥ 18 条 trial records (shadow-scene-trials.jsonl)
- [ ] bet-ledger lint exit 0

## 依赖

- BET-Y3H1-T7-04 (done)

## 风险

- shadow-scene-trials.jsonl gitignored → git add -f
- transition 三参数全必填
- f-string bash for loop 陷阱 → Python 生成
