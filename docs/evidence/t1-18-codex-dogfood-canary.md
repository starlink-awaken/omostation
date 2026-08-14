---
status: experimental
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-13
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
    - `controller approval` 与 provider approval 分离，provider approval 的来源是同一
      Orca terminal 的手点确认。

### 验收检查命令（静态校验）

- `rg -n "Clone identity and worker identity are separate\\." docs/evidence/t1-18-codex-dogfood-canary.md`
- `rg -n "Transport input acceptance is not task completion\\." docs/evidence/t1-18-codex-dogfood-canary.md`
- `rg -n "Repository writes require explicit human confirmation in the Codex TUI\\." docs/evidence/t1-18-codex-dogfood-canary.md`

### 说明

该文件当前记录的是边界事实，不新增任务状态机定义，不承诺 `task` 已闭环，
也不代替 `WorkflowSucceeded` / `WorkflowVerified` 的执行证据。
