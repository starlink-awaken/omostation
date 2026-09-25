---
schema: resident-retro-candidate/v1
topic: mini
generated_at: 2026-09-24T23:48:29Z
status: candidate
counts:
  runs: 22
  failures: 0
  total: 22
failure_rate: 0.0
failure_breakdown:
  by_event_type:
  trace_count: 0
---
# mini 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-24T23:48:29Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 22 成功运行 + 0 失败模式 = 22 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260918T113701Z-mini-489f12d9.md
- 20260918T113701Z-mini-539cf2c6.md
- 20260920T030320Z-mini-64f7e9d6.md
- 20260920T030320Z-mini-b5646847.md
- 20260920T064739Z-mini-b275e835.md
- 20260920T064739Z-mini-e6282d5c.md
- 20260920T070133Z-mini-37ada5f2.md
- 20260920T070134Z-mini-b23f7287.md
- 20260920T070828Z-mini-a3ef1042.md
- 20260920T070828Z-mini-fcb7d0bc.md
- 20260921T071429Z-mini-32674e15.md
- 20260921T071430Z-mini-87664dcb.md
- 20260922T014100Z-mini-f2f2dad5.md
- 20260922T014101Z-mini-6a86b3ce.md
- 20260922T014347Z-mini-f27a61e8.md
- 20260922T014348Z-mini-92795c07.md
- 20260923T022736Z-mini-94bc5a40.md
- 20260923T022737Z-mini-7b1970d5.md
- 20260924T131807Z-mini-8fafc133.md
- 20260924T131809Z-mini-cf6cb943.md
- 20260924T131955Z-mini-495cdf5a.md
- 20260924T131956Z-mini-99d87d73.md

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
- **20260920T030320Z-mini-64f7e9d6**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.195
- **20260920T030320Z-mini-b5646847**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.206
- **20260920T064739Z-mini-b275e835**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.187
- **20260920T064739Z-mini-e6282d5c**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.215
- **20260920T070133Z-mini-37ada5f2**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.209
- **20260920T070134Z-mini-b23f7287**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.183
- **20260920T070828Z-mini-a3ef1042**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.184
- **20260920T070828Z-mini-fcb7d0bc**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.174
- **20260921T071429Z-mini-32674e15**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.253
- **20260921T071430Z-mini-87664dcb**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.241
- **20260922T014100Z-mini-f2f2dad5**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.193
- **20260922T014101Z-mini-6a86b3ce**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.194
- **20260922T014347Z-mini-f27a61e8**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.316
- **20260922T014348Z-mini-92795c07**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.269
- **20260923T022736Z-mini-94bc5a40**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.304
- **20260923T022737Z-mini-7b1970d5**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.255
- **20260924T131807Z-mini-8fafc133**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.458
- **20260924T131809Z-mini-cf6cb943**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.372
- **20260924T131955Z-mini-495cdf5a**
  - 计划 (objective): real run test
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=0.177
- **20260924T131956Z-mini-99d87d73**
  - 计划 (objective): evidence gate
  - workflow: mini
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=0
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=0.159

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
