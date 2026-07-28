# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-07-28T11:08:55.695902Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `91/100`

## 📥 待决策收件箱 (Decision Inbox)

### ⚠️ 软门禁预警 (Soft Gate Warnings · 不阻断)
- **[X3-SOFT-GATE/soft]** 工作交付月度软门禁: 2026-07 交付 4 < 阈值 8（环比 0 → 4, Δ+4） → [`.omo/_truth/registry/x3-delivery-soft-gate.yaml`](file:///Users/xiamingxing/ws-decision-inbox-land-20260728/.omo/_truth/registry/x3-delivery-soft-gate.yaml)

> 📊 **治理预算**: 40/40/20 (治理≤40%/协作≥40%/弹性20%, ADR-0249). 超40%须送卡.

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `674` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 本月 `2026-07`: `4` / 上月 `2026-06`: `0` (累计 `4`, 软阈 `8`) | 预警 | `spaces/` + `.omo/_truth/registry/x3-delivery-soft-gate.yaml` |
| **知识复用** | KOS 索引篇: `0` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |

## 🤝 协作双轨仪表 (Collaboration Dual-Track · P84)

> 🔴 **能力轨与产能轨数据源物理隔离, 禁止合并** (P84 §0 最高级红线). 构造场景只计能力轨, 真实 backlog 只计产能轨.

### 🎯 能力轨 (Capability · 构造场景, 可加速)
> 数据源: `构造场景 (.omo/_delivery/collab-scenarios/, 可批量注入加速)`

- 场景总数: `134` | 通过率: `79.9%`
- 对抗集: `30` 个, 失败率 `90%` (P84: 全过=对抗不足须加强)
- 冲突消解成功率: `70%` | 平均协商轮次: `0.67`

### 📦 产能轨 (Throughput · 真实 backlog, 不可造)
> 数据源: `真实 backlog (.omo/tasks/done+planned/, 不可造)`

- 真实任务: `5` done / `9` planned (完成率 `35.7%`)
- 人工直做占比: `0%` (0/5)
- **静默丢失: `0`** ✅ 硬红线达成

<details>
<summary>⚙️ <b>治理健康分详情 (复合 91/100, 已自动收纳)</b></summary>

- **GAC 异常扣分**: `69/100` (无 anomalies)
- **常驻 daemon 在线率**: `100.00%`
- **新鲜度分数**: `100/100` (正常)

</details>
