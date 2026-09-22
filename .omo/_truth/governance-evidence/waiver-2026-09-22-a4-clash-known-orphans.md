---
schema_version: governance-waiver/v1
created: '2026-09-22'
bet_id: unbound
run_id: 20260922T110409Z-governance-state-mutation-2e280d04
scope: a4-clash-known-orphans
---

# A4 scheduler gate — 外部 clash-* 主机 cron 登记 unbound-start waiver

A4 调度声明↔安装一致性门 FAIL：`scheduler-compile.py --check` 报告
`orphan_count=6`。六条孤儿 crontab 全部指向 `~/.local/bin/clash-*.sh`
（`clash-health.sh`、`clash-proxy-guard.sh`、`clash-traffic.sh`、
`clash-cert-check.sh`、`clash-bw-warn.sh`、`clash-git-sync.sh`），
实际内容为 `~/.config/clash/repo/scripts/` 下的 61-66 字节 shim，
不含任何 `/Users/xiamingxing/Workspace` 引用。属用户本机外部工具，
与本仓已登记的 `clash-probe.sh`（2026-09-20 确认）同源同族。

本事务无对应台账 BET，按仓内先例（`clash-probe.sh` / `mimo-models-sync.sh`
的 known_orphans 登记）以一次性 `AGCP_REQUIREMENT_ITERATION_GATE=0`
前缀完成 unbound governance-state-mutation start，见 PITFALL-GAT-009。

写入面：
- `.omo/cron/registry.yaml` — `known_orphans` 追加六条，附外部工具确认注释。
- 本 waiver。

验证：
- `python3 bin/scheduler-compile.py --check --json` 由
  `{"ok": false, ..., "orphan_count": 6}` 变为
  `{"ok": true, "drift_count": 0, "orphan_count": 0, "known_orphan_count": 7}`。
- 未改动任何 crontab、调度定义或治理队列；fail-closed 语义保持。

范围外：A9 `cockpit_sources`（zhixing-dashboard 采集器执行根缺陷）
属 BET-Y2Q2-T10-155 独立 lane，不在本事务内。
