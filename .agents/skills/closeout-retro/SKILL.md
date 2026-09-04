---
name: closeout-retro
title: Closeout & Retrospective
description: 闭环收尾与复盘 - 将 AGENTS.md §8 Closeout Checklist + P78 复盘固化为可执行 skill
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - pull_request merged
  - workflow completed
  - user requests closeout
---

# closeout-retro — 闭环收尾与复盘

> 将 AGENTS.md §8 Closeout Checklist + P78 复盘固化为可执行 skill

## 触发条件

- PR 合并后
- Workflow run 完成/失败后
- 用户显式请求 closeout

## 执行步骤

### Step 1: 基础收尾

```bash
git diff --stat
make gac-local-gate
make ssot-guardian
```

### Step 2: P78 诊断前置 4 问

在复盘前必须回答:

1. **反证找了吗** — 是否有证据反驳当前结论？
2. **查运行时实证了吗** — 是否验证了实际运行结果而非仅看代码？
3. **读相关 ADR 了吗** — 是否查阅了相关架构决策记录？
4. **扫了工具链吗** — 是否检查了 `bin/ssot` + `.github/workflows` 确认"缺的"真缺？

### Step 3: 三层固化

| 层 | 操作 | 目标 |
|----|------|------|
| 记忆层 | 写 memory | `.omo/_knowledge/retros/` |
| 协议层 | 更新 AGENTS.md/CLAUDE.md | 修复流程缺陷 |
| Harness 层 | 更新 hook/check | 防止同类问题复发 |

### Step 4: 输出

生成 closeout 报告:
- 变更摘要 (files changed, checks run)
- 复盘结论 (P78 四问回答)
- 固化动作 (memory/protocol/harness 更新列表)

## 相关

- AGENTS.md §8 — Closeout & Retrospective
- `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`
- `.omo/_knowledge/patterns/p78-triple-axis-diagnostic-pattern.md`
