---
title: BET-Y1Q3-T1-01 复盘 — cockpit SSOT 漂移治理 (核实性收口)
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  立账时的三处漂移 (catalog 缺 4 命令/help_map 缺 5/ssb+model-driven 裸注册) 在本收口轮
  实测全部已修复 — 由并发 cockpit PR 完成。核实性收口, 无新代码。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T1-01 复盘 (核实性收口)

## 核验证据 (2026-08-16, 最新 main)

| done_when | 实测 | 命令 |
|---|---|---|
| catalog 补 bdsk/journey/panorama/project | ✅ registry.py 四命令各 2 处 | rg 计数 |
| help_map 补 5 命令 (含 quickstart-check) | ✅ `cockpit help` 五命令全列出 | verify cmd 1 实跑 |
| ssb/model-driven 弃用标注 | ✅ help 列表 `[DEPRECATED]` 前缀 + `--help` 首行标注 | verify cmd 2/3 实跑 |

三条 verify 命令全部通过 (projects/cockpit 内 uv run cockpit 实跑)。

## Q1-Q5 简答

- Q1: 收口轮 0.2h (核验) vs appetite 2d — 工作已被并发 PR 吸收。
- Q2: done_when 三条全过 (上表)。
- Q3: 偏差 = 立账审计 (08-12 cockpit-cmd-audit) 与修复 PR 之间的时差; 教训: candidate 状态期漂移面会被其他轨道顺手修, 收口前必须实跑 verify 而非按 evidence 字段推断。
- Q4: 零代码面 (本 retro + 台账状态)。
- Q5: 下一个 agent: cockpit 命令面变更时注意 registry.py CommandMeta 与 _subcommands.py help 文案双源 (本次已对齐, 未来变更两边同步)。
