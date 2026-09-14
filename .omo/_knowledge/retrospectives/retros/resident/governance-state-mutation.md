---
schema: resident-retro-candidate/v1
topic: governance-state-mutation
generated_at: 2026-08-31T08:20:01Z
status: candidate
counts:
  runs: 27
  failures: 13
  total: 40
failure_rate: 0.325
failure_breakdown:
  by_event_type:
    StepFailed: 13
  trace_count: 13
type: ephemeral
status: archived
---
# governance-state-mutation 运行复盘聚合 (resident 事件驱动)

- generated_at: 2026-08-31T08:20:01Z
- status: candidate (sediment 草稿聚合, 待运营 agent/人工完善为完整 retro)
- sediment 覆盖: 27 成功运行 + 13 失败模式 = 40 草稿
- 失败率: 32.50%

## 成功运行 (runs/)

- 20260803T063243Z-governance-state-mutation-0fd89888.md
- 20260804T073917Z-governance-state-mutation-308c2d35.md
- 20260804T094131Z-governance-state-mutation-a93a676a.md
- 20260806T121548Z-governance-state-mutation-91ec746f.md
- 20260808T052927Z-governance-state-mutation-73470fcc.md
- 20260808T093225Z-governance-state-mutation-0af3aeab.md
- 20260808T094047Z-governance-state-mutation-71fc9960.md
- 20260809T233419Z-governance-state-mutation-d4c98b62.md
- 20260814T123541Z-governance-state-mutation-f3dfe789.md
- 20260814T123841Z-governance-state-mutation-9890ead1.md
- 20260820T021725Z-governance-state-mutation-1d1600c1.md
- 20260820T063442Z-governance-state-mutation-743ac648.md
- 20260820T070722Z-governance-state-mutation-cc7a3f63.md
- 20260820T073454Z-governance-state-mutation-2d39fe5c.md
- 20260821T010715Z-governance-state-mutation-bf1e6b14.md
- 20260821T132222Z-governance-state-mutation-2d082c75.md
- 20260821T132302Z-governance-state-mutation-f8c28458.md
- 20260822T005042Z-governance-state-mutation-70f1c966.md
- 20260822T040703Z-governance-state-mutation-19cbf869.md
- 20260822T081119Z-governance-state-mutation-91f0fc58.md
- 20260823T134905Z-governance-state-mutation-18101638.md
- 20260823T135620Z-governance-state-mutation-06c726b4.md
- 20260824T010956Z-governance-state-mutation-3768d513.md
- 20260825T101143Z-governance-state-mutation-2e7ce1a1.md
- 20260828T034834Z-governance-state-mutation-4a8001e1.md
- 20260828T035040Z-governance-state-mutation-44a204d2.md
- 20260828T044529Z-governance-state-mutation-69537635.md

## 失败模式 (failures/)

- 20260803T063243Z-governance-state-mutation-0fd89888-e5ab3f01.md
- 20260806T121548Z-governance-state-mutation-91ec746f-15ad6389.md
- 20260808T052927Z-governance-state-mutation-73470fcc-2debb7cc.md
- 20260808T093225Z-governance-state-mutation-0af3aeab-d8c05bff.md
- 20260808T094047Z-governance-state-mutation-71fc9960-d4eec045.md
- 20260809T233419Z-governance-state-mutation-d4c98b62-d9589717.md
- 20260820T021725Z-governance-state-mutation-1d1600c1-20cb9637.md
- 20260820T073454Z-governance-state-mutation-2d39fe5c-df786e88.md
- 20260821T010715Z-governance-state-mutation-bf1e6b14-913c9975.md
- 20260821T132222Z-governance-state-mutation-2d082c75-eebd25a6.md
- 20260822T005042Z-governance-state-mutation-70f1c966-917f4ef3.md
- 20260822T040703Z-governance-state-mutation-19cbf869-b901a51a.md
- 20260822T081119Z-governance-state-mutation-91f0fc58-7d61e9f3.md

## 失败根因画像 (确定性启发式)

