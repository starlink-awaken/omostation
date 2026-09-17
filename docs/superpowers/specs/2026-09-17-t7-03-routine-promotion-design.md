---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
bet_id: BET-Y3H1-T7-03
risk_level: L2
human_gate: true
value_indicator_policy: false
type: ssot
---

# BET-Y3H1-T7-03 — document-review routine 推进

## 1. 目标

将 document-review 场景卡从 assisted 推进到 routine（经 supervised 中间态），限定格式类公文场景。验证 assisted 阶段已验证的 document-review 能力在自动激活条件下能否稳定运行。

## 2. In scope

1. **场景卡生命周期推进**: `scene-document-review.yaml` lifecycle 从 `assisted` → `supervised` → `routine`
2. **激活升级**: activation 从 `controlled` → `monitored` → `allowed`
3. **Trial records 补充**: 至少 3 条新的 assisted 运行 trial 记录写入 `shadow-scene-trials.jsonl`
4. **Readiness 验证**: 4 前置条件 (approval_confirmed, blockers_empty, preflight_pass, trial_recorded) 全绿

## 3. Out of scope

- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不扩展到非格式类公文（如人事/合同/财务）
- 不实现新的 document-review 能力模块
- 不修改 admin-notification-workflow 场景卡

## 4. 前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| BET-Y3H1-T7-02 done | ✅ | assisted 升档已完成, lifecycle=assisted |
| calibration=0.9 ≥ 0.6 | ✅ | Phase 1 采样通过 |
| E2E 3/3 全链通过 | ✅ | Phase 2 验证通过 |
| trial records 已写入 | ✅ | 3 条 shadow-scene-trials.jsonl 条目 |
| readiness 4 前置条件 | ✅ | scene-card-lifecycle.py check 全绿 |

## 5. 执行路径

### Step 1: assisted → supervised (中间态)

1. 确认 assisted 运行稳定（连续运行无回退）
2. 写入 3 条新 trial 记录（assisted 阶段实际运行）
3. `scene-card-lifecycle.py check` 验证 4 前置条件
4. `scene-card-lifecycle.py transition --tier supervised`
5. 验证 lifecycle=supervised, activation=monitored

### Step 2: supervised → routine (终态)

1. 确认 supervised 运行稳定
2. 写入 3 条新 trial 记录（supervised 阶段实际运行）
3. `scene-card-lifecycle.py check` 验证 4 前置条件
4. `scene-card-lifecycle.py transition --tier routine`
5. 验证 lifecycle=routine, activation=allowed

### Step 3: Closeout

1. 更新台账 status → done
2. 补全 completion_evidence 三轴
3. 更新 retro
4. PR 合并

## 6. 风险与回退

| 风险 | 影响 | 缓解 |
|------|------|------|
| routine 激活后自动处理出错 | 公文格式/敏感项错误外发 | circuit_breaker: 连续 3 次 < 0.4 → 回退 supervised |
| supervised 阶段发现问题 | 需回退 assisted | 保留 assisted→supervised 回退路径 |
| 非格式类公文误入 routine | 过度放权 | 限定范围: 仅格式类公文进入 routine |

## 7. 验收标准

- [ ] document-review 场景卡 lifecycle = routine
- [ ] activation = allowed
- [ ] ≥ 6 条 trial records (3 assisted + 3 supervised)
- [ ] readiness 4 前置条件全绿
- [ ] bet-ledger lint exit 0
