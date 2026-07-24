# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-24T02:49:19.647792Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `98/100`

## 📥 待决策收件箱 (Decision Inbox)

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/Workspace/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[OMO-DEBT]** P80 T1.2 residual: implement cron.tick_timeout_seconds=30 → [`.omo/tasks/planned/needs-human-p80-phase45-tick-timeout.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-phase45-tick-timeout.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** P80 T1.2 residual: agora-gateway HTTP /health live on :9000 → [`.omo/tasks/planned/needs-human-p80-phase45-agora-health.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-phase45-agora-health.yaml)
- **[OMO-DEBT]** P80 T1.2 residual: bos_stdio_ratio < 65% (live ~69.2%) → [`.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-phase45-bos-stdio.yaml)
- **[OMO-DEBT]** P80 T1.2 residual: task_files entropy cleanup to <200 → [`.omo/tasks/planned/needs-human-p80-phase45-task-entropy.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-phase45-task-entropy.yaml)

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `662` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `11566` | 正常 | `kos/` 篇目 |

<details>
<summary>⚙️ <b>治理健康分详情 (复合 98/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `92/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
