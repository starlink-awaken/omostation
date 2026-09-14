---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y2Q1-T6-03
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T6-03 防腐看门狗常态化与表面积熔断巡检设计

## 1. 目标

将既有防腐散件（anti-corrosion-check 预算检查、detector 死代码探测）
聚合为每日/PR 可触发的常态巡检：**每周净增行数 ≤0 红线**、GaC 规则
健康度打分与退役候选标记、双头依赖与死代码报警、超预算自动熔断阻断。

## 2. In scope

1. `bin/gac/anti-corrosion-patrol.py`（新文件）：
   - `weekly_net_lines()`：git diff 统计周窗口（--since "7 days ago"）
     的 code+docs 净增行数（新增-删除），≤0 红线达标、>0 报告超预算量。
   - `rule_health_score()`：GaC 规则健康度——对 governance-checks.yaml
     登记的规则逐条打分（定义完整/最近执行引用/退役候选标记）。
   - `dead_code_and_dupes()`：调用既有 anti-corrosion-detector 的输出，
     汇总死代码与双头依赖告警。
   - `--enforce`：熔断模式——周净增 >0 或预算超限或高危告警 → exit 1
     （PR/CI 阻断）；`--json` 巡检快照（供 Cockpit 标红消费）。
   - 复用既有 `anti-corrosion-check.py` / `detector.py`，不复制其逻辑。
2. `.omo/_truth/registry/governance-checks.yaml`（增量）：注册
   anti-corrosion-patrol 为 GaC 检查条目。
3. `tests/test_anti_corrosion_patrol.py`（新文件）：红线判定/评分/
   enforce 退出码/JSON 快照单测。

## 3. Out of scope

- 不自动删除代码（退役候选只标记，删除动作属人工/T6 流程）。
- 不新增预算阈值（沿用 anti-corrosion-budget.yaml v2.0.0）。
- launchd/cron 定时注册由人工执行（脚本头部提供片段）。

## 4. 验收（对齐 ledger done_when）

1. patrol 可在每日/PR 自动化触发（CLI 入口 + CI 注册）。
2. 超预算场景 `--enforce` exit 1 阻断；快照 JSON 含标红告警字段。
3. 违例 0 容忍测试套件通过（阈值边界用例）。