- StepFailed: 13 篇
- 关联工作流溯源: 13 个 (trace_id 见下)
  - `20260803T063243Z-governance-state-mutation-0fd89888`
  - `20260806T121548Z-governance-state-mutation-91ec746f`
  - `20260808T052927Z-governance-state-mutation-73470fcc`
  - `20260808T093225Z-governance-state-mutation-0af3aeab`
  - `20260808T094047Z-governance-state-mutation-71fc9960`
  - `20260809T233419Z-governance-state-mutation-d4c98b62`
  - `20260820T021725Z-governance-state-mutation-1d1600c1`
  - `20260820T073454Z-governance-state-mutation-2d39fe5c`
  - `20260821T010715Z-governance-state-mutation-bf1e6b14`
  - `20260821T132222Z-governance-state-mutation-2d082c75`
  - `20260822T005042Z-governance-state-mutation-70f1c966`
  - `20260822T040703Z-governance-state-mutation-19cbf869`
  - `20260822T081119Z-governance-state-mutation-91f0fc58`

## 确定性五问骨架 (ledger 追溯, 自动填充)

- **20260803T063243Z-governance-state-mutation-0fd89888**
  - 计划 (objective): Add agent-onboarding skill, bos-service-discovery skill, a2a-coordination skill, and agent-onboarding workflow to agent-workflows.yaml
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=1043.036
- **20260804T073917Z-governance-state-mutation-308c2d35**
  - 计划 (objective): 批量推进: state sync + closeout active run + 提交 P79 遗留变更 + 审查 draft GaC 规则 + X3 软门禁评估
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=438.461
- **20260804T094131Z-governance-state-mutation-a93a676a**
  - 计划 (objective): 补 PASW 独立 ADR-0371: 修复 0355 引用断裂, 固化子模块隔离机制
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=4633.47
- **20260806T121548Z-governance-state-mutation-91ec746f**
  - 计划 (objective): 3Y-PLAN batch2/3 workflow + skill + task 物化
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=54439.976
- **20260808T052927Z-governance-state-mutation-73470fcc**
  - 计划 (objective): BET-Y1Q2-T6-03 bin 脚本清理 309 → ≤240
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=65517.236
- **20260808T093225Z-governance-state-mutation-0af3aeab**
  - 计划 (objective): P0 fix: remove orphan 0388-layer-contract-direction-ssot.md + renumber 0391-layer-contract-direction-ssot to ADR-0396 (duplicate ADR-0391 cleanup)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=400.813
- **20260808T094047Z-governance-state-mutation-71fc9960**
  - 计划 (objective): P1 fix: repair 5 broken doc refs (archived tools: check-scenario-growth→scenario_lib, check-dead-path-refs→check-dead-path-tool-fallback, check-perf-budget retired, store.json→foundry path)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=331.83
- **20260809T233419Z-governance-state-mutation-d4c98b62**
  - 计划 (objective): SR-03: controlled Agora launchd recovery and live health/A2A smoke
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=627.634
- **20260814T123541Z-governance-state-mutation-f3dfe789**
  - 计划 (objective): Converge governance/runtime diff set to clear ADR-0203 requirement scope
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=48.873
- **20260814T123841Z-governance-state-mutation-9890ead1**
  - 计划 (objective): Prepare final mainline PR for remaining root-level governance/runtime convergence changes
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=96.045
- **20260820T021725Z-governance-state-mutation-1d1600c1**
  - 计划 (objective): 修复 MOSBeliefManager 直接向 .omo/_truth/registry/memory-os.yaml 写入运行时计数，导致 truth registry 持续被运行时污染的问题
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=5922.17
- **20260820T063442Z-governance-state-mutation-743ac648**
  - 计划 (objective): [BET-Y1Q3-T6-12] MOSBeliefManager 运行时计数写入 runtime truth 而非 SSOT registry (Appetite: 1 hour)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=3
  - 指标: event_count=6, duration_s=1332.216
- **20260820T070722Z-governance-state-mutation-cc7a3f63**
  - 计划 (objective): 归档 bin/bc-os/ 下当前无外部引用的 3 个脚本（apple_mail_watcher/l3_smart_router/lifecycle_changer），减少活跃脚本表面积
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=3
  - 指标: event_count=6, duration_s=1439.831
