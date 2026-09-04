---
schema: resident-retro-candidate/v1
topic: governance-audit
generated_at: 2026-09-04T13:40:00Z
status: candidate
counts:
  runs: 9
  failures: 0
  total: 9
failure_rate: 0.0
failure_breakdown:
  by_event_type:
  trace_count: 0
---
# governance-audit 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-09-04T13:40:00Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 9 成功运行 + 0 失败模式 = 9 草稿
- 失败率: 0.00%

## 成功运行 (runs/)

- 20260804T075023Z-governance-audit-60ae992b.md
- 20260807T032632Z-governance-audit-dec7218f.md
- 20260809T054134Z-governance-audit-e14a9bd8.md
- 20260810T144332Z-governance-audit-e558e4a2.md
- 20260817T075007Z-governance-audit-91e33ced.md
- 20260820T011659Z-governance-audit-d64a741e.md
- 20260823T084946Z-governance-audit-5f022470.md
- 20260824T123216Z-governance-audit-556a1f18.md
- 20260825T134542Z-governance-audit-a1cea110.md

## 失败模式 (failures/)

- (无)

## 失败根因画像 (确定性启发式)

- (无失败模式沉淀)

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260804T075023Z-governance-audit-60ae992b**
  - 计划 (objective): 审查 6 条 draft GaC 规则(CR-CROSS-REPO/CR-PR-DESCRIPTION-NON-EMPTY/CR-PRINCIPLE-ENFORCEMENT/CR-RUFF-SCOPE-STABLE/CR-WORKTREE-CLEAN-BEFORE-PR/CR-CROSS-REPO-REGISTRY-CONSISTENT): 检查工具就绪度并推进到 active 或清理
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=10697.446
- **20260807T032632Z-governance-audit-dec7218f**
  - 计划 (objective): Branch, worktree, and submodule hygiene audit and cleanup across root + subprojects
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=3
  - 指标: event_count=6, duration_s=9182.06
- **20260809T054134Z-governance-audit-e14a9bd8**
  - 计划 (objective): D5 retro 强制落地: retro-due 接入 gac-gate (sgf-policy/ci-surfaces 登记) + 补齐 16 个 done bet 缺失 retro
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=61940.13
- **20260810T144332Z-governance-audit-e558e4a2**
  - 计划 (objective): fix project_health_check: exclude venv/dist node_modules from frontmatter coverage
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=48035.662
- **20260817T075007Z-governance-audit-91e33ced**
  - 计划 (objective): [BET-Y1Q3-T6-06] 文档治理减负 — 0 违规后停止扩面转纯维护 (Appetite: 3 days)
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=65411.554
- **20260820T011659Z-governance-audit-d64a741e**
  - 计划 (objective): [BET-Y1Q3-T6-05] 治理工具自净闭环 — 脚本减法配额制度化 + 孤儿清理 (Appetite: 1 week)
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=9548.278
- **20260823T084946Z-governance-audit-5f022470**
  - 计划 (objective): Architecture maturity assessment
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=171705.886
- **20260824T123216Z-governance-audit-556a1f18**
  - 计划 (objective): [BET-Y1Q3-T10-09] worktree submodule init 策略 (gate 环境性失败) (Appetite: 0.5 day)
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=71958.58
- **20260825T134542Z-governance-audit-a1cea110**
  - 计划 (objective): [BET-Y1Q3-T1-12] Exact Capability Binding 与 native asset receipt 消费收敛 (Appetite: 5 days)
  - workflow: governance-audit
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=74958.639

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
