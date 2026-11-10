---
schema_version: specification/v1
spec_version: 1.0.0
title: TASK-EEF1CEDC mini Cron 主机别名
bet_id: BET-Y2Q4-T10-344
owner: governance-team
status: accepted
lifecycle: contract
---

现有 Cron registry 的 `work-agent-respire-mbp-watchdog` 仅列出 `mini`。同一台 mini 在现场也以 `Mac-mini` 标识。编译与安装预览应使用同一主机作用域，在两个已登记别名下各选择一次既有看护条目。仅更新该 registry 条目的别名及说明，并用现有两个测试模块验证。

实施允许写入的三个路径：

- `.omo/cron/registry.yaml`
- `tests/test_scheduler_compile.py`
- `tests/unit/gac/test_install_cron_plane.py`

离线验收覆盖原生主机名 `Mac-mini`、`mini`、`mbp`、未知主机，以及 `Mac-mini` 被显式覆盖成 `mbp` 或 `mini`、未知主机被显式覆盖成 `mini`。核对编译、安装预览和缺项报告，保持现有 launchd 段、任务命令、频率和解释器。独立验证者核对三路径差异和证据。

实施前，owner 核对 TASK-EEF1CEDC、其尚有效的批准、最终 BET 身份、本 Spec 的接受记录及原生编译的 WorkPacket。三个路径逐条经现有 affected graph receipt 与原生 claim。发生范围冲突、工作区状态变化或审批过期即停止。计划行中的 `accepted_specifications` 绑定本 Spec 的版本与实际摘要。

本阶段停止于离线实现和独立验证。Cron 安装、运行态修改、提交、tag、发布、合并和正式收口需要各自的授权。
