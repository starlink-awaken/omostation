# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-24T08:36:58.201940Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `98/100`

## 📥 待决策收件箱 (Decision Inbox)

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[PHYSICAL-SUSPEND-REMINDER]** 物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · 挂起第 0 天 · 勿宣称 G-DEL.1/3 物理达标 → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** Batch2 B3: 第 4/5 角色（research/delivery）实装提案（评估页已齐 · 待拍板） → [`.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** P80 T1.2 residual: bos_stdio_ratio < 65% (live ~69.2%) — REAL migration pending → [`.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml)
- **[OMO-DEBT]** P81 S0.1: M1 提前验收申请（ADR-0210 Confirmation · 人类拍板） → [`.omo/tasks/planned/needs-human-p81-m1-acceptance.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-p81-m1-acceptance.yaml)
- **[OMO-DEBT]** 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） → [`.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml)
- **[OMO-DEBT]** STRAT-P81 Batch 3 提案（物理 KPI 冲刺主轴 · 待人类拍板） → [`.omo/tasks/planned/needs-human-batch3-proposal.yaml`](file:///Users/xiamingxing/ws-p81-cleanup/.omo/tasks/planned/needs-human-batch3-proposal.yaml)

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `674` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `0` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |

<details>
<summary>⚙️ <b>治理健康分详情 (复合 98/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `92/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
