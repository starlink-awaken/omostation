---
title: 单机灾难恢复清单 (OPS-INFRA 任务 4)
type: audit
owner: governance-agent
created: 2026-08-17
bet: BET-Y1Q1-T6-08
related:
  - docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md
  - docs/operations/hermes-governance-boundary.md
last_updated: 2026-08-25
lifecycle: history
---

# 单机灾难恢复清单（"这台 Mac 明天全损会丢什么"）

实测基础：2026-08-17 本机直读。

| 资产 | 规模 | 备份现状 | 恢复难度（若盘毁） |
|---|---|---|---|
| **Hermes 调度定义** `~/.hermes/` | 3.0G（含 cache/audio_cache） | **无异地备份**（核心是 `cron/jobs.json` + `conf/`，MB 级） | **难**：12 任务定义需凭记忆重写；executions.db 历史永久丢失 |
| **crontab** `crontab -l` | ~20 行（3 域混布：Workspace/卫健委/coordination） | **部分**：仓内有历史快照 `.omo/cron/`（含 07-03 归档 + opc-closeout-crontab），但**非每日快照**——最近增量（如 08-15 加的 coordination-backup 行）不在任何仓内副本 | **中**：以仓内快照为基线 + 手工补近期 diff |
| **launchd plist** `~/Library/LaunchAgents/` | 28 个（active，另有 bak/disabled） | **仓内仅 2 个 .plist 入库**（agent-tick-daemon 等） | **难**：~26 个活跃 plist（aetherforge.gateway / l4.governance.watch / 各 agent 守护）需逐个重建，参数含绝对路径与 env，凭记忆不可靠 |
| **共享运行时状态** `~/agents/_shared/runtime/coordination.sqlite3` | claims 70 行 | **有**：crontab 08:30 日备 N=3（.bak.1/2/3 实测在）——但备份与主库**同盘**，盘毁同灭 | **不可恢复**（仅丢 claims 状态，agent 可重认领，影响可控） |
| **Workspace 仓库** | — | GitHub remote（多子仓各有 remote） | **易**：clone 即回 |
| **未同步运行时** `.omo/state/*.jsonl` 等 | 心跳/信号流水 | 同盘仅存 | **部分丢**：感知历史断档，无结构性损失 |

## 风险敞口结论

真正的单点险按序：① launchd 26 个未入库 plist（重建最痛）② Hermes jobs.json（12 任务重写）
③ crontab 快照滞后。**建议排期**（本轮不执行）：
1. 一日速赢：launchd plist + crontab + hermes jobs.json 三件快照脚本并入已有
   coordination 日备 cron（同一 08:30 行扩展，写 `~/agents/_shared/backups/` 再 rsync 到
   Workspace gitignored 目录 + Time Machine 覆盖）
2. Hermes 3.0G 中的 cache 类（audio_cache/cache）可排除，核心定义 <50MB
3. 与 ADR-0414 PARKED-DEFERRED 衔接：物理多机 deferred 期间，本清单即灾备基线文档
