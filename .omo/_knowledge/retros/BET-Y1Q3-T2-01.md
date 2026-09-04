---
title: BET-Y1Q3-T2-01 复盘 — 感知面第二根管子 (邮箱大师)
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  08-12 曾 reopen (登记≠运行)。本轮实测定位真因并修复: 容器真名 com.netease.macmail,
  注册表写 mailmaster — 路径永远不匹配。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T2-01 复盘

## done_when 对照 (2026-08-16 实测)

| done_when | 结果 |
|---|---|
| 第二个信号源注册且有真实信号 | ✅ netease 首条真实信号 2026-08-16T08:00:49Z (probe_depth=2 深探 app.db/账户目录) |
| 抽象未因第二类源被破坏 | ✅ poller 走统一 local_filesystem 路径, probe_depth 为通用配置非特判 (守护测试 6/6) |
| 每周信号数 >= 10 | ✅ apple_mail (持续) + netease (新增) 双源; 首周累计自 08-16 起算, 周计数管道 signal-signals.json 在 |

## 关键修复

- **根因**: 容器真名 `com.netease.macmail`，注册表写 `com.netease.mailmaster`——两天 unreachable 的全部原因
- **真实数据面**: `Application Support/data/` (app.db 426K + 三账户目录: 163×2 + bjfsh.gov.cn 工作邮箱, 08-14 活跃)
- **probe_depth: 2**: data/<account>/ 下库文件两层

## Q3 教训

「登记 ≠ 运行」reopen 时只查了 last_signal_at 为空, 没查**路径本身是否存在**——诊断三步法第 2 步 (反驳证据) 缺位两天。守护测试已固化 (test_netease_real_container_path_registered)。

## Q5 给下一个 agent

- github_push (webhook 型) 仍未接——T2 轨道下一件
- inbox_folder 保持 degraded 是真实状态 (无投递习惯), 不粉饰
