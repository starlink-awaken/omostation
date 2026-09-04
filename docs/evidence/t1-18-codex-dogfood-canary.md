---
status: experimental
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
type: ephemeral
---

# T1-18 Codex Dogfood Canary
Validation time: `2026-08-14 03:12:44+08:00`

## 受监督 Codex 运行边界

本文档记录了受治理运行中 Codex runtime 的边界与验收要求，仅用于监督执行面（非策略面）证明。

### 核对的三条边界（必须保留原文）

- `Clone identity and worker identity are separate.`
- `Transport input acceptance is not task completion.`
- `Repository writes require explicit human confirmation in the Codex TUI.`

### 证据映射

- `Clone identity and worker identity are separate.`
  - 来源：`docs/superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md`
    - "state model" 下明确 `worker start` 与 `interactive_session_started` 在
      分离身份绑定下进行；worker id 与 clone/assignment identity 分别记录于候选身份绑定清单。
- `Transport input acceptance is not task completion.`
  - 来源：同上第 1/3 节
    - `transport_accepted` 被定义为“仅交付数据给 transport”，`model_output_observed` 需
      额外具备 `worker_done + 非空 transcript 摘要`。
    - `state` 上 `interactive_session_started`、`ready`、`input_accepted` 仅表示运行通道层状态。
- `Repository writes require explicit human confirmation in the Codex TUI.`
  - 来源：同上第 1/3/6 节
    - `execute` 仅返回 `awaiting_human_action`，不可跳过人工点击。
    - `controller approval` 与 provider approval 分离。provider approval 必须来自当前
      用户对本次任务的明确授权，并通过同一 Orca terminal 留下可审计的一次性确认；
      不得把它扩张为永久放行。

## 自动化责任边界

自动化可以在 controller approval 已存在后校验 Task、capability、operation level、
write surface、budget 与 worker admission，冻结 baseline，创建 immutable packet 及
Orca Run/Task/Dispatch/TUI 绑定。运行结束后，自动化只能在观察到
`settled + succeeded + worker_done` 和非空 transcript 摘要时收集候选证据，并从 Git
直接测量 changed paths、hash 与 budget，编译 CompletionManifest，交由不同执行身份的
只读 verifier 复测。

自动化不得凭空代替或推断 controller approval 与 Codex provider approval。只有当前
用户明确授予本次任务的代理确认权限、clone identity 与 write surface 均已验证、审批
内容仍严格落在白名单内时，controller 才能代用户发送一次性确认；它不得选择
“don't ask again”，也不得从 `--approve-for-me`、terminal idle、`ready`、
`input_accepted` 或 transport exit 0 推断批准或完成。`Transport input acceptance is not task completion.`
因此 transport ack 只能推进到 `transport_accepted`；只有候选证据完成合同绑定且独立
验证通过后，才允许形成 `WorkflowSucceeded` / `WorkflowVerified` 证据，executor 自报
`done` 或自验均不能跨越这条边界。

本次 canary 在用户明确要求“加强自动化，别老让我操作”后，由 controller 对唯一允许的
本文件发送一次 `Yes, proceed`；未授予永久权限，且最终仍由 Git 直接测量与独立 verifier
决定是否形成 `WorkflowVerified`。

### 验收检查命令（静态校验）

- `rg -n "Clone identity and worker identity are separate\\." docs/evidence/t1-18-codex-dogfood-canary.md`
- `rg -n "Transport input acceptance is not task completion\\." docs/evidence/t1-18-codex-dogfood-canary.md`
- `rg -n "Repository writes require explicit human confirmation in the Codex TUI\\." docs/evidence/t1-18-codex-dogfood-canary.md`

### 说明

该文件当前记录的是边界事实，不新增任务状态机定义，不承诺 `task` 已闭环，
也不代替 `WorkflowSucceeded` / `WorkflowVerified` 的执行证据。
