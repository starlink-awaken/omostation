---
schema_version: governance-waiver/v1
created: '2026-09-23'
bet_id: unbound
run_id: 20260923T011708Z-governance-state-mutation-c19e4d02
scope: a4-clash-node-watch-known-orphan
---

# Waiver · A4 known_orphans 追加 clash-node-watch.sh

## 背景

A4 scheduler gate (`bin/scheduler-compile.py --check`) 在 2026-09-22 报出新孤儿：
crontab 安装了 `23 * * * * /Users/xiamingxing/.local/bin/clash-node-watch.sh`，
但该条目未登记进调度 SSOT，也不在 `known_orphans` 白名单。

## 核验证据

- `/Users/xiamingxing/.local/bin/clash-node-watch.sh` → symlink 指向
  `~/.config/clash/repo/scripts/clash-node-watch.sh`，与已白名单的 6 个
  clash-* 脚本同一来源目录，属用户本机 Clash 代理维护工具套件（外部工具，非工作区调度资产）。
- 脚本内容审阅：只读探测节点连通性 + 本地/TG 通知，明确注释"勿调密"防 GFW 干扰；
  不读写工作区任何状态文件。
- 安装时间 2026-09-22 19:46，晚于 #4215（同日 11:4x UTC 合并）白名单基线，属自然增量。

## 处置

`.omo/cron/registry.yaml` known_orphans 追加一行 `clash-node-watch.sh`，
注释口径与同套件条目一致。验证：

- 变更前: `{"ok": false, "drift_count": 0, "orphan_count": 1, "known_orphan_count": 7}`
- 变更后: `{"ok": true, "drift_count": 0, "orphan_count": 0, "known_orphan_count": 8}`

## bet 绑定说明

本事务不涉及任何 bet 交付数据，为治理数据面增量白名单维护，
经用户 2026-09-22 授权链（"我给你授权，推进吧" + 常驻 PR 合并授权）执行，
与 waiver-2026-09-22-a4-clash-known-orphans.md 同模式。
