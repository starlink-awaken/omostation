---
schema_version: governance-waiver/v1
created: '2026-09-23'
bet_id: unbound
run_id: 20260923T020707Z-governance-state-mutation-c014d723
scope: a4-clash-fleet-cf-known-orphans
---

# Waiver · A4 known_orphans 追加 fleet-watch.sh 与 refresh-cf-ips.sh

## 背景

A4 scheduler gate 报出 2 个新 crontab 孤儿（2026-09-23 安装，属用户 Clash
维护套件持续扩展，与 #4215/#4220 同一模式）：

- `41 * * * * ~/.local/bin/fleet-watch.sh`（8 机 SSH 探活 + 告警/恢复，状态机首见记基线）
- `7 3 * * * ~/.local/bin/refresh-cf-ips.sh`（CF 优选 IP 腐化报告，脚本自述 report-only 不改配置）

## 核验证据

- `fleet-watch.sh` → symlink `~/.config/clash/repo/scripts/fleet-watch.sh`，
  与已白名单 clash-* 同仓同源；只读探测 + 本地通知，不触碰工作区状态。
- `refresh-cf-ips.sh` 脚本实体在 `~/.config/clash/repo/scripts/`，头部注释
  明确 "report-only, 不改配置"；其 crontab 行曾短暂安装（meta-doctor 报
  dead_ref：`~/.local/bin/refresh-cf-ips.sh` 不存在）且已在 2026-09-23 被
  用户移除。本白名单行为防复发登记，**不代表该 job 已安装或可运行**；
  主机 personal 目录（symlink/crontab）不由 agent 改动。

## 处置

`.omo/cron/registry.yaml` known_orphans 追加 2 行。验证（#4220 基线）：

- 变更前: `{"ok": false, "drift_count": 0, "orphan_count": 1, "known_orphan_count": 8}`
  （唯一未豁免孤儿为 fleet-watch.sh；refresh-cf-ips 行彼时已被用户移除）
- 变更后: `{"ok": true, "drift_count": 0, "orphan_count": 0, "known_orphan_count": 9}`

## bet 绑定说明

台账 444 条全部 done，无在途 bet；与 waiver-2026-09-22-a4-clash-known-orphans.md
同模式，经用户 2026-09-22 授权链执行，`AGCP_REQUIREMENT_ITERATION_GATE=0` 记录性豁免。
