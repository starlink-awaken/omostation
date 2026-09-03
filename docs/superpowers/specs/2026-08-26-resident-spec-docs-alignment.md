---
status: accepted
lifecycle: spec
owner: resident
created: 2026-08-26
last-reviewed: 2026-08-26
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-20
type: ssot
last_updated: 2026-09-03
---

# Resident 规格文档对齐：CLI 全量收录 + Agent Cell 子系统状态标记

> 日期：2026-08-26
> 状态：accepted
> BET：BET-Y1Q3-T10-20
> 上游：resident 体系价值兑现优化轮；方向 D（Task #51 下一里程碑，用户选「以上全部依次执行」）

## 背景与问题

`docs/architecture/resident-agent-system-v1.md` 是 resident 体系功能规格 SSOT，但已落后于实现：

1. **2.1 CLI 列表缺子命令**：T10-15 加入的 `resident inbox`、T10-16 加入的 `resident monitor`/`resident heartbeat`
   未收录；`promote` 注释未反映 T10-17 五问骨架能力。
2. **Agent Cell 子系统未收录**：omo main 已有 AGE-v2 Agent Cell 完整实现（cell_* + executor/planner/
   governor/pdp_pep/memory_pipeline/replay/swarm_custodian，2026-08-24~25 并发合入），规格文档只字未提，
   且其「接线/归档」状态无记录（方向 C 决策：不归档、不提前接线，待 T1-12 合流后评估）。
3. **数据面/运维描述过时**：未含 retros/resident（五问 retro + index.md）、evolution-proposals（决策提案）、
   CRON_PROPOSAL_ADR。

## 目标

让规格文档与实现同步：

1. **2.1 CLI 全量收录**：补 `inbox` / `monitor` / `heartbeat`，更新 `promote` 注释（五问骨架）。
2. **新增 §3.1 Agent Cell 子系统**：说明模块清单 + CLI 入口（`omo cell`）+ 状态标记
   （T1-12 并发推进中，方向 C 决策不归档不提前接线）。
3. **§4 运维/数据面更新**：cron 含 CRON_PROMOTE + CRON_PROPOSAL_ADR；数据面含 retros/resident +
   evolution-proposals。
4. last-reviewed 更新为 2026-08-26。

## 设计

纯文档改动（`docs/architecture/resident-agent-system-v1.md`），无代码/配置变更。

## done_when (AC)

1. 2.1 CLI 列表含 `inbox`/`monitor`/`heartbeat`，`promote` 注释含五问骨架。
2. §3.1 Agent Cell 子系统段存在（模块清单 + `omo cell` 入口 + T1-12 状态标记）。
3. §4 含 CRON_PROPOSAL_ADR + retros/resident + evolution-proposals。
4. last-reviewed = 2026-08-26。

## verify

- `make doc-ssot-lint` 相关检查 exit 0（文档 frontmatter/SSOT 合规）

## non_goals

- 不改 omo 代码 / 不改路由表 / 不接线 Agent Cell（方向 C 决策延迟）
- 不归档任何模块（AGE-v2 为并发活跃工作）
- 不引入新章节结构（沿用现有 § 编号，仅插入 §3.1）
