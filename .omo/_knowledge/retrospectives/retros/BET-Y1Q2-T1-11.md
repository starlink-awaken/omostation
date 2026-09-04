---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-11 复盘
type: retro
---

# BET-Y1Q2-T1-11 复盘

## 交付与真实回执

固定版本 `kandev@0.87.1` 完成真实本地生命周期：headless 控制面在
`127.0.0.1` 健康，监听归属于本次 marker 进程树，终止后 launcher、重挂父进程的后代、
进程组和端口全部清零；未创建 Kandev task/agent/model，也未写 Workspace。

脱敏回执摘要：

```json
{
  "assertions": {
    "agent_spawned": false,
    "model_called": false,
    "task_created": false,
    "workspace_written": false
  },
  "checks": {
    "child_reaped": true,
    "health": true,
    "listener_loopback": true,
    "listener_released": true,
    "owned_processes_released": true
  },
  "duration_seconds": 39.249,
  "outcome": "succeeded",
  "package": {"name": "kandev", "version": "0.87.1"}
}
```

原始 canonical receipt 留在系统临时目录、不作为项目真相；SHA-256 为
`14eef19650d3e309b5d14fa23af098573f7dc7c299dc15e0d795090fc619b18b`。
独立红队复现了 launcher 早退、child `setsid`/re-parent 的最危险竞态并给出 `APPROVE`。

## Q1 实际耗时 vs appetite？超出比例？

约半天，未超过 1 day appetite。主要耗时不是 runner 主逻辑，而是两轮对抗审查与真实
Kandev 原生运行包的冷缓存下载。

## Q2 done_when 是否全部通过？哪条没过，为什么？

5/5 通过。固定版本、隔离 home、loopback health、listener ownership、派生进程回收、
脱敏回执、真实启动和独立 reviewer 均有可复查证据。没有创建 task/agent/model，也没有
写 Workspace 或用户级 Kandev 配置。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. Kandev 的 `npx` 启动器会拉取大型平台原生包；冷缓存时 300 秒不足，后端甚至尚未启动。
2. 只按 launcher PID/PGID 清理不可靠：子进程可以 `setsid` 后被 re-parent。最终改为一次性
   非敏感 marker 归属，并同时证明 marker 进程和监听端口归零。
3. macOS Python 的权威临时根通常是 `/private/var/folders/.../T`，不是 `/private/tmp`；安全
   receipt 校验必须使用 `tempfile.gettempdir()` 的事实，而不是 Linux 习惯。
4. 官方 CLI 文档落后于同版本源码；`--headless`、`KANDEV_NO_BROWSER`、
   `KANDEV_SERVER_HOST` 和 `KANDEV_HOME_DIR` 需要以固定版本源码复核。
5. 冷缓存真实执行在 300 秒仍处于 npm 原生包下载，诚实返回 `health_unavailable`，同时证明
   listener/process 已清理；第二次 600 秒上限内成功，事实支持可配置但有硬上限的冷启动窗口。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

本 BET 新增 1 个窄 runner、1 个测试文件、1 个证据文件、1 个复盘文件，并在既有台账新增
1 个 BET；GaC 规则和 ADR 均为 0。全仓 closeout 快照：src_loc `+143,240`、test_loc
`+65,066`、src_files `+571`、test_files `+278`、gac_rules `+0`、gac_required `+1`、
bin_scripts `+145`（相对 2026-08 基线；这是全仓累计口径，不冒充本 BET 独占变化）。

必要性：runner 只解决一个物理边界——候选控制面的真实启动与无残留退出；没有复制任务、
worker、receipt 或 verifier。后续 Kandev 不晋升时，应连同本 runner 一起退役，避免永久表面积。

## Q5 下一个认领本 track 的 agent 需要知道什么？

Kandev 目前只证明了控制面生命周期，不代表 task completed，更不代表 Workspace 交付完成。
下一步先做一个 Pi 的串行、无工具、bounded admission smoke；Kandev 只负责可撤销试点控制面，
所有验收仍回到 Workspace 的 BET/Workflow Mesh/receipt/verifier。Oh My Pi 后置，不能同时晋升。
