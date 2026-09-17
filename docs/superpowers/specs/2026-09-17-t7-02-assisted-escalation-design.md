---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
bet_id: BET-Y3H1-T7-02
risk_level: L2
human_gate: true
value_indicator_policy: false
type: ssot
---

# BET-Y3H1-T7-02 — 公文场景 assisted 升档设计

## 1. 目标

利用 admin-notification-workflow (BET-Y1Q4-T8-04) 作为第二业务驱动，将 document-review 场景从 supervised 推进到 assisted。验证已建成的 document-review 能力在脱离国转中心借调的情况下能否稳定运行。

## 2. In scope

1. **场景卡生命周期推进**: `.omo/_truth/scenarios/v3/scene-document-review.yaml` lifecycle 从 `supervised` → `assisted`
2. **Calibration 采样**: 至少 30 次 document-review 处理，calibration ≥ 0.6，连续 30 次无 rejected
3. **端到端验证**: 至少 3 份 admin-notification-workflow 产出的公文通过 document-review 全链
4. **证据链完整**: 每份公文的 Workflow Mesh 证据链含 human_review checkpoint
5. **Skill 更新**: `scene-shadow-activate` skill 验证 lifecycle transition 路径

## 3. Out of scope

- 不复活 BET-Y3H1-T7-01 / BET-Y3H2-T7-01
- 不推进到 routine 级
- 不实现新的 document-review 能力模块
- 不修改 admin-notification-workflow 的 6 个场景卡

## 4. 前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| T7-02 调研完成 | ✅ done | 确认 admin-notification-workflow 100% 兼容 |
| Y2Q2-T7-02 场景卡 | ✅ done | 5 张 shadow 场景卡已交付 |
| Y3H1-T3-01 冷启动 | ✅ done | 新场景冷启动 < 2 周 |
| T7-07 评审校正 | ✅ done | 退回状态机 / journey 修复 |
| admin-notification 场景卡 | ✅ assisted | 6 张 assisted/controlled 运行中 |

## 5. 执行路径

### Phase 1: Calibration 采样 (Week 1)

1. 确认 mail_daemon 正常扫描上级通知邮件
2. 运行 30 次 document-review 处理 (通过 journey-runner 或 cockpit inbox)
3. 记录每次的 calibration score, success_rate, time_saved_ratio, false_positive_rate
4. 计算加权 calibration: ≥ 0.6

### Phase 2: 端到端验证 (Week 1-2)

1. 选择 3 份 admin-notification-workflow 产出的真实公文
2. 每份走完整 document-review 管线:
   - 拟稿 (draft generation)
   - 格式检查 (format_check, GB/T 9704-2012)
   - 敏感项检查 (sensitive_check)
   - 依据核验 (basis_verify)
   - 审批 (approval → decision_made)
3. 验证 Workflow Mesh 证据链完整性

### Phase 3: 生命周期推进 (Week 2)

1. 验证 calibration ≥ 0.6 且连续 30 次无 rejected
2. 执行 lifecycle transition: supervised → assisted
3. 更新场景卡 frontmatter
4. 运行 bet-ledger lint 验证

## 6. 风险与回退

| 风险 | 影响 | 缓解 |
|------|------|------|
| 格式检查/敏感项检查无独立实现 | 依赖 LLM 输出质量 | circuit_breaker: 连续 3 次 < 0.4 → 回退 supervised |
| admin-notification-workflow journey status=draft | runner 可能不触发 | 手动触发或先修 journey status |
| 真实邮件量不足 | calibration 样本不够 | 使用历史邮件回放 (replay 模式) |

## 7. 验收标准

- [ ] document-review 场景卡 lifecycle = assisted
- [ ] calibration ≥ 0.6 (加权: success_rate 0.5 + time_saved_ratio 0.3 + false_positive_rate 0.2)
- [ ] 连续 30 次无 rejected
- [ ] ≥ 3 份公文通过全链验证
- [ ] Workflow Mesh 证据链含 human_review checkpoint
- [ ] bet-ledger lint exit 0
