---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# Phase 10 交叉审计报告

> 类型: 交叉审计
> 审计对象: Phase 10 规划文档及相关 OMO 文件
> 审计日期: 2026-05-31
> 审计方法: 7 文件交叉对比（规划/状态/目标/注册表/索引/债务源/交付证据）
> 历史交叉审计记录 / reference only。本文记录 Phase 10 时点的交叉审计发现，不是当前 system/goals/control 状态或当前审计结论 SSOT。
> 当前事实请回看 `/.omo/state/system.yaml`、`/.omo/goals/current.yaml`、`/.omo/_delivery/` 与当前治理检查结果。

---

## 审计范围

| 文件 | 角色 |
|------|------|
| `plans/archive/phase10-planning-analysis.md` | Phase 10 主规划需求分析（被审计方） |
| `state/system.yaml` | 系统状态 SSOT |
| `goals/current.yaml` | 当前阶段目标 |
| `plans/README.md` | 计划注册表 |
| `_knowledge/design/INDEX.md` | 设计索引 |
| `_knowledge/management/INDEX.md` | 管理索引 |
| `DEBT-ANALYSIS.md` | 债务源数据 |
| `_delivery/task-center/control/current.yaml` | 控制面交付证据 |
| `_delivery/task-center/freshness/current.yaml` | 新鲜度交付证据 |

---

## 发现概要

| 严重度 | 数量 | 说明 |
|:-----:|:----:|------|
| 🔴 严重 | 4 | 系统状态与文档严重不一致 |
| 🟠 主要 | 6 | 规划内容缺陷或遗漏 |
| 🟡 次要 | 5 | 细节可优化 |

---

## 一、🔴 严重不一致 (Critical)

### C1: system.yaml `current_phase: 8` 但 Phase 9 W3 执行中

**来源**: system.yaml:1 `current_phase: 8` vs Phase 9 W3 task `in_progress`

**影响**: 系统 SSOT 与事实不符。控制面引用 `current_phase: 8` 导致新鲜度判断错误。

**Phase 10 映射**: S1 已定义此修复，但 Phase 10 计划中 S1 的目标 `current_phase: 9` 描述不精确——不是把 8 改 9，而是同步为 **实际状态**（Phase 9 执行中）。

**修复要求**: Phase 10 计划需明确 S1 应设 `current_phase: 9, phase9_status: in_progress, next_milestone: 自动基于 P9 完成状态`

### C2: goals/current.yaml 仍标注 Phase 8，无 Phase 9 目标

**来源**: goals/current.yaml:1 `# Phase 8 active goals` + `phase: 8`

**影响**: 所有 Phase 9 任务在 goals 文件中无对应目标条目，导致 OMO 目标-任务链路断裂。

**Phase 10 映射**: Phase 10 计划完全未提及 `goals/current.yaml` 的更新需求。S1 应扩展覆盖此文件。

### C3: plans/README.md Phase 8 条目仍标 `active`（G5），且无 Phase 10 条目

**来源**: plans/README.md:68-72 四个 Phase 8 计划文档状态均为 `active`

**影响**: 阅读注册表的人以为 Phase 8 仍在执行。同时 Phase 10 规划文档不在注册表内。

**Phase 10 映射**: S2 覆盖了 Phase 8 状态修正，但未要求添加 Phase 10 自身条目。建议 S2 一并处理。

### C4: 控制面处于 `degrade` 状态，新鲜度 70

**来源**: `control/current.yaml` `decision: degrade`, `freshness_score: 70`
         `freshness/current.yaml` `freshness_score: 70`, `stale_items: [state_update_stale]`

**影响**: 系统信号显示不健康，可能阻止新 Phase 的正常推进。

**Phase 10 映射**: S3 已定义。但 S3 的 30 分钟工作量估计偏低——需确认刷新控制面是否需要重建证据链。

---

## 二、🟠 主要缺陷 (Major)

### M1: 产品债务计数不匹配

