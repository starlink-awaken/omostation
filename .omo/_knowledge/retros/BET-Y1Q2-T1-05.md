---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-05 复盘
type: retro
---
# BET-Y1Q2-T1-05 复盘

## Q1 实际耗时 vs appetite？超出比例？

实际约 3 小时，appetite 为 2 天；使用约 6.3%，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？

10/10 通过。ECOS 的 DelegationMandate M2、四类确定性生成物、漂移检查与目标测试已在 PR #19 验证；OMO 的 grant/revoke/replay/admit、16 格风险矩阵、稳定拒绝原因、恶意回放、无写判定、并发冲突与 CLI 真实链路已在 PR #27 验证。OMO 远端 lint、全量测试和 coverage 三个 job 均通过。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. 两轮外部 Agent 都曾在目标测试通过后报告完成，但独立 reviewer 仍复现出负数/NaN 预算绕过、非法 trace、revoke 快照篡改、回放跳过本地不变量和伪并发测试。外部 Agent 的完成消息只能触发验收，不能替代验收。
2. OMO standalone CI 使用 `uv run --no-project`，不会消费 workspace 的本地 `ecos` path source；本地绿不能证明独立子仓可加载生成契约。最终在 CI 中固定安装已合并 ECOS SHA，并按 CI 实际启用的 import-order/formatter 规则修复后才全绿。
3. Orca 初始 worker 启动落入 bare shell，导致三次 `worker_done` 因 capability 缺失被拒。协调器没有把拒收伪装成成功，而是在独立验证后以 recovery override 结算并精确停止孤儿终端。
4. `bet-ledger.py surface` 在该隔离 worktree 中因部分子模块未检出，报告测试行数相对全仓基线下降 319,822 行并返回非零；这不是本 BET 删除测试，不能作为真实净减证据。另有 25 个 T6 ledger lint 错误为本 BET 之前已存在的台账债。
5. `bet-ledger.py verify/complete` 原先用根仓 `git ls-files` 检查子模块内部路径，导致已提交并已 stage gitlink 的文件永久假报“未入库”。本轮以 TDD 增加 gitlink-pin 检查：只接受根 index 的 mode-160000 SHA 中真实存在的 exact child path，子模块脏文件和旧 pin 仍 fail closed。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

以已合并子仓 PR 的 GitHub tracked diff 为准：ECOS PR #19 为 +7,228/-0、7 文件；OMO PR #27 为 +3,088/-18、9 文件；合计净增 10,298 行、16 个已修改/新增文件，其中大头是 MOF 编译生成物和负向测试。根仓 D0 harness 为 `bet-ledger.py` +98/-13、专测 +162/-0，并新增本复盘、4 条真实 write surface 和 2 个 gitlink 更新；GaC 规则 +0、ADR +0、新脚本 +0。

`bet-ledger.py surface` 原始输出中的关键非零项为：`test_loc -319,822`、`src_loc -578,376`、`gac_required +0`。前两项由隔离 worktree 的部分子模块口径导致，已判定为不可用于本 BET 的假下降；没有据此删除任何测试或源码。

## Q5 下一个认领本 track 的 agent 需要知道什么？

W2-02 只提供纯 admission 决策，不是物理 enforcement。下一步必须先核验 G-1，再单独登记 W2-03 BET，把 PDP/PEP、Capability Gateway、PolicyDecision 与 ActionReceipt 接入；W2-04 的 Episode/Role Portfolio/Inbox 投影使用独立 write surface。OMO standalone CI 继续固定消费已落地的 ECOS 契约 SHA，不能依赖开发机相邻目录。跨子模块 BET 的 D0 以 root staged gitlink pin 为准，不得用 child worktree 的 dirty 状态冒充持久化。
