---
title: Round Workflow
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - new feature work
  - architecture change
  - multi-PR effort
---

# round-workflow — Round 工程闭环

> 将 AGENTS.md §10 Round Workflow Playbook 7 步闭环转为可执行 skill

## Round 类型

| 类型 | 触发 | 输出 |
|------|------|------|
| **R-patch** | 修缺陷 / 守门 | 1-2 ADR + 测试, Health 持平或↑ |
| **R-feature** | 新增能力 | 3+ ADR + 工具, Health ↑ |
| **R-meta** | 治本 | 4-5 ADR + 元模型扩展, Health ↑ |
| **R-archive** | 决策回顾 | 0 实改, 1-2 ADR 治理声明 |

## 7 步执行

```
Round X:
0. baseline:  make m4-health
1. worktree: bash bin/gac/gac-worktree.sh claim round-{X}
2. deliver:   实施 N 个 deliverable (每 PR 1 deliverable)
3. tests:     加 T-X 系列测试, 跑 regression
4. self-reflex: bin/mof/mof-bootstrap.py all (5-check strict)
5. ADR:       写新 ADR
6. health:    make m4-health-compare (delta ≥ 0)
7. close:     写 docs/M4-DECISIONS-INDEX.md, 准备 PR
```

## 每 Round 必须回答 3 个门槛

| 门槛 | 问题 |
|------|------|
| **P72** | 路径不过载？ |
| **P52** | 不动元模型/引擎？ |
| **P74** | Governance 自闭环？ |

## 相关

- AGENTS.md §7 — Historical Patterns & Architecture
- `.omo/_knowledge/decisions/0148-round-trip-playbook.md`
- `bin/plan/bet-ledger.py` — BET 台账