**来源**: phase10-planning-analysis.md:47 `| **产品债务** | 10 项 |` 但实际枚举仅 P1-P6（6 项）

**原因**: 继承自 Phase 9 规划，原文未更新。DEBT-ANALYSIS.md 也未列出 10 项独立的产品债务。

**修复**: 改为 `6 项（另有 4 项 Feature Debt 未独立编号）`，或在 DEBT-ANALYSIS.md 中补全后统一。

### M2: D7 (Orphaned Task) 在 3 个 Wave 中均未分配

**来源**: phase10-planning-analysis.md:103 列出 D7，但 W1/W2/W3 均不包含 D7

**影响**: D7 成为"规划中的孤儿"——有识别无行动。与 Debt mountain 中的 D7 条目自相矛盾。

**修复**: 
- W1 中加入 D7 的确认步骤（检查 `blocked_tasks: 2` 的实际情况）
- 或将 D7 归入 W2 作为 Cross-repo 治理的一部分

### M3: 健康基线"Phase 9 93-95"是假设而非实际

**来源**: phase10-planning-analysis.md:347 `Phase 9 基线: 93-95 (假设 W3/W4 完成)`

**影响**: 实际 system.yaml `health_score: 90.0`。如果 Phase 9 W3/W4 的交付物未产生健康分提升，基线预测会偏离。

**修复**: 
- 明确标注"预测基线"而非"基线"
- 添加一个必须的 re-baseline 步骤：Phase 9 完成后重新采集实际健康分
- 建议改为"Phase 9 假设完成（W3+W4 关闭）后预期基线: 93-95"

### M4: S1 目标描述过于简单

**来源**: phase10-planning-analysis.md:172 `system.yaml 状态同步 | 10 分钟 | current_phase→9`

**风险**: 仅改 `current_phase` 数字是表面同步。`goals/current.yaml` 的 Phase 8 标识、Phase 9 目标缺失、`next_milestone` 均为问题。

**修复**: S1 范围扩展为"系统 SSOT 状态全面修复"，涵盖 system.yaml + goals/current.yaml + blocked_tasks 核查。

### M5: D7 无验证标准

**来源**: 交付标准矩阵（phase10-planning-analysis.md:319-338）无 D7 条目

**影响**: 即使 D7 被分配到某个 Wave，也无法验证是否完成。

**修复**: 在交付矩阵中为 D7 添加条目。

### M6: Phase 10 计划未引用 goals/current.yaml

**来源**: phase10-planning-analysis.md:366-374 "与现有 OMO 文档的关系"未包含 goals/current.yaml

**影响**: goals/current.yaml 是 OMO 执行核心文件，Phase 10 启动时必须更新它。

**修复**: 在 Section 12 中加入 goals/current.yaml 引用。

---

## 三、🟡 次要优化 (Minor)

### m1: D2/D3 时间线表述存在歧义

**来源**: phase10-planning-analysis.md:56-57 `跨越 5 个阶段未处理`（P5→P9）

**问题**: P9 仍在执行中，严格说 P9 的"机会"尚未结束。虽然 P9 非债务清理阶段，但标为"跨越"略有超前。

**修复**: 添加脚注 `*Phase 9 为非债务阶段，D2/D3 未纳入其范围`

### m2: T4 验证命令可能产生误报

**来源**: phase10-planning-analysis.md:332 `grep -r "/Users/" packages/`

**问题**: 某些合法文件路径可能匹配（如 README 中的示例路径），导致误报。

**修复**: 改验证命令为 `grep -rn '"/Users/' packages/ --include='*.py'` 或细化过滤规则。

### m3: Wave 3 ruff 清理目标未按优先级细分

**来源**: phase10-planning-analysis.md:201-203 T1/T2/T3 并列在同一优先级

**问题**: KOS (5,263)、Minerva (955)、OntoDerive (1,307) 的清理工作量差异巨大，不设阶段目标可能导致 Wave 3 超期。

