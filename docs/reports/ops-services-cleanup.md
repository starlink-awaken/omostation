# BET-Y1Q4-T14 ops services 清理报告 — 注册表与现实同步

> **日期**: 2026-09-11 | **执行**: xiamingxing | **结果**: ops status missing 303 → **0** (验收线 ≤ 5)

## 1. 问题

`ops status` 显示 **303 missing / 339** (bet 立项时记录 20, 期间继续漂移)。
根因三类:

| 根因 | 数量 | 说明 |
|---|---|---|
| manual 能力注册项冒充服务 | 268 | bos.*/cli.*/工具条目, 非守护进程, ops liveness 不适用 |
| cron 注册 vs crontab 脱节 | 26 | 注册了但 crontab 无对应 job (历史 job 被移除, 注册残留) |
| signal 指向幻影路径 | 19+7 | `.omo/_delivery/<svc>/` 目录从未被写入; docker 栈未运行 |

## 2. 处置 (全部数据修正, 未重写 ops 工具)

### Pass 1: enabled 裁决 (302 disable)

| scheduler | 裁决规则 | disable |
|---|---|---|
| manual | 全部 disable (能力注册项, 非服务) | 268 |
| cron | entrypoint 文件名 / id token 在 crontab 独立词匹配, 否则 disable | 26 |
| launchd | label 无 plist 且 launchctl 未加载 → disable | 1 |
| docker | compose 栈未运行 → disable (重启由 compose 管理) | 7 |

保留 33 条: 23 launchd (plist 存在) + 4 cron (crontab 活跃) + 2 gha + 4 already-disabled。

**cron 匹配防误判措施** (调研中发现并已修):
- `omo` 子串误命中 `omostation` → 词边界正则 `(?<![\w-])ep(?![\w-])`
- entrypoint=`projects/omo` 占位写法 → 二次用 id token (cron.ssot_guardian → `ssot-guardian`) 匹配 make target
- 否定结论全部人工回查 crontab 确认

### Pass 2: 20 条 kept-enabled 的 signal 修正

| 类别 | 条目 | 新 signal | 理由 |
|---|---|---|---|
| 有真实日志 | gac.daemon_watchdog, mail.daemon, resident.sediment | `runtime/logs/*-stdout.log` | 日志存在且新鲜 |
| cron 活跃 | cron.log_rotate, ssot_guardian, ssot_sync, worktree_prune | `runtime/cron/*.log` | crontab job 真实写这些日志 |
| silent daemon | resident.heartbeat/decision/execute/monitor/event_ingest/signals/inbox/promote | `~/Library/LaunchAgents/*.plist` | 无产物可观测; plist 安装态存在, 状态诚实显示 stale |
| on_demand 工具 | omo.governor/verifier/replay/alert/status | enabled: false | 无 label 无产物, 健康由调用方 governance-orchestrator 负责 |

## 3. 结果

```
处置前:  missing 303 | healthy 4 | stale 3 | unreachable 19 | disabled 9
处置后:  missing 0   | healthy 7 | stale 14 | unreachable 2 | disabled 316
```

- **missing 0 ≤ 5** ✓ (验收达标)
- 每条 disable 带 `disabled_reason` (YAML 双引号安全), git 可回滚
- 活跃服务零删除: 23 条真实 launchd + 4 条真实 cron 全部保留

## 4. Audit trail

- 逐条裁决 JSON: 本报告同目录 `ops-disposition-audit.json` (338 条, 含 id/scheduler/enabled_before/enabled_after/action/reason)
- 处置脚本: 一次性, 未入仓 (留在 /tmp 审计), 本报告即决策文档
- 回滚: `git revert` 本 PR 单文件 (services.yaml)

## 5. 防漂移建议 (后续 BET)

1. **注册表准入闸**: 新增 scheduler=cron 条目时强制要求 crontab 存在性校验 (可在 governance-semantic-gate 加一条)
2. **signal 存在性 lint**: `bin/ops/cli.py --check-signals` 对 enabled 条目的 signal 路径做存在性 drift 检测 (类比 gen-service-configs --check)
3. **manual 类拆分**: 268 条能力注册项长期应迁出 services.yaml 到 capability registry, 根治"注册表当能力目录用"
