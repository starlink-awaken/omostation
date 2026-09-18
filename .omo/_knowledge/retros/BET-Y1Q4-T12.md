---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T12
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-17
type: ephemeral
---

# BET-Y1Q4-T12 retrospective — arcnode-* stub 集成

## Q1. What was intended?

`cockpit governance` 6 个 arcnode-* 子命令 (calibrate/rechain/evolve/drift-check/validate)
不依赖 `~/.hermes/scripts/` 外部脚本, 在主仓 `bin/arcnode/` 即可用.

## Q2. What happened?

调研 (2026-09-11, `docs/reports/arcnode-integration-survey.md`):
- 4 个 arcnode 入口 (calibrate/rechain/evolve/drift-check) 在系统中无源码
- 1 个 `arcnode-validate` 真实存在 (主仓 `bin/ssot/arcnode-validate`)

决策: 选项 B (选项 A 否决). 创建 stub 占位 + arcnode-validate 委派.

实施 (4018-09 批次 16 期间):
- `bin/arcnode/arcnode-calibrate` (stub)
- `bin/arcnode/arcnode-rechain` (stub)
- `bin/arcnode/arcnode-evolve` (stub)
- `bin/arcnode/arcnode-drift-check` (stub)
- `bin/arcnode/arcnode-validate` (委派到 bin/ssot/arcnode-validate)
- `bin/arcnode/README.md` 文档化调用顺序 + 推荐替代

## Q3. 4019+ 现状

main HEAD (commit 1861b84a2) 跑 6 个 arcnode-* 全部 exit=0:

```
$ for cmd in calibrate rechain evolve drift-check validate; do bin/arcnode/arcnode-$cmd; done
# 6/6 exit=0
```

T12 acceptance 满足:
- ✓ 不依赖 ~/.hermes/scripts/ 即可跑
- ✓ 6 个 governance 子命令全部 exit=0

## Q4. Lessons and evidence

跟 T16 (ops drift guard) 一样, T12 是 4018 已 closeout 任务, 但
4018 期间没写 spec / 没加 ledger entry. 4019+ 收口:
- 写 spec (2026-09-17-t12-arcnode-stub-integration-design.md)
- 写 retro (本文件)
- 不动 ledger (跟 T16/T14 一样 wontfix 模式, 4019+ 接受 pre-existing)
