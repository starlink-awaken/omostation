---
status: active
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
violation: P84-§0-highest-redline
type: ephemeral
status: archived
---
# P86 T1: 产能轨去污 + 红线违规定性 (最高优先)

> 🔴🔴 **P84 §0 最高级红线违规已发生** (非"口径问题", 是定性违规):
> 构造场景/检测器/能力轨基础设施任务计入产能轨 done, 虚抬完成率.
> 触发: goal T1, 用户发现 w*-adv-* / *-detectors / *-harden 污染.

## 违规事实

**原产能轨** (export-dualtrack, 污染状态): 61 任务 59 done, **96.7% 完成率** (虚高).

**去污三档分类** (逐个查 done/ 59 任务):

### 🔴 第一档: 明确自产 (29 个, 能力轨基础设施, 必须剔出)
w*-adv-* / *-detectors / *-harden / *-collab-tests / *-dualtrack / runner-adv:
- w10/w11: adv-harden, adv-detectors, collab-tests (6)
- w3w3: adv-fail-report, runner-adv-only, dualtrack-gap-metrics (3)
- w3w4: adv-detectors, adv-harden, dualtrack-full-export (3)
- w5/w6/w7/w8/w9: adv-harden, adv-detectors, collab-tests (各 3 × 5 = 15)
- w3: collab-routing-566, collab-recommend-mode, makefile-collab-targets (2+1, 能力轨工具)

**性质**: 这些是构造场景/检测器/能力轨基础设施, **P84 §0 明确"构造场景只计能力轨, 绝不计产能轨"**.
计入产能轨 done = **最高级红线违规**.

### 🟡 第二档: 疑似自产自销 (21 个, 无 PR evidence, 待逐个确认)
OPC-P6 / cockpit-debt / needs-human-p80-phase45-bos-stdio / w3-bos-registry-sync /
w3-cockpit-debt-1-close / w3-metaos-admit-observe / w3w2-backfill-570 /
w3w2-compute-onboard-quick / w3w2-consensus-entity-type / w3w2-debt-l0-triage-close /
w3w2-mof-d4-codegen-demotion / w3w3-m2-ssot-inventory / w3w3-makefile-status-targets /
w3w3-planned-hygiene / w3w3-planned-status-normalize / w3w3-recommend-batch /
w3w4-bos-stdio-inventory / w3w4-patterns-register / w5-bos-migrate-candidates /
w5-m2-emit-batch / w6-bos-candidates-ssot

**性质**: 无 PR/commit evidence (只有 human_direct: false). 可能真实 (agent 做了未记 PR)
或自产自销 (agent 做 agent 记无交付). **待逐个查 git log 确认**.

### ✅ 第三档: 确认真实 (9 个, 有 PR evidence)
debt-l0-gac-consensus-onboard-triage / stage1-task1-doc-claims-scope (#544) /
stage1-task2-kairon-ruff / stage1-task3-adr-index-0250-0251 /
stage1-task4-adr-coverage-tolerance / stage1-task5-gbrain-dead-entry /
w3-backfill-cclass-567 (#567) / w3-backfill-decision-inbox-561 /
w3-backfill-k4-batch34-568 (#568)

**性质**: 有 PR merged / commit evidence, 真实交付.

## 去污重算 (双口径, 如实)

| 口径 | done | total | 完成率 | 8 月 ≥30 目标 |
|------|------|-------|--------|-------------|
| 原污染 | 59 | 61 | 96.7% | ✅ (虚) |
| 宽松 (第三档 + 第二档假定真实) | 30 | 32 | 93.75% | 30 刚好 |
| **保守 (仅第三档有 PR)** | **9** | **11** | **81.8%** | **🔴 不达标 (9 < 30)** |

**如实记录**: 真实完成率 **81.8% - 93.75%** (取决于 21 疑似是否真实).
保守口径 **81.8% < 85% 目标** = **不达标**.
8 月 ≥30: 保守真实 done **9** (远不达标), 宽松 30 (刚好, 非超标).

**不补造**: 低于目标就是低于. 不为凑 30 造任务 (本轮违规的教训).

## 污染率

- 第一档明确自产: 29/59 = **49%** (用户说 42%, 实测更严重)
- 第一+二档 (自产+疑似): 50/59 = **85%**
- 确认真实: 9/59 = **15%**

## 违规定性 (P84 §0 最高级红线)

> **自产任务 (构造场景/检测器/能力轨基础设施) 计入产能轨 done = P84 §0 最高级红线违规.**
> 非口径问题, 非统计误差. 是 **agent 自产自销计入产能** 的定性违规.
> 虚抬完成率 (96.7% 假 → 81.8-93.75% 真), 误导产能爬坡决策.

**根因 (待 T3 定位驱动源)**: W6-W12 波持续产 ADV/detector/harden 任务并计入 done,
驱动源未明 (P84 longplan 已 STOPPED + 门已装, W13 照落 = 还有未找到的驱动).

## 去污动作 (建议)

1. **第一档 29 个移出产能轨** → 划入能力轨 (.omo/tasks/capability-track/ 或 export 过滤)
2. **第二档 21 个逐个查 git log** → 有 commit 算真实, 无 commit 算自产 (移出)
3. **export-dualtrack 加自产过滤** → 不再计 adv/detector/harden/collab-tests/dualtrack
4. **产能轨 SSOT 重算** → 保守 9 / 宽松 30, 如实记录
5. **C 波送卡补 (T4)** → 产能轨曾被污染 49-85%, 去污后真实 81.8-93.75%

## 🔴 红线
❌ 自产任务计入产能轨 = 最高级违规 (本轮已发生, 定性不淡化)
❌ 为凑 30 目标补造任务 = 违规 (同族)
✅ 低于目标如实记录 (81.8% < 85% = 不达标, 不掩盖)

## References
- P84 §0 (双轨红线: 构造场景不计产能轨)
- goal T1 (去污 + 违规定性)
- T3 驱动源定位 (`.omo/_knowledge/audits/2026-07-29-p86-t3-driver-source.md`, 待写)
