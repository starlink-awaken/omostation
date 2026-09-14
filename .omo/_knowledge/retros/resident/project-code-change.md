---
schema: resident-retro-candidate/v1
topic: project-code-change
generated_at: 2026-09-14T04:35:36Z
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
# project-code-change 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-14T04:35:36Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 2 成功运行 + 0 失败模式 = 2 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260913T230353Z-project-code-change-10ba437f.md
- 20260914T040913Z-project-code-change-a78b5042.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260913T230353Z-project-code-change-10ba437f**
  - 计划 (objective): [BET-Y1Q4-T6-25] OpenHuman 本地桥接器升级与多源健康生物标记物 Schema 归一化 (OpenHuman Local Bridge & Biometric Normalizer) (Appetite: 3 days)
  - workflow: project-code-change
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=12433.308
- **20260914T040913Z-project-code-change-a78b5042**
  - 计划 (objective): Unbound mechanism recovery: make ledger-safe-insert emit a semantic bets list item
  - workflow: project-code-change
  - 指标: event_count=1, duration_s=0.0

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
