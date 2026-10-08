---
schema: resident-retro-candidate/v1
topic: mini
generated_at: 2026-10-08T12:38:27Z
status: candidate
counts:
  runs: 4
  failures: 0
  total: 4
failure_rate: 0.0
failure_breakdown:
  by_event_type:
  trace_count: 0
---
# mini 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-10-08T12:38:27Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 4 成功运行 + 0 失败模式 = 4 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260921T121948Z-mini-55a1e31d.md
- 20260921T121949Z-mini-d70219ab.md
- 20260923T130256Z-mini-961def15.md
- 20260923T130256Z-mini-c5f3e035.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260921T121948Z-mini-55a1e31d**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.167
- **20260921T121949Z-mini-d70219ab**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.167
- **20260923T130256Z-mini-961def15**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.173
- **20260923T130256Z-mini-c5f3e035**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.177

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