**修复**: 对 T1 (KOS) 设 Wave 3 子目标——先清至 1,500，剩余至 500 留到 Phase ∞。或明确 T1/T2/T3 的先后顺序。

### m4: G2 "控制闸门扩展"验证标准缺失

**来源**: 交付标准矩阵无 G2 条目

**问题**: G2 在 Wave 3 中定义但无对应的交付验证标准。

**修复**: 添加 G2 的交付标准和验证方法。

### m5: health_score: 90.0 来源于 Phase 5，未经重新计算

**来源**: system.yaml:6 `health_score: 90.0` 连续 5 个阶段未变

**问题**: Phase 10 计划中 G4 计划校准健康分体系，但准确做法是：**先校准评分体系本身，再用新体系评估实际健康分**。

**修复**: 建议 G4 拆为两个子项——(a) 评分体系重新设计 (b) 用新体系重新评估当前健康分。

---

## 四、交叉索引检查

| 期望引用 | Phase 10 计划 | 结果 |
|---------|:-------------:|:----:|
| 引用 system.yaml | ❌ 未直接引用 | **缺失** |
| 引用 goals/current.yaml | ❌ 未引用 | **缺失** (M6) |
| 引用 DEBT-ANALYSIS.md | ✅ Section 12 提及 | 正确 |
| 引用 Phase 9 计划 | ✅ Section 12 提及 | 正确 |
| 引用 Phase 8 分析 | ✅ Section 12 提及 | 正确 |
| 引用 Phase 1-6 Review | ✅ Section 12 提及 | 正确 |
| Phase 10 在 plans/README.md 中存在 | ❌ 不存在 | **缺失** (C3) |
| Phase 10 在 design/INDEX.md 中存在 | ✅ 已添加 | 正确 |
| Phase 10 在 management/INDEX.md 中存在 | ✅ 已添加 | 正确 |

---

## 五、审计结论

| 维度 | 评分 | 说明 |
|:----:|:----:|------|
| 覆盖完整性 | **B** | 25 项债务基本全面，但 D7 孤悬在外 |
| 事实一致性 | **C** | 与 system.yaml/goals/current.yaml 存在多处不一致 |
| 可执行性 | **B+** | Wave 结构清晰，但少数验证标准（D7/G2）缺失 |
| 自洽性 | **B** | 内部逻辑一致，但产品债务计数不准确 |
| 外部一致性 | **C-** | 与 OMO 系统状态严重脱节 |

**总体**: **B-** — 规划内容扎实，但与 OMO 系统现状存在多处脱节，修订后方可启动。

---

## 六、修订要求汇总

| 优先级 | ID | 修订内容 | 涉及文件 |
|:-----:|:--:|---------|---------|
| P0 | C1 | 修正 system.yaml 状态描述——S1 扩展 | phase10-planning-analysis.md Section 9 |
| P0 | C2 | 增加 goals/current.yaml 更新到 S1 | phase10-planning-analysis.md Section 9 |
| P0 | C3 | plans/README.md Phase 8→completed + 加 Phase 10 条目 | phase10-planning-analysis.md Section 9 + plans/README.md |
| P0 | C4 | S3 增加证据链重建的工作量说明 | phase10-planning-analysis.md Section 9 |
| P1 | M1 | 产品债务计数 10→6+4 澄清 | phase10-planning-analysis.md Section 2 |
| P1 | M2 | D7 分配至 W2 + 添加交付标准 | phase10-planning-analysis.md Section 6/10 |
| P1 | M3 | 健康基线明确标注"预测" | phase10-planning-analysis.md Section 11 |
| P1 | M4 | S1 范围扩展 | phase10-planning-analysis.md Section 6/9 |
| P1 | M5 | D7 验证标准 | phase10-planning-analysis.md Section 10 |
| P2 | M6 | 增加 goals/current.yaml 引用 | phase10-planning-analysis.md Section 12 |
| P2 | m1-m5 | 次要优化 | phase10-planning-analysis.md 各对应章节 |

---

*审计人: CodeBuddy · 2026-05-31*
