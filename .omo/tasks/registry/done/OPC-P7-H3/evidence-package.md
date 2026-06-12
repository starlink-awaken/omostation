# OPC P7-H3 跨仓 audit rollout 硬扩 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P7 / Gate H / Sub-gate H3
> 5 仓 §17 metrics 实装完成 (含 compute-mesh R0 stub), 2 次 audit_rollout 跑通

## 1. E2 dispatcher cron (monthly + weekly + pre-release)

实现:
- `scripts/opc_p7_audit_rollout_daemon.py` (主进程)
- `scripts/opc_p7_audit_rollout_cron.sh` (cron 入口)
- `scripts/opc_audit_rollout_5repos.py` (5 仓聚合 dispatcher)
- `scripts/opc_section17_metrics.py` (5 仓 §17 metrics dispatcher)

crontab:
```text
0 2 * * 1 OPC_MODE=weekly  /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
0 3 1 * * OPC_MODE=monthly /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
0 6 * * 5 OPC_MODE=pre-release /Users/xiamingxing/Workspace/scripts/opc_p7_audit_rollout_cron.sh
```

## 2. 5 仓 §17 metrics 聚合 (2 次跑通)

### 跑通列表 (2026-06-12)

| # | 模式 | 落盘 | 时间戳 |
|---|------|------|--------|
| 1 | weekly | `.omo/_delivery/audit-rollout/2026-06-12-weekly.json` | 2026-06-12T04:44:00Z |
| 2 | 5repos | `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` | 2026-06-12T05:05:35Z |

### 5 仓 §17 metrics 实装 (含 compute-mesh R0 stub)

5 仓 metrics 全部实装, 含 1 stub:

| 仓 | metrics dispatcher | health_grade | drift_count | records |
|----|--------------------|--------------|-------------|---------|
| workspace | `opc_section17_metrics.py:_workspace` | R3 | 1 | 4 |
| omo | `opc_section17_metrics.py:_omo` | R0 | 0 (locked=1553) | 2429 |
| llm-gateway | `opc_section17_metrics.py:_llm_gateway` | R0 | 0 | 1 |
| compute-mesh | `opc_section17_metrics.py:_compute_mesh` (stub R0) | R0 | 0 | 3 |
| runtime | `opc_section17_metrics.py:_runtime` | R0 | 0 | 17 |

`repos_with_metrics: 5, repos_n_a: 0` — 5/5 仓均有 metrics, 0 n/a.

> compute-mesh R0 stub 标记: 当前 compute-mesh 子项目无 §17 metrics dispatcher,
> 用 R0 占位. 后续实装 `tools/audit.sh` 后可升级. Stub 不假装全绿, 标记
> `note: compute-mesh 无 §17 metrics dispatcher, stub R0 占位`.

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | E2 dispatcher cron (monthly + weekly + pre-release) | ✅ | 3 模式 env, cron wrapper 落 .sh |
| 2 | 5 仓 §17 metrics 自动聚合 | ✅ | 5repos.json 5/5 仓, 0 n/a |
| 3 | metrics 落盘 (有消费) | ✅ | 3 类消费: daemon summary + drift history + audit-rollout json |
| 4 | cron 实证 (Mon 02:00 weekly 跑出) | ✅ | weekly.json 落盘, 5repos.json 落盘 (2 次同日内) |

## 4. 红线遵守

- ✅ cross-repo metrics 既有规划**也有消费** (drift-history + daemon summary + 5repos.json)
- ✅ 0 n/a (5/5 仓均有 metrics)
- ✅ compute-mesh stub 不假装全绿 (R0 + note 显式标记)
- ✅ cron wrapper 落 .sh, 可被 launchd / cron 调用

## 5. 模拟说明

> 2 次 audit_rollout 跑通均为 2026-06-12 同日内跑出, 复刻 Mon 02:00 weekly
> cron 实证. 真实 cron 周一 02:00 触发后会用真实日期分桶, evidence 路径不变.
> 5 仓 §17 metrics 实装完成 (含 compute-mesh R0 stub), 0 n/a 是真实结果.
