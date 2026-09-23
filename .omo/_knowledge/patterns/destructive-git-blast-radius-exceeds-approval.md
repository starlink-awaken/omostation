---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-09-23
related:
  - host-mutation-dual-gate.md
  - p73-truth-driven-engineering-pattern.md
  - ../pitfalls/gate/PITFALL-GAT-011.yaml
source: session-2026-09-23-governance-debt-convergence
type: ssot
---

# Pattern — 破坏性操作的真实爆炸半径可能远超授权前提

## The Insight

**用户授权的是"目标"，不是"手段"。** 一句"可以，继续 / 我授权推进"针对的是 agent 当轮陈述的前提假设
（例如"工作树是脏的，reset 一下即干净"）。若真实状态使该前提为假，则该授权**不覆盖**实际会发生的破坏。
执行前必须验证前提本身，而不是把授权当作对任意达成手段的空白背书。

## 触发场景

准备对**共享主工作区**执行 `git reset --hard` / `git checkout --` / `git clean -fd` / 强制分支切换等
不可逆或会覆盖未提交/已提交工作 的操作。多 agent + Resident Agent 并发写同一工作树时，风险被放大。

## 实证来源（2026-09-23）

用户说"可以。继续"后，agent 拟对 `/Users/xiamingxing/Workspace` 跑 `git reset --hard origin/main` 以"清脏"。
`reset --hard 前三确认` 预检发现前提为假：

1. 本地 `main` 领先 `origin/main` **9 个仅本地 commit**（含未推送的 clash-infra-war retro、
   clash-node-architecture 编辑）——reset 会**静默销毁已提交工作**，不是"清工作树"。
2. Resident Agent 正在**并发提交**——reset 与并发写者交织会丢数据。

真实爆炸半径 = "销毁 9 个 commit + 打断并发写者"，远超授权所依据的"只是清脏"前提。
→ agent **STOP**，把真实范围如实 surface，未代理执行破坏性 reset。随后 9 个 commit 全部干净落地，
 restraint 被验证正确。

## 方法：破坏性 git 前三确认（任一不满足即停）

| # | 确认项 | 命令 | 停止条件 |
|---|--------|------|----------|
| ① | 当前分支正确 | `git rev-parse --abbrev-ref HEAD` | 非预期分支 |
| ② | reset 目标 == 该分支的 origin 状态且**不回退已提交工作** | `git log --oneline origin/main..HEAD` | 有领先 commit |
| ③ | 工作树真的干净、无并发写者 | `git status --short` + `ps aux \| grep <resident>` | 脏 / 有并发提交 |

## 遇到前提为假时（非破坏性替代）

- **不删只挪**：move aside / 改名 / `git stash push -u -m "<唯一 tag>"`（共享环境禁裸 `git stash`，用唯一 message + `apply` 精确恢复）。
- **快照兜底**：`make wip-snapshot` / `bin/gac/workspace-wip-guard.py`。
- **等并发落定**：Resident/executor 提交完成后复查，再决定。
- **升级给用户**：如实报告"目标 vs 真实手段代价"，请用户就**实际后果**重新授权，而非沿用旧前提下的授权。

## 关联纪律

- 主工作区只读，凡改动必 worktree（AGENTS.md §0）——从源头消除"在主工作区清脏"的需求。
- P73 真值驱动：动手前先测量真实状态，不信"看起来是脏的"。
- 姊妹教训 [[PITFALL-GAT-011]]：同样属"把告警信号读得比实际更危险/更紧急"——CI 的 `cancelled`
  被当成 `failure`。两者共性：**在采取破坏性/占有性动作前，先证伪那个吓人的信号**。
