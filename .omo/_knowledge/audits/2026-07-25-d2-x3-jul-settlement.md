---
title: D2 — X3 7 月交付月度结算与归因
date: 2026-07-25
type: audit
strat: STRAT-P81
related_cards:
  - strat-p81-batch3-workorder
related_runs:
  - D3 closeout (#501)
last_updated: 2026-08-25
lifecycle: history
owner: unassigned
---

# D2 · X3 7 月交付月度结算与归因

## 结算结论

X3 工作交付月度软门禁（T4.1）7 月结算：

- **本月 (2026-07) 交付**: 4
- **上月 (2026-06) 交付**: 0
- **环比**: Δ+4（正向增长）
- **软门禁阈值**: 8
- **状态**: 4 < 8 → 软门禁预警**保留**（warning only，不阻断 CI/workflow）

## 口径核实（P73 事实驱动）

X3 软门禁口径（`.omo/_truth/registry/x3-delivery-soft-gate.yaml`）：

- `source_scan`: `spaces/**/*.yaml`
- `match_keywords`: `delivery` / `deliverable`

7 月 spaces/ delivery 文件（实测 4）：

- `spaces/runtime-space-cross-root-rule-registry.yaml`
- `spaces/system-space-cross-root-rule-registry.yaml`
- `spaces/system-space-rollout-policy.yaml`
- `spaces/runtime-space-rollout-policy.yaml`

**注意**：X3 口径 ≠ git PR 数。7 月 git squash PR = 21, merge PR = 10, 但 X3 只计
spaces/ delivery yaml。两者维度不同：git PR 是代码/治理提交, X3 delivery 是空间交付物。
**4 是 X3 口径真值**, 不是漏算。

## 月度归因（为什么不凑数）

7 月 4 个 spaces/ delivery 全是**治理配置类**（cross-root-rule-registry + rollout-policy）,
非业务/创意交付。7 月主轴：

- **R 波**: health 91→96（治理修复, adr-coverage pattern_text + 幽灵 run 收口）
- **P 波**: G-DEL.3 物理测量（macmini 真机, p99 159ms WiFi 未达标）
- **C 波**: health≥95 gate 解锁（待人类拍板 C1 角色扩容）

7 月重心在治理健康度 + 物理底座, spaces/ 交付是治理配置的副产物。
环比 Δ+4（从 0 增长）是正向信号, 但未达 8 软阈。

**不凑数**: 4 是真实交付, 软门禁预警保留, 月度归因如实记录。
不人为添加 delivery yaml 凑到 8（违背 D2「不凑数」原则 + KISS）。

## 看板影响

- X3 软门禁: 预警保留（4 < 8）, 不阻断
- BRIEF §1 已正确显示预警（`[X3-SOFT-GATE/soft]`）
- 下月（8 月）若 C 波角色扩容落地, spaces/ delivery 可能增长（角色配置产出）
