---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-09 复盘
type: retro
---
# BET-Y1Q2-T1-09 复盘

## 1. 实际耗时是否落在 appetite 内？

是。工作在 1 天 appetite 内完成，范围保持为一个 Orca/Crush 启动适配器、定向测试与真实无写入探针，没有修改 Orca 安装包或扩建通用编排系统。

## 2. Done when 是否全部达成？

- 已直接验证当前 Crush `v0.88.1` 支持 `--yolo`/`-y`，而 `crush '-yolo'` 会报 `Unknown shorthand flag: 'o' in -olo`。
- 适配器先验证 Orca runtime，再创建 `crush --yolo` terminal，等待 `tui-idle`，并从 terminal preview 确认 `Yolo mode!` 后才 dispatch。
- runtime、JSON、TUI、身份或 dispatch 任一失败均 fail closed；dispatch 不自动重试，存在 terminal 时返回 `residual_resources`。
- 成功回执固定为 `dispatch_injected` 与 `input_accepted=unproven`，没有把 Orca 的 injected 结果冒充模型 ACK。
- 真实探针完成了 Crush 启动、任务注入与 `worker_done` 回执，未修改工作树文件。

## 3. 哪些假设被推翻？

1. `workerStart ready` 不是 shell/TUI 已可输入。Orca 的 ready 属于调度状态，terminal input 还存在启动竞态。
2. 固定等待几秒不是可靠修复；可用的直接证据是 `tui-idle`、terminal connected/writable 与 Crush 的 `Yolo mode!` 输出。
3. `dispatch injected` 不等于模型输入已接受，更不等于任务完成。当前 Orca CLI 没有独立的 TUI input ACK，因此回执必须保留 `unproven`。
4. `-yolo` 不是当前 Crush 的合法参数；正确长参数是 `--yolo`。

## 4. 交付事实与残余风险

- 真实 E2E 的 task 与 dispatch 均完成，并收到 worker 的结构化 `worker_done`。
- 当前 coordinator terminal 没有 stable pane identity，跨上下文执行 delivery ack 返回 `stable_pane_required`；`worker-release` 也无法从非绑定 runtime context 找到已完成 dispatch。因此本轮没有用强制关闭 terminal 冒充 release，真实 terminal 被如实列为残留资源。
- 适配器只覆盖 Crush。本轮不承诺首个模型 token、跨崩溃恢复、自动 reaper、exactly-once 或其他 Agent CLI。
- D2 全仓表面积相对 2026-08 基线：`src_loc +143,481`、`test_loc +65,379`、`src_files +570`、`test_files +276`、`adr_total +30`、`gac_rules +0`、`gac_required +1`、`bin_scripts +143`、`standards +2`、`collab_scenarios -216`。这是当前全仓累计观察量，不将其冒充本 BET 的净增；本 BET staged stat 为 5 个文件、约 700 行，主要来自启动状态机及其行为测试。

## 5. 下一位 Agent 最需要知道什么？

继续扩充 Agent 池时应复用同一个生命周期合同：`runtime ready → terminal/TUI ready → process identity → one dispatch → worker receipt → verified delivery`。每个 CLI 都必须提供自己的 readiness 证据和合法 argv，不能把 Orca 的通用 ready 当作统一证明。配额与模型路由应在后续独立 BET 中接入 CodexBar、动态调度器、omlxc/AetherForge 及 provider/worker registry，不能塞进这个窄修复。
