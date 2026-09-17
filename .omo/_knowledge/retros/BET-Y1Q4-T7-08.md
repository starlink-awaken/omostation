---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-17
bet_id: BET-Y1Q4-T7-08
title: BET-Y1Q4-T7-08 复盘
type: retro
---
# BET-Y1Q4-T7-08 复盘

## Q1 实际耗时 vs appetite？超出比例？

本轮在隔离 worktree 中完成 governed packet 建立、validator/connector
收敛、focused regression test 和文档绑定。实现工作未超出 1 day appetite；
额外时间用于处理空 submodule worktree 和 workflow affected-graph claim
前置条件。

## Q2 done_when 是否全部通过？哪条没过，为什么？

实现层 done_when 已在 worktree 中满足：70 张场景卡通过生命周期验证与新的
registry 验证，唯一 v1 卡只产生显式 legacy warning；connector 的 list/create
测试证明 root 隔离和显式 state mutation。PR #3882 已于 2026-09-17
squash merge，合并提交为 `aa6d6c0b96da7baf19a88cfe1535b501470f7e6f`；
合并后的主线复测和 closeout evidence 已完成。

GaC local gate 唯一失败项是既有的 `check-cockpit-ui-dist`：当前隔离树的
`projects/cockpit-ui` 没有 dist/index.html，且子项目没有 package.json，无法
执行自愈构建。其余 gate checks 通过；该失败不由本 BET 的文件变更引入。

## Q3 过程中发现的与 plan 不符的事实（打假）

`scene-card-registry.py` 的旧口径把缺失 `domain` 和
`promotion_evidence` 当作阻断错误，导致全部当前 v2 卡被报告为无效；这些
字段并不属于当前 lifecycle validator 的必需契约。connector 的硬编码主工作树
路径会使隔离 worktree 的只读探针读取错误文件，且 create 会把 state 写到错误
位置。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

新增 1 个 focused test、1 个 accepted spec 和 1 个 retro；更新两个 validator/
connector 脚本、两个脚本 registry 描述、spec registry 和 BET ledger。未新增
GaC 规则、ADR、顶层入口或 scene-card 数据迁移。

## Q5 下一个认领本 track 的 agent 需要知道什么？

不要通过批量补写 `domain` 或 `promotion_evidence`“修复”场景卡；registry
必须继续委托 canonical lifecycle contract，并将 v1 兼容性限制在显式 warning。
任何 connector 验证都应传入隔离 root，不能依赖用户本机绝对路径。若 gate 仍被
cockpit-ui dist 缺失阻断，应先按独立子模块任务恢复其构建输入，不要把该问题
混入 Scene/Journey 收敛。

## 合并后收尾

- PR #3882: `aa6d6c0b96da7baf19a88cfe1535b501470f7e6f`
- focused regression: `3 passed`
- lifecycle validation: `70 valid, 0 invalid`
- registry validation: `70 valid, 0 invalid`; only `meeting-supervision`
  emits the intentional `scene-card/v1` legacy warning
- connector probe from the isolated repository root: 3 eligible Journey cards
- value axis remains `NOT_PROVEN`; this governance BET has
  `value_indicator_policy: false`
