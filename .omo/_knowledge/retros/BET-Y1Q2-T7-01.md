# BET-Y1Q2-T7-01 Retrospective — 工程交付 dogfood 开 shadow

> 完成日期: 2026-08-08  
> 状态: done  
> 耗时: < 1 day

## 目标

建立高频低风险的 decision_outcome 样本源，PR 评审意见即天然 human_verdict。

## 交付物

1. **Scene Card 更新** (`docs/scene-cards/engineering-delivery-dogfood.yaml`)
   - lifecycle: active → shadow
   - bet reference: BET-Y1Q1-T7-01 → BET-Y1Q2-T7-01
   - 明确标注"本场景产出永不计入 X3 价值指标"
   - 目标: 每周 >= 20 条 decision_outcome

2. **验证通过**
   - `grep -c 'lifecycle: shadow' docs/scene-cards/engineering-delivery-dogfood.yaml` → 1

## 技术决策

### 1. Shadow 模式语义
**决策**: lifecycle=shadow 表示观察模式，无业务副作用  
**理由**:
- 仅记录 decision_outcome，不触发实际执行
- PR 评审意见作为天然 human_verdict
- 为 capability_calibration 提供样本数据

### 2. 价值指标排除
**决策**: 明确标注不计入 X3 价值指标  
**理由**:
- Shadow 是观察阶段，产出质量未验证
- 避免污染价值指标基线
- 未来晋升 active 后重新评估

### 3. 样本目标
**决策**: 每周 >= 20 条 decision_outcome  
**理由**:
- 足够支撑 capability_calibration 统计显著性
- 与 PR 评审频率匹配（~4 PR/天 × 5 天）
- circuit_breaker: < 10/周 → 扩大到 commit 级评审

## 验证结果

```bash
$ grep -c 'lifecycle: shadow' docs/scene-cards/engineering-delivery-dogfood.yaml
1
```

**关键验证点**:
- ✅ engineering-delivery 场景 lifecycle=shadow
- ✅ 明确标注"本场景产出永不计入价值指标"
- ✅ bet reference 更新为 BET-Y1Q2-T7-01

## 依赖关系

- **前置依赖** (已 done):
  - BET-Y1Q1-T7-01: scene card draft→shadow 生命周期
  - BET-Y1Q1-T3-02: MOS decision_outcome 记录

- **后续依赖** (待执行):
  - BET-Y1Q2-T4-01: capability_calibration 自动更新 (已完成)
  - BET-Y1Q2-T8-01: /outcomes 结果与校准面板

## 教训与模式

### 1. Shadow 模式作为安全观察窗口
**模式**: lifecycle=shadow 允许无副作用观察  
**应用**: 新场景、新能力的首次上线  
**教训**: shadow 是必经阶段，不跳过直接 active

### 2. 价值指标守门
**模式**: 明确标注 non-goal 避免污染  
**应用**: 实验性产出、dogfood 阶段  
**教训**: 价值指标需要纯净数据源，实验产出需隔离

## 治理合规

- ✅ Scene card 更新: lifecycle=shadow
- ✅ Bet ledger 更新: status=done
- ✅ Retro document: light retro
- ✅ 验证命令: grep 通过

## 后续工作

1. **样本收集**: 每周检查 decision_outcome 数量
   - 目标: >= 20 条/周
   - circuit_breaker: < 10/周 → 扩大范围

2. **Calibration 观察**: 通过 T4-01 闭环观察 calibration 变化
   - 预期: 初期 calibration 波动大，逐步稳定
   - 目标: 8 周后 calibration 稳定在 0.6-0.8

3. **晋升评估**: 8 周后评估是否晋升 active
   - 条件: calibration 稳定 + 样本充足 + 无重大回退
   - 晋升后: 重新评估是否计入 X3 价值指标

## 结论

BET-Y1Q2-T7-01 成功开启 engineering-delivery shadow 模式，为 capability_calibration 提供高频低风险样本源。架构治理合规，验证通过。
