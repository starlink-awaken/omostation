---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
migration-from: .omo/_knowledge/design/plans/dbo-archive/
note: "P54 R1: 整体迁移自 design/plans/dbo-archive/, 因 DBOS Phase 0 已冻结 (2026-05-14), 内容价值保留但定位改为归档。"
---

# DBOS (DigitalBrainOS) Phase 0 计划归档

> ⚠️ **历史归档** — 2026-05-14 Phase 0 冻结, 内容仅作历史可追溯, 不可作为执行依据。

## 迁移说明

| 原位置 | 新位置 |
|--------|--------|
| `.omo/_knowledge/design/plans/dbo-archive/` | `.omo/_knowledge/plans-archive/dbo-archive/` (本目录) |
| `.omo/_knowledge/design/plans/dbo-archive/approved/` | `.omo/_knowledge/plans-archive/dbo-archive/approved/` |
| `.omo/_knowledge/design/plans/dbo-archive/templates/` | `.omo/_knowledge/plans-archive/dbo-archive/templates/` |

**迁移理由** (P54 R1):
- DBOS Phase 0 已冻结 (2026-05-14 phase0-freeze-report)
- 当前架构已演进至 eCOS v6 (5+4+1+1), 与 DBOS Phase 0 设计有结构性差异
- 7 个文件 (`approved` 4 + `templates` 3) 不再是 active plan
- 沿用 P53"不动路径"原则的演进版: 整体子树迁移到 plans-archive/ 而非仅加 frontmatter

## 内容索引

### Approved (历史批准)
- `approved/GIP-2026-001-global-implementation-plan.zh-CN.md` — DBOS 全局实施计划
- `approved/W1-conductor-operating-system.md` — Conductor 操作系统 W1 设计
- `approved/phase0-freeze-report.md` — Phase 0 冻结报告 (2026-05-14)
- `approved/PLAN-INDEX.md` — 计划索引

### Templates (模板可复用)
- `templates/proposal-template.md`
- `templates/sprint-plan-template.md`
- `templates/wave-plan-template.md`

## 当前权威计划

| 类别 | 权威读源 |
|------|----------|
| 当前活跃计划 | `.omo/_knowledge/design/plans/` |
| 历史归档 | `.omo/_knowledge/plans-archive/` |
| 当前 Phase/状态 | `.omo/state/system.yaml` |
| 当前目标 | `.omo/goals/current.yaml` |

---

*最后更新: 2026-06-23 · P54 R1 治理收敛 · 迁移自 design/plans/dbo-archive/*