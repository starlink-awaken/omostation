---
schema: resident-retro-candidate/v1
topic: convergence-pulse-weekly
generated_at: 2026-09-05T12:00:01Z
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
# convergence-pulse-weekly 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-05T12:00:01Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 2 成功运行 + 0 失败模式 = 2 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260830T220813Z-convergence-pulse-weekly-aca8bf55.md
- 20260830T221348Z-convergence-pulse-weekly-ae1537e8.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260830T220813Z-convergence-pulse-weekly-aca8bf55**
  - workflow: convergence-pulse-weekly
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=270476.744
- **20260830T221348Z-convergence-pulse-weekly-ae1537e8**
  - workflow: convergence-pulse-weekly
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=36.695

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
