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


# BET-Y3H1-T7-06: health-medical-workflow 场景冷启动 — draft→routine

## 目标

将 health-medical-workflow 驱动的 4 个 draft 场景 (archive, intake, visit-prep, visit) 冷启动推进到 routine。复用 T7-02/T7-03/T7-04/T7-05 已验证的推进模式。

## 范围

| 场景卡 | 域 | Journey | 升档前 | 升档后 |
|--------|-----|---------|--------|--------|
| scene-health-archive | work* | health-medical-workflow | draft / preview | routine / allowed |
| scene-health-intake | work* | health-medical-workflow | draft / preview | routine / allowed |
| scene-health-visit-prep | work* | health-medical-workflow | draft / preview | routine / allowed |
| scene-health-visit | work* | health-medical-workflow | draft / preview | routine / allowed |

\* health-* 场景卡 domain 字段为 work（预存数据质量问题，不阻塞推进）

## 非目标

- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不修改 health-medical-workflow journey 定义
- 不修复 domain 字段 (work → health 不在本 BET 范围)

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

Total: 4 scenes × 9 = 36 trial records

## 执行步骤

1. **draft→shadow**: 无 readiness check
2. **写 12 条 dry_run trial records**
3. **shadow→assisted**: readiness check (trial_recorded ✓)
4. **写 12 条 assisted trial records**
5. **assisted→supervised**: readiness check (trial_recorded ✓)
6. **写 12 条 supervised trial records**
7. **supervised→routine**: readiness check (trial_recorded ✓)

## 验收标准

- [ ] 4 场景卡 lifecycle = routine
- [ ] 4 场景卡 activation = allowed
- [ ] ≥ 36 条 trial records (shadow-scene-trials.jsonl)
- [ ] bet-ledger lint exit 0

## 依赖

- BET-Y3H1-T7-04 (done)
- BET-Y3H1-T7-05 (done)

## 风险

- shadow-scene-trials.jsonl gitignored → git add -f
- transition 三参数全必填
- f-string bash for loop 陷阱 → Python 生成
- health-medical-workflow journey 状态为 draft
