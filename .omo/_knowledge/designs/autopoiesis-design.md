---
lifecycle: pattern
owner: governance-team
last_updated: 2026-08-18
---
# Autopoiesis 设计 — 架构自创生机制 (META-04)

> 创建: 2026-08-08 | 状态: 设计稿 (D-plan) | owner: architecture-team
> 前置: 感知/反思/进化闭环已实现 (Phase B/C), 本设计定义"自修改架构"的门禁与回滚

---

## 1. 什么是 Autopoiesis（自创生）

Autopoiesis 是"生命体"区别于"自动化系统"的本质：系统能**生产自身的组成部分**，
即**修改自身结构以维持和提升其功能**。

当前系统是自动化：感知→执行→报告→人工改架构。
目标是自治化：感知→执行→**系统提议改架构**→受约束评估→人批准→**系统自改**→验证→回滚可逆。

## 2. 设计原则

| 原则 | 说明 |
|------|------|
| **保守自改** | 系统只修改"元结构"（规则/配置/场景卡），不直接改核心引擎代码 |
| **人批准门禁** | 架构变更必须经人工批准（S3 门禁），系统只提议不执行 |
| **可逆优先** | 所有自改必须可回滚（git revert / 配置快照） |
| **证据驱动** | 每次自改必须绑定运行证据（debt/gap/outcome） |
| **渐进收敛** | 自改幅度受限（单次变更 ≤1 个 ADR/规则），防失控 |

## 3. 三层自改范围

### L1 配置自改（最安全，当前已部分实现）
- 修改 governance-checks.yaml 规则（rule-adapt 已产出建议）
- 修改 signal-sources.yaml 信号源
- 修改 scene-cards.yaml 场景卡
- **门禁**: 无需架构评审，lint 通过即可
- **现状**: rule-adapt/constraint-gate 已支撑，但需加"自动应用"能力

### L2 结构自改（需评审）
- 新增 ADR（架构决策）
- 新增/修改 journey spec
- 调整 MOF M2 模型
- **门禁**: S2 人工评审 + mof validate + adr-number-check
- **现状**: evolution-agent 已能产出提案，需接"提案→ADR"落地链

### L3 引擎自改（最危险，需强门禁）
- 修改 omo/kairon/ecos 核心引擎代码
- **门禁**: S3 高风险 + 双人评审 + 全量测试 + 回滚演练
- **现状**: 禁止自动执行，仅允许"系统提议+人工执行"

## 4. 自修改闭环（完整流程）

```
┌────────────────────────────────────────────────────────┐
│  ① 感知: problem-detector/Governor 发现异常              │
│  ② 反思: scene-reflection 记录 + evolution-agent 聚合     │
│  ③ 提议: evolution-agent 产出进化提案 (S1/S2/S3)          │
│  ④ 约束: constraint-gate 评估 (红/灰线)                   │
│  ⑤ 门禁: S1自动 / S2人批 / S3人工执行                     │
│  ⑥ 自改: 落 ADR / 改配置 / 改 spec (受 L1-L3 范围约束)    │
│  ⑦ 验证: gap-verify + journey-check + 测试               │
│  ⑧ 回滚: 失败 → git revert / 配置快照恢复                 │
│  ⑨ 闭环: outcome 写入 MOS → Trust Policy 更新            │
└────────────────────────────────────────────────────────┘
```

## 5. 关键组件映射（现状 → 目标）

| 闭环环节 | 现有组件 | 缺口 | 目标 |
|---------|---------|------|------|
| ①感知 | signal-poller + problem-detector | 无 | ✅ 已实现 |
| ②反思 | scene-reflection | 无 | ✅ 已实现 |
| ③提议 | evolution-agent | 提案不自动落 ADR | 接"提案→ADR"落地器 |
| ④约束 | constraint-gate | 无 | ✅ 已实现 |
| ⑤门禁 | S1/S2/S3 分级 | S1 自动应用缺失 | autoloop 接 L1 配置自改 |
| ⑥自改 | 人工 | 无自动写 SSOT | **新组件: autopoiesis-applier** |
| ⑦验证 | gap-verify + task-verify | 无 | ✅ 已实现 |
| ⑧回滚 | git | 无自动化 | 新组件: rollback-snapshot |
| ⑨闭环 | outcome→MOS | 无 | ✅ 已实现 (T-B2) |

## 6. 风险与缓解

| 风险 | 级别 | 缓解 |
|------|------|------|
| 系统自改导致不可逆损坏 | 高 | 仅 L1 自动 + L2/L3 人批准；配置快照 |
| 提案质量差 | 中 | evolution-agent 提案必须绑定证据 (debt/gap ref) |
| 自改循环失控 | 中 | 单次变更上限 + gap-verify 门禁拦截退化 |
| 回滚失败 | 中 | 所有自改用 git 原子提交 + 快速 revert |

## 7. 实施里程碑

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M1 | 感知-反思-进化-约束-验证 闭环 | ✅ 已实现 (Phase B/C/D) |
| M2 | L1 配置自改 (rule-adapt 建议→自动应用) | 🔄 下一步 |
| M3 | 提案→ADR 落地器 (evolution-agent 接 ADR) | 📋 规划 |
| M4 | rollback-snapshot (自改回滚自动化) | 📋 规划 |
| M5 | L2 结构自改 (journey/spec 自动新增) | 📋 远期 |

## 8. 验收标准

- [ ] M2: 一条 rule-adapt 降级建议被系统自动应用（人批准后），且可回滚
- [ ] M3: evolution-agent 产出的提案能自动落为 ADR 草稿
- [ ] M4: 自改后若 gap-verify 退化，系统自动回滚
- [ ] M5: 系统能自主新增一个 journey spec（有证据支撑）并通过验证

---

**结论**: Autopoiesis 不是全自动魔法，而是**受约束的自修改能力**。
当前基础设施已 80% 就位（感知/反思/进化/约束/验证闭环），
缺的是 L1 配置自改的应用器和回滚快照。建议按 M2→M5 渐进实现。