- **20260820T073454Z-governance-state-mutation-2d39fe5c**
  - 计划 (objective): [BET-Y1Q3-T1-01] cockpit SSOT 漂移治理 — COMMAND_CATALOG + help_map 同步 + 弃用 CLI 清理 (Appetite: 2 days)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=63132.163
- **20260821T010715Z-governance-state-mutation-bf1e6b14**
  - 计划 (objective): [BET-Y1Q3-T1-08] 退役 coordination-daemon 独立 clone 部署并迁移备份到 Workspace (Appetite: 1 day)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=42289.435
- **20260821T132222Z-governance-state-mutation-2d082c75**
  - 计划 (objective): [BET-Y1Q3-T1-09] D4 逃生口固化 — 权限类 vs fingerprint 债 + 观察再跳 + 人类口硬拒 (Appetite: 1 day)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=39.691
- **20260821T132302Z-governance-state-mutation-f8c28458**
  - 计划 (objective): [BET-Y1Q3-T1-09] D4 逃生口固化 — 权限类 vs fingerprint 债 + 观察再跳 + 人类口硬拒 (Appetite: 1 day)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=3
  - 指标: event_count=6, duration_s=1295.668
- **20260822T005042Z-governance-state-mutation-70f1c966**
  - 计划 (objective): Drop archived scripts/ from ruff debt_scope so ruff-debt does not require that tree
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=31904.348
- **20260822T040703Z-governance-state-mutation-19cbf869**
  - 计划 (objective): Compress AGENTS.md: fix numbering, remove hardcoded/outdated refs, preserve all info via pointers
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=20126.4
- **20260822T081119Z-governance-state-mutation-91f0fc58**
  - 计划 (objective): Compress CLAUDE.md/ARCHITECTURE.md/README.md/projects/AGENTS.md: remove duplication, fix stale refs, preserve all info
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=5471.829
- **20260823T134905Z-governance-state-mutation-18101638**
  - 计划 (objective): [BET-Y1Q3-T1-10] resident 体系全面接线 — 配置/文档/治理/CI/MCP/BOS URI 感知 (Appetite: 2 days)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=failed, evidence_count=1
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=417.239
- **20260823T135620Z-governance-state-mutation-06c726b4**
  - 计划 (objective): [BET-Y1Q3-T1-10] resident 体系全面接线 — 配置/文档/治理/CI/MCP/BOS URI 感知 (Appetite: 2 days)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=2
  - 指标: event_count=6, duration_s=32924.848
- **20260824T010956Z-governance-state-mutation-3768d513**
  - 计划 (objective): 差距治理 S1-S4 落地: CAP-OWN 能力所有权+删除闸门 / PROJ-FORCE 投影强制化 / AUTO-FIX / GEN-FORCE (waiver: .omo/_truth/governance-evidence/waiver-2026-08-24-gap-governance.md)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=3
  - 指标: event_count=6, duration_s=4359.193
- **20260825T101143Z-governance-state-mutation-2e7ce1a1**
  - 计划 (objective): register .omo/affected.json as runtime asset in omo-governance-surfaces.yaml (fix pre-existing Governance Check red: unregistered top-level asset affected.json)
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=3
  - 失败根因: step=execute, error=workflow failed
  - 指标: event_count=6, duration_s=87645.814
- **20260828T034834Z-governance-state-mutation-4a8001e1**
  - 计划 (objective): Canonical claim for #2386 prerequisite ADR continuity recovery
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=124.483
- **20260828T035040Z-governance-state-mutation-44a204d2**
  - 计划 (objective): Stable-actor canonical claim for #2386 prerequisite ADR continuity recovery
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=False, status=blocked, evidence_count=1
  - 失败根因: step=execute, error=None
  - 指标: event_count=6, duration_s=1508.708
- **20260828T044529Z-governance-state-mutation-69537635**
  - 计划 (objective): Canonical claims for post-2398 BOS mirror recovery
  - workflow: governance-state-mutation
  - 实际步骤: execute
  - 结果与证据: ok=True, status=ok, evidence_count=1
  - 指标: event_count=6, duration_s=738.012

> 上节为事件流确定性提取 (计划/实际/结果/失败/指标); 语义项见下待人工完善。

## 待完善(运营 agent/人工)

- [ ] 关键发现
- [ ] 净增减
- [ ] 交接建议
