---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-31
last-reviewed: 2026-08-31
bet_id: BET-Y1Q3-T1-13
risk_level: L2
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# T4-07 closeout — 子模块指针同步与 agora index 恢复

## Objective

在 T4-07 Human Adjudication merge 后，恢复 `projects/agora` 子模块 index 并将 `projects/agora`、`projects/cockpit`、`projects/omo` 同步到父仓库 HEAD 记录的 commit，消除 `git status` 大面积删除、子模块漂移。

## Contract

- 唯一实现面是子模块指针恢复与 `docs/plans/3y-bet-ledger.yaml` 台账条目。
- 不修改子模块内部业务代码，不新增/删除子模块，不改变 T4-07 业务逻辑。
- 接受依据为 `git status --short == 空` 且 `git submodule status` 无 `+` 前缀。

## Done when

- `projects/agora` index 已恢复，工作区文件全部存在
- 三个子模块 commit 与父仓库 HEAD 指针一致
- 父仓库 `git status --short` 返回空

## Non-goals

- 子模块内部功能改动
- 新子模块或 gitlink 结构调整
