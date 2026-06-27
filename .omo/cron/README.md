# Cron 治理定时任务索引

> GaC 统一治理 cron 调度 + 散落 cron 职责梳理 (深化3 收编)

## cron 清单 (6 套 + GaC 统一)

| cron | 职责 | 频率 | GaC 关系 |
|------|------|------|---------|
| **gac-crontab** | GaC 体系 (radar/validate/healthcheck/legacy-drift/gc) | daily/weekly | **统一入口** |
| governance-crontab | X1-X4 检查 (x1-x4-check.sh) + debt-audit + dashboard 生成 | daily/weekly/monthly | 部分重叠 (GaC indexed X1-X4 policy) |
| governance-agent-crontab | omo governance-agent 调度 | 6h | 独立 (agent 运行时) |
| governance-dashboard-crontab | governance-dashboard + gov-trend 报告 | daily/weekly | 独立 (仪表盘生成) |
| x2-freshness-crontab | x2_freshness_audit (cross-lint/debt-evidence/mof-bump) | daily/weekly/monthly | 部分重叠 (GaC indexed X2-FRESH-*) |
| opc-closeout-crontab | OPC P5-P7 (radar/weekly-loop/drift-detector/self-evolve/release-cycle/audit-rollout/doc-lint) | daily/weekly | 独立 (OPC 生命周期) |

## 安装 (按需)

```bash
# GaC 体系 (推荐先装, 治理核心)
crontab .omo/cron/gac-crontab

# X1-X4 检查 + 债务审计 (和 GaC indexed 部分重叠, 互补)
crontab .omo/cron/governance-crontab

# X2 抗熵 freshness (和 GaC indexed X2-FRESH-* 部分重叠)
crontab .omo/cron/x2-freshness-crontab

# OPC 生命周期 (独立, P5-P7 闭环)
crontab .omo/cron/opc-closeout-crontab

# 查看: crontab -l | grep -E "gac|governance|x2|opc"
```

## 重叠标注 (未来统一执行路径)

GaC indexed 已收敛 X1-X4 policy (25) + X2-FRESH-* (13) 规则到统一注册表.
当前 governance-crontab (x1-x4-check.sh) + x2-freshness-crontab (x2_freshness_audit.py)
**仍独立执行** (跑实际脚本), GaC 是**注册层** (不替代执行).

**未来统一**: gac-executor 消费 GaC 规则 executor 字段后, 可统一调度
(X1-X4/X2-FRESH 规则经 GaC 路由到 omo_audit/x2_freshness_audit), 届时
governance-crontab + x2-freshness-crontab 可合并进 gac-crontab.

当前保留各自 cron (执行实际脚本, 防合并破坏定时检测).

## 废弃

- `crontab-backup-` (0 字节空文件, 已删)

---

*cron 索引 v1 · 2026-06-27 · 深化3 收编 (文档统一 + 重叠标注, 不破坏实际 cron)*
