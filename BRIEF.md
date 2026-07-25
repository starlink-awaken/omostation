# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-25T14:52:35.178274Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `96/100`

## 📥 待决策收件箱 (Decision Inbox)

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/Workspace/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[PHYSICAL-SUSPEND-REMINDER]** 物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · 挂起第 1 天 · 勿宣称 G-DEL.1/3 物理达标 → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** ingress-registry 28 task carrier missing (cockpit-triage WIP 悬空引用, governance-verify fail 根因) → [`.omo/tasks/planned/needs-human-ingress-registry-drift.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-ingress-registry-drift.yaml)
- **[OMO-DEBT]** Batch2 B3: 第 4/5 角色（research/delivery）实装提案（评估页已齐 · 待拍板） → [`.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml)
- **[OMO-DEBT]** MOF/M4 治理优化 D1-D4 决策签核 (Phase 1/2 启动前置) → [`.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** STRAT-P81 Batch 4 提案（多 agent 协作深化主轴 · C 波 · 待人类拍板） → [`.omo/tasks/planned/needs-human-p81-batch4-proposal.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p81-batch4-proposal.yaml)
- **[OMO-DEBT]** P80 T1.2 residual: bos_stdio_ratio < 65% (live ~69.2%) — REAL migration pending → [`.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml)
- **[OMO-DEBT]** 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） → [`.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml)

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `674` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `11648` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **协作仪表** | 协商轮次 `2` · 冲突消解 `1/1` · 失败率 `20%` (含不静默) | 正常 | `.omo/_truth/registry/x3-collab-metrics.yaml` |

<details>
<summary>⚙️ <b>治理健康分详情 (复合 96/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `85/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
