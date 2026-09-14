---
schema_version: retrospective/v1
type: retro
title: "<BET-ID> Closeout Retro — <简短标题>"
bet_id: "<BET-ID>"
status: draft
lifecycle: contract
owner: governance-agent
created: "<YYYY-MM-DD>"
last-reviewed: "<YYYY-MM-DD>"
---

# <BET-ID> Closeout Retro

> **TL;DR**: 一句话概括本次交付的核心结果。

## Deliverables

- `<path/to/file1>` — 简述
- `<path/to/file2>` — 简述

## Q1 实际耗时 vs appetite？

Appetite: __天。实际: __。
（超出/未超出。超出原因：）

## Q2 done_when 是否全部通过？哪条没过，为什么？

逐条列出 done_when 条件，标注 ✅ 通过 / ❌ 未通过。

| # | done_when 条件 | 结果 | 说明 |
|---|----------------|------|------|
| 1 | ... | ✅/❌ | ... |

## Q3 过程中发现的与 plan 不符的事实（打假）

1. ...
2. ...

（如果没有不符事实，写"无"）

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

| 类别 | 增 | 净 |
|------|----|----|
| 代码行 | +N | +N |
| 文件 | +N | +N |
| GaC 规则 | +N | +N |
| ADR | +N | +N |
| 脚本 | +N | +N |

## Q5 下一个认领本 track 的 agent 需要知道什么？

（关键上下文、依赖、阻塞项、已知坑）

---

## Evidence

- **Run**: `<agent-workflow-run-id>`
- **PR**: #<PR号>
- **Merge SHA**: `<sha>`
- **Worktree**: `ws-<session>`

## 教训 (Lessons Learned)

1. **<教训标题>**: <详细描述，含触发条件和改进措施>
2. ...

## Next Steps

1. [ ] <下一步行动>
2. [ ] ...
