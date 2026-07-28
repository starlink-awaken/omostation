# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-27T16:00:40.962042Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `96/100`

## 📥 待决策收件箱 (Decision Inbox)
> ⏳ **决策积压**: 7 张待人类拍板 — 人类决策是当前系统瓶颈 (非技术问题). 一页勾选清单见 `.omo/tasks/planned/decision-checklist-13-items.md`.

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/Workspace/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[PHYSICAL-SUSPEND-REMINDER]** 物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · 挂起第 3 天 · 勿宣称 G-DEL.1/3 物理达标 → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** Batch2 B3: 第 4/5 角色（research/delivery）实装提案（评估页已齐 · 待拍板） → [`.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml)
- **[OMO-DEBT]** MOF/M4 治理优化 D1-D4 决策签核 (Phase 1/2 启动前置) → [`.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml)
- **[OMO-DEBT]** metaos 治理批 Phase 1/2 前提: D1-D4 四项决策 (CLI/PID/agentkit/admit) → [`.omo/tasks/planned/needs-human-metaos-phase12-d1-d4.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-metaos-phase12-d1-d4.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） → [`.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml)
- **[OMO-DEBT]** done/ 流转停滞 — 任务状态机无人推进 (真实运营信号) → [`.omo/tasks/planned/needs-human-task-flow-stagnation.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-task-flow-stagnation.yaml)

> 📊 **治理预算**: 40/40/20 (治理≤40%/协作≥40%/弹性20%, ADR-0249). 超40%须送卡.

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `674` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `11648` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |

## 🤝 协作管线仪表 (Stage 1 · S1.2 · strat-p83)

> 月度爬坡 (strat-p83 S1.1). 红线: 静默丢失>0 立即停管线 · 造任务凑数=最高级违规 · 治理≤40%.
> 指标定义 SSOT: `.omo/plans/stage1-collab-tracker.md` (待 generate-brief 模板化持久 · TODO).

| 月份 | 真实任务 | 完成率 | 人工直做 | 静默丢失 | 协作 vs 单agent |
|------|---------|--------|---------|---------|----------------|
| 2026-08 目标 | ≥30 | ≥85% | ≤50% | **=0** | ≥1x (不可劣于) |
| 准备期实测 (07-28) | 1 | 100% | 0% | **0** ✅ | **5.4x** |

**协作质量五指标**: 冲突消解率(≥80%) · 协商轮次(≤2) · 协商成本(基线) · 失败重试率(≤10%) · **静默丢失(=0 硬红线)**.
**任务#1 (DOC_CLAIMS_SCOPE) 实测**: 6 haiku 并行 · 0 冲突 · 1 轮 dispatch · 0 retry · 0 静默丢失 · 5.4x 加速.

> 📊 **治理占比**: 七轮收口 (PR #544 merged · main `4b1376312` · CI 11/11 + phase-gate). 8 月起协作主轴 ≥40%, 治理 ≤40%.

<details>
<summary>⚙️ <b>治理健康分详情 (复合 96/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `85/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
