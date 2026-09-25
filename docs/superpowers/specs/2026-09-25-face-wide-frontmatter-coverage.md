---
schema_version: specification/v1
spec_version: 1.0.0
title: Face-Wide Frontmatter Coverage — extend #4291 to all paths
bet_id: BET-Y2Q4-SH-2
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
---

# BET-Y2Q4-SH-2 — Face-Wide Frontmatter Coverage

## Context

PR #4291 (`241c2c3b2`) "frontmatter 全覆盖 + superpowers 镜像归档" 修了 46 个文档，但范围限制在 `.agents/*` 和 `docs/*`。诊断 `#4310` 发现：

- 530 个 retros 中 342 个 (64%) 缺 `schema/status/lifecycle` 字段
- 5 个子仓文档（`projects/.omo/AGENTS.md`, `projects/.omo/README.md`, `projects/cockpit-ui/AGENTS.md`, `projects/cockpit-ui/ARCHITECTURE.md`, `projects/cockpit-ui/BOUNDARY.md`）无 frontmatter
- 8 份 GOVERNANCE.md（`projects/*/GOVERNANCE.md`）是同一模板的重复副本（2 种 hash）

**根因**: 修复是事件式（修一个具体 drift），不是面式（修一类 drift）。同类问题在不同路径仍存在。

## Goal

建立 **face-wide frontmatter 治理**：
1. 工具能扫**所有** frontmatter 必填字段，覆盖**所有** frontmatter-bearing 路径
2. 自动 patch（增量补缺，不动现有值）
3. 防止未来同类 drift 复发

## Non-goals

- **不改 SSOT 文档** (.omo/standards/、.omo/_truth/) — 这些有独立 SLA 和真复核要求
- **不重命名字段** — 只补缺，不改 key 命名
- **不扫 archived** — `.omo/_knowledge/design/plans/archive/` 已归档文档豁免

## Done when

- `bin/ssot/frontmatter-coverage.py --face-wide` 扫 7 类路径：
  - `docs/` (含 docs/plans/, docs/superpowers/, docs/reports/, docs/operations/, docs/scene-cards/, docs/architecture/)
  - `.agents/` (含 .agents/skills/, .agents/sentinel/, .agents/ORIGINAL_REQUEST.md)
  - `.omo/_knowledge/retros/` (含 .omo/_knowledge/retros/resident/)
  - `.omo/_knowledge/reports/` (新增诊断报告路径)
  - `.omo/_knowledge/decisions/` (ADR 类)
  - `.omo/standards/` (治理合同类)
  - `projects/*/AGENTS.md` + `projects/*/README.md` + `projects/*/GOVERNANCE.md` (子仓入口类)
- 必填字段 6 个: `schema`, `status`, `lifecycle`, `owner`, `last-reviewed`, `type`
- 输出覆盖率 matrix (path × field)，报告每个组合的 miss 率
- `--apply` 模式自动 patch 缺字段（仅补，保留现有值）
- test fixtures 覆盖 ≥ 10 个 path × field 组合
- 集成到 `make gac-local-gate`：覆盖率 < 80% 时 WARN（不阻断），< 50% 时 FAIL
- 实证：跑完后 retros 缺字段从 342 降到 ≤ 30

## Verification

```bash
uv run --with pyyaml python bin/ssot/frontmatter-coverage.py --face-wide --json
uv run --with pyyaml python bin/ssot/frontmatter-coverage.py --face-wide --dry-run --apply
make gac-local-gate
```

## 关联债务

- 完成后应能 close:
  - (无现成债务，但归入 `DEBT-FRONTMATTER-COVERAGE` 新债，治理债务层级)
- 关联发现 (from #4310):
  - **#2** 5 子仓文档无 frontmatter
  - **#3** 8 GOVERNANCE.md 重复（顺带处理 template 收敛）
  - **#25** 342 retros 缺 frontmatter 关键字段

## Bootstrap authorization

- workflow: `project-code-change`
- agent: governance-agent
- 优先级: P0 (治本 — 修一类而非一件)
- 依赖: 无（独立）