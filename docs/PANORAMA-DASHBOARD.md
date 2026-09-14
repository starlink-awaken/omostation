---
type: ssot
owner: governance-team
last_updated: 2026-09-12
---

# 织星全景驾驶舱（Panorama Dashboard）

> BET-Y1Q4-T10-163 · 体系运行指挥台 —— 与 Serena 只读观测站（:43191）互补。
> 本文件是入口文档；运行事实以 `runtime/dashboard/data.json` 为准，不硬编码。

## 访问

```bash
python3 bin/panorama/panorama-serve.py          # 前台 → http://127.0.0.1:43910
make panorama-serve                             # 同上（Makefile 入口）
open http://127.0.0.1:43910                     # 浏览器查看
```

常驻安装（launchd，KeepAlive + 5min 自动刷新）：

```bash
cp runtime/cron/com.omostation.panorama-dashboard.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.omostation.panorama-dashboard.plist
launchctl list | grep panorama-dashboard
```

## 七大板块

| 板块 | 内容 | 数据源 |
|---|---|---|
| 体系总览 | 5+4+1+1 层、OMO 单控制面、健康 KPI | bet-ledger + gates |
| 门禁 A1–A9 | 实时 verdict / exit / 依赖边界 | gate-health-check.py |
| Agent 全景 | worktree/分支/最近活动（全 agent 可见） | git worktree list |
| 任务与里程碑 | Y1Q1→Y3H2 窗口进度、in_progress/blocked | 3y-bet-ledger.yaml |
| 运行态 | meta-doctor 摘要、launchd/crontab、调度 | meta-doctor + launchctl |
| 治理 | 本文档 + 经验入口 | docs |
| 知识入口 | 白皮书/架构/流程卡片（存在性+直达） | 文档存在性探测 |

## 边界（与 Serena 观测站分工）

- 驾驶舱 = **运行指挥台**：真实 SSOT 聚合、里程碑与 agent 可见性。
- Serena（:43191）= **外部证据观测**：digest-bound 快照、reference_cell canary、
  环境证据链。两者数据不互推，PARTIAL≠PASS 铁律不变。
- 驾驶舱**只读**：零写入、零派工、零审批（AGENT-READING 边界纪律）。
- 副作用自检：`python3 bin/panorama/panorama-collect.py --check-side-effects`

## 关联

- 规划：BET-Y1Q4-T10-163（驾驶舱）/ T10-164（A1-A9 receipt）/ T10-165（Role/Capsule 语义）/ T10-166（ASD 契约）
- 采集器：`bin/panorama/panorama-collect.py` · 服务：`bin/panorama/panorama-serve.py`
- 产物：`runtime/dashboard/`（gitignored，勿手编）
- 刷新：launchd `com.omostation.panorama-dashboard`（登记于 `.omo/cron/registry.yaml`，sfop_slot=S）
