---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T6-16
risk_level: L3
human_gate: true
value_indicator_policy: false
type: ssot
---

# T6-16 多仓本地分支、脏工作树与未合并交付的保护性收敛设计

## 1. 目标

在不丢弃并发工作、不强推、不重置共享树的前提下，盘点根仓及子仓的本地分支、
未提交状态、开放 PR 与子模块指针漂移，按 owner、可达性、测试与合并状态形成
可执行的收敛序列，并逐项处置到可判定状态。

## 2. In scope

1. 根仓本地 `main` 与 `origin/main` 的分叉（领先/落后提交的内容等价判定，
   冗余提交不重放，未合并增量保住分支引用后对齐）。
2. 根仓全部 `ws-*` worktree 与本地分支：逐个判定 `已合并可清退` /
   `owner 在途保留` / `unknown 待联系`，可清退项执行 remove + 分支删除。
3. 子模块脏工作面（cockpit / omo / runtime / cockpit-ui 等）：标记
   owner-owned / generated / unknown / 已恢复。
4. 子模块指针漂移（ssot-guardian 报告的 aetherforge/ecos/family-hub/
   kairon/omo 等本地 gitlink 前移）：判定是并发在途（保留并登记）还是
   可入账（走 submodule-pointer-transaction）。
5. 开放 PR 队列的过期项（重复 PR、已被 squash 吸收的分支）标记处置。

## 3. Explicitly out of scope

- 不强推任何共享分支；不 `reset --hard` 共享 checkout；不删除 owner 不明的
  未提交内容。
- 不新增治理机制 / workflow / registry。
- 不把收敛动作计入个人价值（value_indicator_policy=false）。
- 不在本 spec 范围内重写其他 bet 的交付内容。

## 4. 方法与纪律

- 分支等价性只看内容 diff（`git diff origin/main...<branch>`），不看 merge-base。
- 任何处置前先 `git reflog` / `git status` 取证；owner 判定优先查 run 记录
  （`.omo/_delivery/agent-workflows/runs/`）与开放 PR head。
- 每项处置在收敛报告中记录：surface、判定、动作、证据。

## 5. 验收（与 ledger done_when 对齐）

1. 每个根仓/子仓 dirty surface 被标记为 owner-owned、generated、unknown
   或已恢复，并有对应处置记录。
2. 根仓本地 main 与 origin/main 内容等价（冗余本地提交不再污染后续
   fetch/push 流）。
3. 可清退的 worktree / 分支已清退；owner 在途项有登记。
4. ssot-guardian 的 submodule_pointer_drift 高危项数量下降或逐项有 owner
   登记。
5. 收敛报告落盘 `docs/reports/`，retro 记录发现。
