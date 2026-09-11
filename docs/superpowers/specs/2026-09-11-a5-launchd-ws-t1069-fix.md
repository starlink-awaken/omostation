---
schema_version: specification/v1
spec_version: 1.0.0
title: A5 残留死引用修复 — 3个 launchd 服务指向已废弃 ws-t1069 路径
bet_id: BET-Y1Q4-T10-152
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---


# A5 残留死引用修复 — ws-t1069 → Workspace

## 1. Problem

`com.omostation.resident-daemon` / `com.omostation.pipeline-morning` /
`com.omostation.tailscale-heartbeat` 三个 launchd 服务的
`ProgramArguments`/`WorkingDirectory` 全部指向
`/Users/xiamingxing/ws-t1069`——该目录真实存在但不是 git 仓库、无
`.venv`，是空壳。`resident-daemon` 因此持续 `exit 78` crash-loop（
`KeepAlive=true` 反复重启反复失败）；`tailscale-heartbeat` 因脚本路径
不存在报 `exit 127`。

真实工作区在 `/Users/xiamingxing/Workspace`，对应路径（`.venv`、
`bin/health/tailscale-heartbeat.sh`、`omo.pipeline_supervisor`、
`omo.resident.daemon`）均已核实真实存在。

## 2. Goal

把三个 plist 里的 `ws-t1069` 替换为 `Workspace`，重新加载，验证三个
服务都能正常执行（不再是之前的 crash/not-found 状态）。

## 3. Non-goals

- 不调查 `ws-t1069` 这个目录本身为什么存在、要不要删除——那是另一个
  独立问题，不在本 BET 范围
- 不修改这三个服务的业务逻辑（daemon 本身的行为、pipeline_supervisor
  的调度内容、tailscale-heartbeat 脚本内容）

## 4. Change

纯文本替换，对三个 plist 文件里所有 `/Users/xiamingxing/ws-t1069`
字符串替换为 `/Users/xiamingxing/Workspace`，无其他改动。

## 5. Acceptance

- [x] `plutil -lint` 三个文件均 OK（改动后 XML 仍合法）
- [x] `grep -l ws-t1069` 三个文件均无匹配（替换彻底）
- [x] `launchctl unload` → 编辑 → `launchctl load` → 三个服务的
  `launchctl list` exit code 均为 0（之前 resident-daemon=78,
  tailscale-heartbeat=127）
- [x] `launchctl kickstart` 强制触发后，日志里出现真实成功执行的证据
  （不是旧的 "No such file or directory"），`resident-daemon`/
  `pipeline-morning` 出现真实 PID（此前为 `-`，说明此前根本没有
  真正跑起来过）
