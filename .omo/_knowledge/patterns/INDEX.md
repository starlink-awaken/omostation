---
status: active
lifecycle: index
owner: governance-team
last-reviewed: 2026-09-17
type: ssot
---

# Patterns INDEX — 可复用模式目录

> 跨任务踩坑经验沉淀. 每个 pattern 至少经过一次失败 + 一次修复实证.

## 类别

### PR / 合并 (P97-P103)

| ID | 标题 | 教训 |
|-----|------|------|
| P97 | TYPO apply (12 实际修复) + apply/rollback 集成测试 | #0091 |
| P98 | 3 ASPIRATIONAL + 1 REAL_BUG + 4 TYPO + regex bug 修 | #0092 |
| P99 | ADR-0092 self-ref 清 + omo_lint 兑现路径 | #0093 |
| P100 | omo_lint schemas 子模块拆分 (1269→800L) | #0094 |
| P101 | omo_lint yaml-bypass 子模块拆分 (800→731L) | #0095 |
| P102 | omo_lint surfaces 子模块拆分 (731→694L, <600L ideal) | #0096 |
| P103 | omo_lint mutation-ledger 子模块拆分 (594→544L) | #0097 |

### 网关 / 安全 (P79)

| ID | 标题 |
|-----|------|
| P79 | Partial Worktree Reachability False-Positive |

### 工作流 / 协作 (P104, P106)

| ID | 标题 | 教训 |
|-----|------|------|
| P104 | Ledger Closeout Reuse-Existing-Work Pattern | 复用已合入实现, 不重复造轮子 |
| P106 | Main-Branch Edit Clobbering by Concurrent Agents | 裸 main 编辑被并发 agent 覆盖, 先切分支 |

### 治理 / 检查 (P105)

| ID | 标题 |
|-----|------|
| P105 | Doc-Governance Auto-Bump Pattern |

### 测试 / 前端 (P107)

| ID | 标题 | 教训 |
|-----|------|------|
| P107 | SPA Catch-All Route vs Test Expectation xfail Pattern | 设计冲突用 narrow exception + xfail, 不强行改产品代码 |

## 引用规则

- 新增 pattern 必:
  1. 命名 `p<N>-<kebab-case>.md`
  2. frontmatter 含 `status / lifecycle / owner / last-reviewed / type`
  3. 至少含 TL;DR + 陷阱矩阵 + 教训来源 + 关联 PR
- 引用时必带 ADR 或 commit SHA 证据

## 关联

- `bin/ssot/auto-bump-doc-governance-budget.py` (P105 实现)
- `.omo/_knowledge/retros/LESSONS-LEARNED-2026-09-16.md`
EOF
