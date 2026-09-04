---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-12 复盘
type: retro
---

# BET-Y1Q2-T1-12 复盘

## 交付与真实回执

Pi 0.84.1 已从候选提升为受限的 L0 `reasoning/verification` worker。正式验证不是直接跑
CLI，而是使用既有任务与准入链：

`WorkflowRequested → WorkflowAdmitted → StepDispatched → OMO dispatch → Pi adapter → AetherForge → omlxc/coding`

真实模型调用返回精确 marker：

```text
OMO_WORKER_DISPATCH_OK:pi:BET-Y1Q2-T1-12
```

脱敏回执摘要：

```json
{
  "outcome": "succeeded",
  "worker": "pi",
  "provider": "omlxc",
  "model": "coding",
  "route_ref": "bos://compute/aetherforge/infer",
  "duration_seconds": 2.998,
  "checks": {
    "aetherforge_health": true,
    "child_reaped": true,
    "session_persisted": false,
    "temp_cwd_unchanged": true,
    "temp_removed": true,
    "tools_enabled": false,
    "user_config_unchanged": true
  }
}
```

Canonical receipt SHA-256 为
`3185833834b6e62a1828b8d468154372d60dc223ce1a285aa81b599fd2ba3028`；stdout digest 为
`c25099daa48f9fad68f177a748073a1f176600ab31a60bcc454fcb3656ba13c6`。Prompt、模型原文、
本机身份、凭证与用户配置原文均未持久化。主 Workspace `.omo` 前后未变化，试验临时根已删除。

## Q1 实际耗时 vs appetite？超出比例？

约一天，符合 1 day appetite。主要耗时用于把“CLI 能运行”提升为“正式派工不会越权”：补齐
operation level、write scope、capability、工作目录、坏模板、非零退出与持久化命令脱敏门禁。

## Q2 done_when 是否全部通过？哪条没过，为什么？

6/6 通过。根 adapter 定向 34 tests 通过；OMO worker/MCP/lifecycle 定向 48 tests 通过，只有
1 条既有 CLI deprecation warning；Ruff 与 `git diff --check` 通过；独立 reviewer 给出 CLEAR。

本 BET 没有伪造 `WorkerAcknowledged`、`EvidenceRecorded`、`WorkflowVerified`、
`WorkflowClosed`。Pi 是同步 CLI，当前 adapter receipt 也不是 external receipt schema；强行补齐会把
“进程结束”冒充“完整任务闭环”。这部分若有真实需求，应另开窄 BET。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. `pi --offline` 只禁目录/版本刷新，不代表模型离线；真正的模型请求仍进入本机 AetherForge。
2. 只把 worker 标成 admitted 不够：原 dispatch 没有在工件写入前强制 operation level、write scope
   和 capability，存在“拒绝了但已污染运行态”的风险。
3. 相对 adapter 路径依赖调用 cwd；MCP、promotion 与 direct dispatch 必须统一解析受管 Workspace。
4. 仅用 `allowed_operation_level or risk_level` 会产生降级旁路，必须取两者的较高风险。
5. capability 字段缺省或类型错误不能静默兼容 Pi；最终通过 `require_explicit_capabilities` 对 Pi
   严格执行，同时保留 legacy worker 的兼容边界。
6. 保存实际绝对 launch argv 会泄露用户名和本机路径；运行时用绝对路径，持久化证据改用
   `<workspace_root>` 占位符。

## Q4 净增减与必要性

新增 1 个 bounded adapter、1 个根测试面；OMO 在既有 worker dispatch/core/promotion/MCP 上补
通用准入策略与回归测试；更新 1 个 worker SSOT、1 份协作标准与本复盘。没有新增第二个任务、
worker、模型路由或 receipt truth。

必要性：adapter 负责 Pi 进程与本地算力物理边界；OMO 负责 worker 是否有权执行。两者职责不同，
不能由 prompt 约束替代。

## Q5 下一个认领本 track 的 agent 需要知道什么？

下一步串行验证 Oh My Pi，不与 Pi 同时扩权。Oh My Pi 必须复用同一准入策略和 AetherForge/omlxc
算力边界，但它没有 Pi 的 `--offline`，也不能照抄参数；先做独立 bounded adapter 与真实回执，成功
后才从 declared 晋升。Grok、MiMo、AGY、OpenCode、Kilo 继续保持 disabled/declared。

全仓台账 lint 仍有 25 个既有 T6 条目问题；OMO 全量 CI 仍受默认分支所钉 ECOS 缺
`ActionReceipt` 的既有基线影响。这两项与本 BET 定向实现分开报告，不冒充全仓绿色。
