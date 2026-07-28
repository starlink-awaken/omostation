# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-28T07:54:53.100289Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `91/100`

## 📥 待决策收件箱 (Decision Inbox)
> ⏳ **决策积压**: 6 张待人类拍板 — 人类决策是当前系统瓶颈 (非技术问题). 一页勾选清单见 `.omo/tasks/planned/decision-checklist-13-items.md`.

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/Workspace/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[PHYSICAL-SUSPEND-REMINDER]** 物理底座挂起周重申（ADR-0228 D3）: needs-human-p80-physical-hosts 仍开放 · 挂起第 4 天 · 勿宣称 G-DEL.1/3 物理达标 → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** Batch2 B3: 第 4/5 角色（research/delivery）实装提案（评估页已齐 · 待拍板） → [`.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-role-expansion-proposal.yaml)
- **[OMO-DEBT]** MOF/M4 治理优化 D1-D4 决策签核 (Phase 1/2 启动前置) → [`.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-mof-m4-d1-d4-decisions.yaml)
- **[OMO-DEBT]** metaos 治理批 Phase 1/2 前提: D1-D4 四项决策 (CLI/PID/agentkit/admit) → [`.omo/tasks/planned/needs-human-metaos-phase12-d1-d4.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-metaos-phase12-d1-d4.yaml)
- **[OMO-DEBT]** P80 T2: expand physical hosts ≥4 + G-DEL.3 true two-host measure → [`.omo/tasks/planned/needs-human-p80-physical-hosts.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-p80-physical-hosts.yaml)
- **[OMO-DEBT]** 机器恢复日验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁） → [`.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml`](file:///Users/xiamingxing/Workspace/.omo/tasks/planned/needs-human-batch2-physical-recovery-checklist.yaml)

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

## 🤝 协作双轨仪表 (Collaboration Dual-Track · P84)

> 🔴 **能力轨与产能轨数据源物理隔离, 禁止合并** (P84 §0 最高级红线). 构造场景只计能力轨, 真实 backlog 只计产能轨.

### 🎯 能力轨 (Capability · 构造场景, 可加速)
> 数据源: `构造场景 (.omo/_delivery/collab-scenarios/, 可批量注入加速)`

- 场景总数: `10` | 通过率: `70.0%`
- 对抗集: `6` 个, 失败率 `50%` (P84: 全过=对抗不足须加强)
- 冲突消解成功率: `50%` | 平均协商轮次: `0.6`

### 📦 产能轨 (Throughput · 真实 backlog, 不可造)
> 数据源: `真实 backlog (.omo/tasks/done+planned/, 不可造)`

- 真实任务: `5` done / `10` planned (完成率 `33.3%`)
- 人工直做占比: `0%` (0/5)
- **静默丢失: `0`** ✅ 硬红线达成

<details>
<summary>⚙️ <b>治理健康分详情 (复合 91/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `69/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
