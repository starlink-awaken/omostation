---
schema: bet-retro/v1
bet_id: BET-Y2Q1-T6-03
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-06
type: ephemeral
---

# BET-Y2Q1-T6-03 retro — 防腐看门狗常态化与表面积熔断

## What changed

- **`bin/gac/anti-corrosion-patrol.py`**（新）：聚合既有防腐散件——
  `weekly_net_lines`（周窗口 git diff 净增行数，红线 ≤0）、
  `rule_health_score`（governance-checks.yaml 85 条规则健康度打分
  + 退役候选标记）、`dead_code_and_dupes`（调用既有 detector，不复制
  逻辑）、`budget`（调用既有 anti-corrosion-check）；`--enforce`
  熔断（breach → exit 1）+ `--json` 巡检快照（cockpit 标红字段
  cockpit_alert.level）。
- **governance-checks.yaml**：注册 `CR-ANTI-CORROSION-PATROL`
  （blocking: true, cmd: --enforce --json）。
- 测试 5/5（红线形态/评分形态/detector 集成/enforce 退出码分支/
  JSON 快照），ruff clean。
- 真实巡检快照：verdict PASS，周净增 0（红线达标），健康度 78
  （66/85，退役候选 4）。

## Q3 (打假)

- 首版健康度打分 0 分：正则 body 提取用 `- id:\s*{rid}\n` 而 id 后
  无换行场景失配；块体关键字只查 cmd/command 漏了 check/script。
- `any(a, b, c)` 误用（应为可迭代单参）——低级错误靠真实运行暴露。
- governance-checks.yaml 文件尾追加再次破坏 YAML（与 ledger 同陷阱），
  锚定"最后一个规则块结束位置"插入后通过。
- 真实巡检发现 main 上防腐预算确有 violations（既有 check 报告）——
  patrol 如实透传不掩盖。

## Q4 (遗留)

- 退役候选（4 条）只标记不删除——删除动作属人工/T6 流程。
- launchd/cron 定时注册由人工执行（脚本头部有说明）。
- Cockpit 消费快照 JSON 的标红 UI 面待接（快照字段已预留
  cockpit_alert.level）。
