---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-14 复盘
type: retro
---

# BET-Y1Q2-T1-14 复盘

## 交付与真实回执

本轮没有再造 WorkPacket 或新的任务真相，而是在 OMO 上补了一层编排器无关协调合同：

`BET → Workflow run → WorkPacket/hash → assignment → external task → EvidenceRecorded → independent VerificationReceipt → WorkflowVerified`

Kandev 当前只有离线 fixture adapter，所有 live `dispatch/observe/interrupt` 都稳定返回 `not_enabled`。
Orca、Multica、Ruflo 或其他控制面后续只需要实现相同四函数边界，不获得完成判定权。

OMO 子仓交付经 [PR #35](https://github.com/starlink-awaken/omostation-omo/pull/35) 合并为
`217bb47d817f3fe5259d43b2d073515001a47f8f`，并以
`bet/BET-Y1Q2-T1-14-omo-20260813` 固化。平台 CI 的 lint、test、test-cov 全部通过。

## Q1 实际耗时 vs appetite？

约半天，符合 1 day appetite。实现本身很快，主要时间用于两轮红队审查和递归修复 OMO 独立 CI，
避免把本地兄弟仓可见的绿灯误当成独立仓可复现。

## Q2 done_when 是否全部通过？

5/5 通过。新增合同测试 30 条；OMO 完整独立 CI 等价命令为 1347 passed、202 skipped、0 failed；
平台 lint、test、test-cov 全绿；ECOS 既有 WorkPacket/CompletionManifest/VerificationReceipt 合同回归
105 条通过。独立 reviewer 最终 CLEAR。

负向证据覆盖 packet hash 篡改、changed path 越界、重复/冲突 manifest、transport failure、收据对象
构造后篡改、跨 workflow/assignment/BET/step 重放以及 verified 后变更候选。上述路径均不产生虚假
`WorkflowVerified`。

## Q3 与计划不符的事实

1. ECOS 的三类合同早已存在；本轮正确动作是复用和接线，不是按蓝图文字重新建模。
2. OMO CI 固定在旧 ECOS `64a3b418`，导致 main 连续五次无法导入已上线的 `ActionReceipt`；本轮将其
   固定到远端 main 的可达 SHA `3d252996`，同时覆盖新增 WorkPacket 编译器依赖。
3. 新 worker admission gate 让旧 dogfood fixture 缺少 capabilities 后失败；补的是 fixture 真实声明，
   没有放宽生产门禁。
4. observability 测试在 CI 的 `uv run --no-project` 内再次执行 `uv run omo`，错误解析不存在的兄弟仓；
   改为当前受控 Python 进程调用公开 CLI。
5. standalone OMO CI 不具备外层 Workspace `.omo/projects`，因此 Workspace 拓扑断言明确 skip；生产路径
   推导和根仓集成行为未放宽。

## Q4 净增减与必要性

新增一个 OMO 协调模块和一组合同测试；没有新数据库、状态机、CLI、UI、scheduler 或控制面真相。
额外修改四个 CI/测试文件，都是平台实跑暴露的独立仓可复现缺口。代码量偏大，主要来自明确的身份链、
错误族和对抗性回归；MVP 没有抽象第二层框架。

## Q5 后续提示

下一步优先让一个真实编排器（首选 Kandev 小试点，Orca 保持执行适配器）消费本合同，验证
`dispatch/observe/interrupt/collect` 的 canonical receipt；仍以 Workspace WorkPacket、OMO Mesh 与独立
VerificationReceipt 为唯一完成真相。不要把 Kandev/Ruflo/Multica 的 UI completed、worker exited 或日志
结束直接映射成 `WorkflowVerified`。
