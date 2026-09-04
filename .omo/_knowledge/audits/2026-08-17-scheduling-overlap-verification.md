---
title: 三处调度重叠核实报告 (OPS-INFRA 任务 2)
type: audit
owner: governance-agent
created: 2026-08-17
bet: BET-Y1Q1-T6-08
related:
  - docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md
last_updated: 2026-08-25
lifecycle: history
---

# 调度重叠核实（宿主机实测 2026-08-17，本机终端权限可用）

## ① 治理审计三重复（Hermes 07:00 / crontab 09:05+09:10 / launchd 每小时）

| 通道 | 实测 | 干什么 |
|---|---|---|
| Hermes `omo-governance-audit` 07:00 | jobs.json 确认在册 | Hermes 内置 audit 任务（产出 `~/.hermes/cron/governance.jsonl`） |
| crontab 09:05/09:10 | `crontab -l` 确认 | `bin/governance-evolution.py status/packages --json` → `runtime/cron/operating-rhythm-daily.log`（664KB 活跃，最后写入 08-17 09:10） |
| launchd `com.omostation.governance-scanner` 每小时 | `launchctl list` 确认（PID `-`，上次退出 0） | 周期扫描 |

**结论：非重复，是三层不同职责**——Hermes 是引擎侧 audit、crontab 是 roadmap 进化状态投影、
launchd scanner 是 CI 级巡检。产出各自独立落盘（governance.jsonl / operating-rhythm-daily.log /
scanner 状态），无相互覆盖路径。**建议：保留，无需合并**；唯一成本是三处时间错峰（07/09/每小时），
恰好构成串行流水，可接受。

## ② 漂移检测两重复（Hermes 05:00 / crontab 周一 10:05）

| 通道 | 实测 |
|---|---|
| Hermes `omo-drift-detection` 05:00 | jobs.json 确认在册 |
| crontab 周一 10:05 `bin/mof-drift` | 确认 → 实际路径 `bin/mof/mof-drift`（crontab 写的 `bin/mof-drift` **不存在**，见下） |

**结论：部分重叠 + 发现一处静默失败**——crontab 行 `cd ~/Workspace && bin/mof-drift`：
`bin/mof-drift` 不存在（真实位置 `bin/mof/mof-drift`）。cd 后相对路径解析失败，
**该每周巡检自 crontab 写入起每次失败**，输出进 weekly.log 被吞。建议：crontab 改
`bin/mof/mof-drift` 或移除该行让 Hermes 05:00 全责（两者检测面待比对，倾向后者——
同机同仓双份 drift 无增益）。

## ③ cron-daily-dashboard 静默失败（11+ 天，最高优先级发现）

- crontab 08:30 每日跑 `bash bin/gac/cron-daily-dashboard.sh` → `runtime/logs/governance-dashboard-cron.log`
- **脚本不存在**：`ls bin/gac/cron-daily-dashboard.sh` → No such file
- **git 全历史零痕迹**：`git log --all -S 'cron-daily-dashboard'` 零命中——该脚本**从未入过仓**（不是被删，是 crontab 引用了一个只在本机存在过/从未存在过的文件）
- **失败实证**：cron.log 尾部连续 `bash: bin/gac/cron-daily-dashboard.sh: No such file or directory`
- **影响时长**：`.omo/_delivery/dashboard/` 最后产物 **2026-08-06 09:56**，之后零新文件
  → **每日治理快照已断流 ≥11 天，无任何告警**
- 建议（交人类二选一）：(a) 补写该脚本（10 行 bash：evidence-smoke + governance-audit
  输出重定向到 dashboard/）；(b) 移除该 cron 行。**当前 GaC 快照已有 governance-scanner
  每小时覆盖，倾向 (b) + 把 dash 需求并进 scanner**。

## 处置汇总（本轮只报告不执行）

| 发现 | 建议 | 决策者 |
|---|---|---|
| 三重审计 | 保留（职责正交） | 无需动作 |
| mof-drift 路径断 | 修路径或删行 | 人类 |
| dashboard 断流 11 天 | 删 cron 行（scanner 已覆盖） | 人类 |


## 处置落地 (2026-08-17 同日, 用户批准 F1/G1 + 备份留档)

| 项 | 决策 | 执行 |
|---|---|---|
| dashboard 幽灵 cron | **F1 删行** | ✅ crontab 已删 (改前快照: crontab-snapshot-pre-f1g1-20260817.txt) |
| mof-drift 路径 | **G1 修正** | ✅ crontab 行改 `bin/mof/mof-drift`, 周一巡检恢复 |
| 三重审计 | 保留 | 无动作 |
