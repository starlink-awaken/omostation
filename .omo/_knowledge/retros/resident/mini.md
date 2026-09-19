---
schema: resident-retro-candidate/v1
topic: mini
generated_at: 2026-09-19T08:27:09Z
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
# mini 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-19T08:27:09Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 2 成功运行 + 0 失败模式 = 2 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260918T113701Z-mini-489f12d9.md
- 20260918T113701Z-mini-539cf2c6.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260918T113701Z-mini-489f12d9**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.2
- **20260918T113701Z-mini-539cf2c6**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.194

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
