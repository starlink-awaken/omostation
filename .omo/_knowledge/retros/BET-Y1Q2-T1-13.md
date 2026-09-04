---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-13 复盘
type: retro
---

# BET-Y1Q2-T1-13 复盘

## 交付与真实回执

Oh My Pi 16.1.16 已从候选提升为受限的 L0 `reasoning/verification` worker。正式验证复用
现有任务、准入和派工链：

`WorkflowRequested → WorkflowAdmitted → StepDispatched → OMO dispatch → OMP adapter → AetherForge → omlxc/coding`

正式调用返回精确 marker：

```text
OMO_WORKER_DISPATCH_OK:oh-my-pi:BET-Y1Q2-T1-13
```

脱敏回执摘要：

```json
{
  "outcome": "succeeded",
  "worker": "oh-my-pi",
  "provider": "omlxc",
  "model": "coding",
  "route_ref": "bos://compute/aetherforge/infer",
  "checks": {
    "aetherforge_health": true,
    "child_reaped": true,
    "session_persisted": false,
    "temp_removed": true,
    "tools_enabled": false,
    "user_config_unchanged": true
  }
}
```

正式 canonical receipt SHA-256 为
`dc86dc1543f39b47c6e7d5cb4e6b06597cdac6359ba96dd6840180d28e3d1518`；stdout digest 为
`10b6d789fdbb4946fcba59b4bd7e1d5109e9d6113c6df61e0ae1b32d12f250d3`。事件顺序、空写路径、
禁止仓库写入的 prompt 和 `dispatch_state=active` 均已实测。临时 Workspace 与 adapter trial 均已删除。

## Q1 实际耗时 vs appetite？

约半天，符合 1 day appetite。主要耗时不是“让 OMP 能答一句话”，而是收口 CLI 版本、配置事实、
凭证身份、进程清理和本地模型路由，避免把裸 CLI 成功误判为受治理 worker 准入。

## Q2 done_when 是否全部通过？

5/5 通过。adapter 与 Pi registry 回归 94 tests 通过；Ruff、Python compile、`git diff --check`
通过；两轮独立 reviewer 最终均为 CLEAR。正式 smoke 与 OMO dispatch smoke 均调用真实
`omlxc/coding`，没有 mock 模型、provider 或 OMO dispatch。

本 BET 不伪造 `WorkerAcknowledged`、`EvidenceRecorded`、`WorkflowVerified` 或
`WorkflowClosed`。OMP 当前是同步 CLI transport；完整 Mesh closeout 若产生真实需要，应另开窄 BET。

## Q3 与计划不符的事实

1. 本机同时存在 OMP 16.1.16 与 17.2.15；本轮必须固定 Agent Pool 已观察的 Bun 16.1.16，不能跟随 PATH 漂移。
2. OMP 的权威模型配置是 `models.yml`，`models.json` 只是兼容面；两者存在时必须核对受审字段一致。
3. 当前配置以精确环境变量 `AETHERFORGE_API_KEY` 引用凭证，而非旧 Keychain command。adapter 只接受
   这个精确 identity 或精确 `aetherforge-gateway` Keychain command，并在父进程用 `shell=False` 解析。
4. OMP 没有 Pi 的 `--offline`；因此不能宣称离线，只能诚实声明模型请求固定经 loopback AetherForge。
5. 首轮 marker probe 失败会把 PGID 0 当进程组，存在误杀 workflow runner 的风险；红队发现后改为
   类型化 unavailable、危险 PGID 双层过滤和 fail-closed。
6. OMP 会在隔离临时树创建数据库/缓存；正确边界是“所有写入只在 trial 且最终删除”，不是假装零运行态写入。

## Q4 净增减与必要性

新增 1 个 OMP bounded adapter 和 1 个专测面；只更新 worker SSOT、Pi 的 admitted 集合回归、协作标准
与本复盘。没有修改 OMO 内核、AetherForge、omlxc、用户 OMP 配置或 provider registry，也没有抽取
不成熟的通用多 CLI adapter。

## Q5 后续提示

OMP 当前仅允许显式 `reasoning/verification`、L0、`write_scope:none`。不要凭这次成功给它代码修改、
工具或 L1 权限。下一步应回到多 Agent 协作合同和真实个人场景，不再连续堆 CLI 准入；OpenCode、Grok、
MiMo、AGY、Kilo 等仍保持 declared/disabled，只有出现明确任务收益时才做各自的真实回执和晋升。
