# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-24T05:52:58.490112Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `96/100`

## 📥 待决策收件箱 (Decision Inbox)

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/Workspace/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[PHYSICAL-SUSPEND-REMINDER]** 物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · 挂起第 0 天 · 勿宣称 G-DEL.1/3 物理达标 → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** STRAT-P81 Batch 2 提案（Batch1 closeout · 待人类拍板） → [`.omo/tasks/planned/needs-human-batch1-batch2-proposal.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch1-batch2-proposal.yaml)
- **[OMO-DEBT]** Batch1 B4: G-DEL.2b 达标申请（process-local · 待人类宣布） → [`.omo/tasks/planned/needs-human-batch1-g-del-2b-application.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch1-g-del-2b-application.yaml)

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `674` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `11566` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `30` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `30` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `30` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |

<details>
<summary>⚙️ <b>治理健康分详情 (复合 96/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `85/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
