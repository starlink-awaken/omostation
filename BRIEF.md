# BRIEF.md — 织星状态简报与决策收件箱

> **Generated**: `2026-09-05T13:54:07.931150Z` | **SSOT Source**: `.omo/state/system.yaml::health_score` | **ISC-3 复合分**: `52/100`

## 📥 待决策收件箱 (Decision Inbox)
> ⏳ **决策积压**: 1 张待人类拍板 — 人类决策是当前系统瓶颈 (非技术问题). 一页勾选清单见 `.omo/tasks/closed/decision-checklist-13-items.md`.

### ⏳ 待处理卡片与债务 (Needs Human Decisions)
- **[OMO-DEBT]** planned 卡 status 归一: deferred/backlog → pending|candidate → [`.omo/tasks/archived/done/w3w3-planned-status-normalize.yaml`](file:///Users/xiamingxing/ws-solidify-lessons/.omo/tasks/archived/done/w3w3-planned-status-normalize.yaml)

> 📊 **治理预算**: 40/40/20 (治理≤40%/协作≥40%/弹性20%, ADR-0249). 超40%须送卡.

## 📈 X3 价值仪表 (Value Metrics)

| 维度 | 度量指标 | 状态 | 物理数据源 |
|------|----------|------|------------|
| **创意创作** | 新增发布数: `676` | 正常 | `@创意创作/_outputs` |
| **工作交付** | 未接入真实数据源 (BET-Y1Q1-T1-01 废除 mtime 伪指标) | 待接入 | — |
| **知识复用** | KOS 索引篇: `0` | 正常 | `kos/` 篇目 |
| **角色·engineering** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·governance** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |
| **角色·audit** | 完成率 `100.00%` · 成本单位 `?` | 正常 | `.omo/_truth/registry/x3-role-metrics.yaml` |

## 🤝 协作双轨仪表 (Collaboration Dual-Track · P84)

> 🔴 **能力轨与产能轨数据源物理隔离, 禁止合并** (P84 §0 最高级红线). 构造场景只计能力轨, 真实 backlog 只计产能轨.

### 🎯 能力轨 (Capability · 构造场景, 可加速)
> 数据源: `构造场景 (.omo/_delivery/collab-scenarios/, 可批量注入加速)`

- 场景总数: `4` | 通过率: `100.0%`
- 对抗集: `0` 个, 失败率 `0%` (P84: 全过=对抗不足须加强)
- 冲突消解成功率: `100%` | 平均协商轮次: `0.25`

### 📦 产能轨 (Throughput · 真实 backlog, 不可造)
> 数据源: `真实 backlog (.omo/tasks/done+planned/, 不可造), Z4 去污后 (剔自产)`

- 真实任务: `0` done / `63` planned (完成率 `0.0%`)
- 人工直做占比: `0%` (0/0)
- **静默丢失: `0`** ✅ 硬红线达成

## ⚙️ 治理健康分详情 (Health Detail)

- **复合健康分**: `52/100` (警戒, 请看下方分项)
- **GAC 异常扣分**: `0/100`
- **常驻 daemon 在线率**: `50.00%`
