---
type: ssot
name: adr-concurrent-number-collision-expertise
description: 并发 agent 同日写 ADR 时编号撞车的占号与让号启发式（omostation）
triggers:
  - ADR 撞车
  - adr-coverage
  - ADR 编号
  - decisions/019
  - architecture-convergence
  - 0195
  - INDEX.md ADR
  - fix(adr)

last-reviewed: 2026-08-26
owner: governance-team
---

# ADR 并发编号撞车

## The Insight

在 omostation，ADR 号不是「我本地 max+1 就行」，而是 **全局共享的有序命名空间**，由多 agent / 多 worktree 同时抢占。  
**原则：谁先合入 main 谁拥有该号；撞车时后到者让号并改 INDEX，不改已合入文件的语义号。**

## Why This Matters

2026-07-15 Scheme C / Wave2 栈中，两条线同时占用 0193 附近号段：

- 功能线：demo-seed / setfacl（后定为 0193/0194）
- 治理线：architecture-convergence ISC-2（后固定为 **0195**）

症状：

- `adr-coverage` / INDEX 阻断
- PR 描述写 0193 但 main 上已是另一文件
- 调和 PR #360：`architecture-convergence 0193→0195`，功能 ACL 顺延 **0196–0198**

若强行覆盖已合入 ADR 文件名，历史 PR/closeout 链接全断。

## Recognition Pattern

- 同一天多个 worktree 都在加 `.omo/_knowledge/decisions/01xx-*.md`
- CI / 本地 gate：`adr-coverage`、INDEX 缺项、同号双文件
- PR body 的 ADR 号与 `origin/main` 上文件名不一致
- 出现 `fix(adr): …撞车调和` 类提交

## The Approach

1. **Claim 号之前（写文件前）**：
   ```bash
   git fetch origin main
   ls .omo/_knowledge/decisions/ | sort | tail -20
   # 读 INDEX 末尾；不要只信本地脏 worktree
   ```
2. **占号心智**：`next = max(on origin/main) + 1`，不是 max(local branches)。
3. **撞车已发生时的让号规则**：
   - 已在 **origin/main** 的号 **保留**（本轮：0195 = ISC-2）
   - 未合入 / 后到功能 ADR **整体顺延**（本轮：plan-acl=0196, demo-seed-ui=0197, apply-acl=0198）
   - 同步改：文件名、frontmatter 标题、INDEX、closeout、PR 描述
4. **不要** 用 grep 词面「0195 被用」代替 `ls decisions/` + 读 INDEX（word-level 假阴性）。
5. 长期：claim worktree 时预占 `next-adr-id` 短锁（复盘建议，尚未落地）。

## Example

```text
# 错误：本地看了 0192 就写 0193，另一 agent 已合入 0193
# 正确：fetch 后发现 0193/0194 已被 demo-seed；ISC-2 让到 0195；
#       你的 plan --acl 从 0195 改为 0196 再 push
```

证据：`docs/closeout/2026-07-15-stack-summary-retrospective.md` §7；PR #360 / #365。
