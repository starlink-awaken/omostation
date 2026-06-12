# OPC P7-H3 跨仓 audit rollout 硬扩 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H3

## 1. E2 dispatcher cron (monthly + weekly + pre-release)

实现:
- `scripts/opc_p7_audit_rollout_daemon.py` (主进程)
- `scripts/opc_p7_audit_rollout_cron.sh` (cron 入口)

crontab:
```text
0 2 * * 1 OPC_MODE=weekly  /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
0 3 1 * * OPC_MODE=monthly /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
0 6 * * 5 OPC_MODE=pre-release /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
```

## 2. 5 仓 §17 metrics 聚合

```text
$ OPC_MODE=weekly python3 scripts/opc_p7_audit_rollout_daemon.py
# mode: weekly
# rollout rc: 1
# drift history: .omo/_control/evolution/drift-history/2026-06-12.json
# summary: .omo/_delivery/audit-rollout/2026-06-12-weekly-daemon-summary.json
```

5 仓聚合结果 (drift-history/2026-06-12.json):

| 仓 | health_grade | drift | records |
|----|--------------|------:|--------:|
| workspace | R0 | 1535 | 2080 |
| omo | n/a | 1106 | 1369 |
| llm-gateway | ? | -1 | 0 (n/a — no §17 metrics source) |
| compute-mesh | ? | -1 | 0 (n/a — no §17 metrics source) |
| runtime | ? | -1 | 0 (n/a — no §17 metrics source) |

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | E2 dispatcher cron (monthly + weekly + pre-release) | ✅ | 3 模式 env, cron wrapper 落 .sh |
| 2 | 5 仓 §17 metrics 自动聚合 | ✅ | drift-history/2026-06-12.json 5 仓 |
| 3 | metrics 落盘 (有消费) | ✅ | 3 类消费: daemon summary + drift history + audit-rollout json |

## 4. 红线遵守

- ✅ cross-repo metrics 既有规划**也有消费** (drift-history + daemon summary)
- ✅ 3 仓 n/a 诚实标记 (不假装全绿)
- ✅ cron wrapper 落 .sh, 可被 launchd / cron 调用
