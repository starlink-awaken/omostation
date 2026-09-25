---
schema: resident-retro-candidate/v1
topic: bet-execution
generated_at: 2026-09-24T23:08:28Z
status: candidate
counts:
  runs: 2
  failures: 0
  total: 2
failure_rate: 0.0
failure_breakdown:
  by_event_type:
  trace_count: 0
---
# bet-execution 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-24T23:08:28Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 2 成功运行 + 0 失败模式 = 2 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260921T065903Z-bet-execution-5d3ba2b1.md
- 20260923T110523Z-bet-execution-3d555b07.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260921T065903Z-bet-execution-5d3ba2b1**
  - 计划 (objective): [BET-Y1Q2-T7-01] 工程交付 dogfood 开 shadow (Appetite: 1 week)
  - workflow: bet-execution
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=2144.604
- **20260923T110523Z-bet-execution-3d555b07**
  - 计划 (objective): [BET-Y2Q2-T4-01] North-star recovery and first real Decision Episode proof (Appetite: 13 weeks)
  - workflow: bet-execution
  - 指标: event_count=1, duration_s=0.0

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
