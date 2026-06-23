---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# X3: 价值堆栈策略

> 日期: 2026-05-27

## 1. 什么是价值堆栈

所有智力资产按价值层级管理，每层有不同半衰期和保鲜策略。价值堆栈的核心思想是：并非所有知识资产的价值衰减速度相同，因此需要差异化的保鲜策略和检查周期。高层级（如公理、原则）变化极慢，可以低频高成本维护；低层级（如工具、技能）变化快，需要高频低成本检查。

这种分层管理避免了"一刀切"的维护负担——不需要每天检查公理，也不需要每年才更新工具。

## 2. 7个价值层级

| 层级 | 示例 | 半衰期 | 保鲜策略 | 执行者 | 当前实现 |
|------|------|--------|---------|--------|---------|
| Axiom | 逻辑自洽>功能堆砌 | 终身 | 纯版本，几乎不检查 | Manual | L4 Self |
| Principle | 架构先行，红蓝对抗 | 5-10年 | 季度review+变更记录 | X2 Cron | L4 Self |
| Theory | 信息论/控制论 | 10-30年 | 年检(新证据追踪) | X2 Cron | — |
| Framework | 4+1+3架构 | 3-5年 | 半年检查 | X2 Cron | 文档 |
| Knowledge | 研究结果/实体 | 1-3年 | 月检(新鲜度标记) | X2 Cron | KOS |
| Skill | Hermes技能文件 | 6-12月 | 每次使用纠正 | 交互中 | 技能文件 |
| Tool | cron脚本/CLI工具 | 1-6月 | 每次使用前健康检查 | Watchdog | X2脚本 |

## 3. 保鲜策略详解

### Axiom（公理层）
- **半衰期**: 终身
- **保鲜策略**: 纯版本管理，几乎不需要检查。只在认知体系发生根本性变革时才需修订。
- **触发条件**: 用户主动发起哲学层面的反思（通常数年一次）。
- **执行者**: Manual（人工）

### Principle（原则层）
- **半衰期**: 5-10年
- **保鲜策略**: 季度review + 变更记录。每次修改需记录变更原因和影响范围。
- **触发条件**: X2 Cron 每季度提醒检查；L4 identity 修改时联动重置半衰期。
- **执行者**: X2 Cron

### Theory（理论层）
- **半衰期**: 10-30年
- **保鲜策略**: 年度检查，追踪新证据和学术进展。对经典理论（如信息论、控制论）做交叉验证。
- **触发条件**: X2 Cron 每年触发年检管道。
- **执行者**: X2 Cron

### Framework（框架层）
- **半衰期**: 3-5年
- **保鲜策略**: 半年检查。评估框架是否仍然适应当前需求，是否有更好的替代方案。
- **触发条件**: X2 Cron 每半年执行框架健康检查。
- **执行者**: X2 Cron

### Knowledge（知识层）
- **半衰期**: 1-3年
- **保鲜策略**: 月度检查，新鲜度标记。KOS 中的每条知识记录都带有 freshness 字段，过期标记后触发重新验证或归档。
- **触发条件**: X2 Cron 每月运行 freshness_check.sh。
- **执行者**: X2 Cron

### Skill（技能层）
- **半衰期**: 6-12月
- **保鲜策略**: 每次使用自动纠正。技能文件在交互过程中实时优化，使用频率越高保鲜越好。
- **触发条件**: 交互中自然触发。
- **执行者**: 交互中

### Tool（工具层）
- **半衰期**: 1-6月
- **保鲜策略**: 每次使用前健康检查。Watchdog 检查工具可用性，失效自动告警或修复。
- **触发条件**: Watchdog 或每次调用前。
- **执行者**: Watchdog

## 4. 集成点

### X3↔L1 Schema
consensus schema（kos/consensus/）中 freshness 字段对接 eidos schema 的 version 字段。
具体：consensus result 的 expires_at 对应 schema 的 deprecation_date。

### X3↔X2 Cron
freshness_check.sh 读取共识过期记录 → 触发X2保鲜管道。
X2 cron 按 freshness 策略决定处理（通知/归档/删除）。

### X3↔L4 Self
L4 的价值原则（principle）是 X3 的 Principle 层实例。
当用户修改 L4 identity 时，X3 的半衰期重置。

## 5. 当前实现状态

- Consensus domain: ✅ 已建（Phase 5, kos/consensus/）
- Freshness cron: ✅ 已建（freshness_check.sh）
- 价值层级枚举: ⚠️ 部分（KOS entity type有PRINCIPLE/THEORY等，未实现半衰期逻辑）
- 保鲜策略自动执行: ❌ 待X2-1实现
