---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-15
related:
  - ../decisions/0203-requirement-iteration-workflow-mandatory.md
source: learner-2026-07-15-stack-retro
---

# Pattern — ADR 并发编号撞车

## The Insight

ADR 号是 **全局共享有序命名空间**，多 agent / 多 worktree 同时抢占。  
**原则：谁先合入 `origin/main` 谁拥有该号；撞车时后到者让号并改 INDEX，不改已合入文件的语义号。**

## Why This Matters

2026-07-15 Scheme C / Wave2 栈：功能线与 ISC-2 同时抢 0193 附近号段，导致 `adr-coverage` / INDEX 阻断；调和后 ISC-2 固定 **0195**，功能 ACL 顺延 **0196–0198**（PR #360 / #365）。

## Recognition

- 同日多 worktree 写 `.omo/_knowledge/decisions/01xx-*.md`
- PR 上的 ADR 号与 `origin/main` 文件名不一致
- `fix(adr): …撞车调和` 类提交

## Approach

1. 写文件前：`git fetch origin main` + `ls decisions/ | sort | tail` + 读 INDEX 末尾  
2. `next = max(on origin/main) + 1`，不信本地脏 branch  
3. 已合入号保留；未合入顺延；同步文件名 / 标题 / INDEX / closeout / PR body  
4. 判断存在性用 `ls` + Read，不用 word-level grep 假阴性  

证据：`docs/closeout/2026-07-15-stack-summary-retrospective.md` §7。
