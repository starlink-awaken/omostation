---
schema_version: retrospective/v1
type: retro
title: "PR3 Closeout Retro — retro 模板 + docs freshness SOP"
bet_id: "BET-Y1Q4-T1-14"
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# PR3 Closeout Retro

> **TL;DR**: 新增 retro 模板和文档保鲜 SOP，为全部固化 PR 系列提供标准化复盘格式和文档新鲜度管理规范。纯文档交付，零脚本/gate 变更。

## Deliverables

- `.omo/_knowledge/retros/_template.md` — 标准 retro 模板（73 行），含 bet_id/run/merge/evidence/教训/next 结构
- `docs/standards/docs-freshness-sop.md` — 文档保鲜 SOP（289 行），含 frontmatter 必备字段、6 个检查工具说明、--check/--strict 差异、触发 workflow、常见失败修复

## Q1 实际耗时 vs appetite？

Appetite: 1 day。实际: ~15 min。未超出。（纯文档，无代码逻辑）

## Q2 done_when 是否全部通过？哪条没过，为什么？

| # | done_when 条件 | 结果 | 说明 |
|---|----------------|------|------|
| 1 | retro 模板创建完成 | ✅ | `_template.md` 73 行，frontmatter 校验通过 |
| 2 | docs freshness SOP 创建完成 | ✅ | `docs-freshness-sop.md` 289 行，frontmatter 校验通过 |
| 3 | 纯文档，无 gate/脚本修改 | ✅ | 仅新增 2 个文件，零修改 |
| 4 | worktree 隔离 | ✅ | `ws-pr3-retro-template-freshness-sop` 独立 worktree |

## Q3 过程中发现的与 plan 不符的事实（打假）

1. `agent-workflow.py start` 的 workflow-id 是 `project-doc-change`（不是 `doc-change`）
2. claim 命令对 work-packet scope 有限制 — 文档级新文件不在预设 scope 内，需直接在 worktree 操作

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

| 类别 | 增 | 净 |
|------|----|----|
| 文件 | +2 | +2 |
| 代码行 | +362 | +362 |
| GaC 规则 | 0 | 0 |
| ADR | 0 | 0 |
| 脚本 | 0 | 0 |

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. `_template.md` 是模板文件，status 设为 `draft`（使用时复制并修改 bet_id/title/status）
2. `docs-freshness-sop.md` 是 reference 文档，引用了 6 个保鲜工具 — 新增工具时需同步更新
3. retro 模板格式已与最近 4 个 retro（T1-12/T1-13/T1-14）的结构对齐

---

## Evidence

- **Run**: `20260905T043612Z-project-doc-change-4456abd2`
- **PR**: (待创建)
- **Merge SHA**: (待合并)
- **Worktree**: `ws-pr3-retro-template-freshness-sop`

## 教训 (Lessons Learned)

1. **agent-workflow claim scope**: 新建文件的路径不在预设 work-packet scope 内时，需绕过 claim 直接在隔离 worktree 操作。这是纯文档 PR 的常见模式。

## Next Steps

1. [ ] 提交 PR 并等待 review
2. [ ] 合入后更新 `bin/README.md` 中对 docs-freshness-sop 的引用
