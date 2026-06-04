# Phase 11 交叉审计报告 — 基线

> 类型: 交叉审计（基线评估）
> 审计对象: Phase 11 规划文档（pre_planning 阶段）
> 审计日期: 2026-06-01
> 审计方法: 7 检查点交叉对比（参照 Phase 10 C1-C4 经验）

---

## 审计范围

| # | 检查点 | 审计对象 | 审计标准 | 当前状态 |
|:-:|--------|---------|----------|:--------:|
| A1 | system.yaml | `state/system.yaml` | Phase/Wave/健康分与事实一致 | ⚠️ |
| A2 | goals | `goals/current.yaml` | 覆盖当前 Phase 目标 | ⚠️ |
| A3 | plans/README | `plans/README.md` | 注册表活跃文档与实际一致 | ⚠️ |
| A4 | control plane | `_delivery/task-center/control/current.yaml` | freshness ≥90, 无 divergence | 🔴 |
| A5 | debt tracking | `DEBT-ANALYSIS.md`, 各 Wave plan | 所有债务项标记状态可追踪 | ⚠️ |
| A6 | health trajectory | system.yaml + 各 closeout | 从 Phase 1-11 连续可追溯 | ✅ |
| A7 | verification criteria | 各 Wave execution-plan | 每个未找到 exit gate 有可执行验证 | ✅ |

### 审计结果说明

| 状态 | 含义 |
|:----:|------|
| ✅ | 已符合标准 |
| ⚠️ | 部分符合（已修补但未最终验证） |
| 🔴 | 不符合（继承自 Phase 10 的遗留问题） |

---

## 基线发现

### A1 — system.yaml (⚠️)

Phase 11 fields added (`phase11_status: pre_planning`), but `current_phase` still says `10` (correct — Phase 10 is still active). Fields will auto-resolve when Phase 10 closes.

**风险**: 如果 Phase 10 关闭时未更新 `current_phase` 字段，将重复 C1 问题。
**建议**: 在 Phase 11 Entry Gate 中显式检查 system.yaml 更新。

### A2 — goals/current.yaml (⚠️)

Phase 11 目标已作为 `phase11` 子节添加到 `current.yaml`，包含 S1-S5 目标和 4 Wave 结构。

**风险**: Phase 10 目标与 Phase 11 目标共存于同一文件，需注意边界清晰。
**建议**: Phase 10 关闭时将其目标标记为 `completed`。

### A3 — plans/README.md (⚠️)

Phase 11 已注册在 GATED 区域（`phase11-program-plan.md` 为 `pre_planning`），且新增了 `PRE-PLANNING` 状态分类和 `🔵 PRE-PLANNING` 区域。

**风险**: 新增的 `🔵` 状态标识为 OMO 规范首次引入，需验证是否被其他文档识别。
**建议**: 在 `plans/README.md` 头部状态表中已加入定义，且预规划 4 个 Wave 执行计划均已列在 PRE-PLANNING 区。

### A4 — Control plane (🔴 **Critical**)

继承自 Phase 10 的遗留问题。`control/current.yaml` 显示：
- `decision: degrade`
- `freshness_score: 70`
- `stale_reason: "state_update_stale"`
- `divergence_detected: ["system_phase_mismatch", "goals_snapshot"]`

**Phase 11 响应**: G11.1.1 / T1.4 已列为 Wave 1 P0 任务 — 必须在 Phase 11 执行前恢复。

### A5 — Debt tracking (⚠️)

债务状态已从 Phase 10 继承到 Phase 11 规划：
- D2/D3 — 已分配至 G11.2.1 / T2.1-T2.2
- D7 — 已分配至 G11.2.1 / T2.3
- P1 — 已分配至 G11.2.2 / T2.4-T2.5
- T1 — 已分配至 G11.2.2 / T2.7
- C1-C4 — 已分配至 G11.1.1 / T1.1-T1.4

**剩余**: DEBT-ANALYSIS.md 中 25 项债务需要建立统一进度仪表板（已列为 T1.14）。

### A6 — Health trajectory (✅)

健康分轨迹从 Phase 1-10 可追溯：
`75 → 80 → 88 → 90 → 90 → 90 → 90 → 90 → 90 → 90`
Phase 11 目标：`90 → 92 → 94 → 96 → 97`

**风险**: 健康分 90 已连续 6 阶段停滞。Phase 11 的 97 目标需有明确的度量杠杆。
**建议**: 在 Wave 1 确认健康分计算方式和可操作提升路径。

### A7 — Verification criteria (✅)

4 个 Wave 执行计划均包含详细的 Exit gate checklist，每个任务有具体的验证命令或标准。

**风险**: 部分验证标准（如 KOS ruff ≤500）需要手动执行，需考虑 CI 自动化。
**建议**: 在 Wave 2 执行前将关键验证标准 CI 化。

---

## 评分

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 覆盖度 | B+ | Phase 11 规划覆盖了 7/7 检查点 |
| 事实一致性 | C | A4 control plane degrade 是 Phase 10 遗留的 Critical 问题 |
| 可执行性 | B+ | 37 个详细任务分配到 4 Wave，每个有交付物和验证 |
| 自洽性 | A- | 规划文档内部一致，无矛盾 |
| 外部一致性 | B- | 依赖 Phase 10 完成状态（当前 W3 执行中） |

**基线综合评分: B-**（与 Phase 10 审计结论相同，但原因不同：Phase 10 是 SSOT 不一致，Phase 11 是依赖前置完成）

---

## 从 Phase 10 继承的审计反应

| Phase 10 教训 | Phase 11 应对 | 状态 |
|----------------|---------------|:----:|
| C1: system.yaml 不同步 | W1 P0 修复，引入 `check-system-consistency.sh` | ✅ 已规划 |
| C2: goals 无当前 Phase | W1 必须更新 goals/current.yaml | ✅ 已规划 |
| C3: plans/README 误导 | W1 更新 README + 预规划区域 | ✅ 已规划 |
| C4: 控制面 degrade | W1 P0 修复 control plane | ✅ 已规划 |
| M1: 债务计数不准确 | T1.14 债务进度仪表板 | ✅ 已规划 |
| M2: D7 orphaned 未分配 | T2.3 清理 | ✅ 已规划 |
