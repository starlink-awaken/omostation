---
schema: md/v1
status: archived
lifecycle: history
owner: unassigned
last-reviewed: 2026-09-25
type: ephemeral
bet_id: BET-Y1Q4-T7-07
completed_at: 2026-09-13
run_id: 20260913T23-t7-07-refine-script
pr: "https://github.com/starlink-awaken/omostation/pull/3755"
---


# Retro: BET-Y1Q4-T7-07 — Continual Harness 证据驱动自演化与沙箱回滚管道

## 交付摘要

| 项目 | 状态 |
|------|------|
| bin/ops/continual-harness-refine.py (轨迹审阅与技能萃取) | ✅ (本 PR 新增) |
| projects/omo/src/omo/resident/refine_rollback.py (回滚驱动器) | ✅ (#3701 之前) |
| T6-07 refine_pipeline 接入 (skill 落盘 + receipt) | ✅ (本 PR stub) |

## What went well

- 零模型调用: 仅确定性逻辑 (sha256 digest, 文件 IO)
- skill 落盘到 .omo/_knowledge/skills/ (gitignored)
- receipt 落盘到 .omo/_knowledge/refinements/<id>.json
- rollback 委派 omo CLI (件二), 单一职责

## What was learned

- 技能 package 与 serGKI 的 SEMA 信念库结构兼容 (同 schema, 不同 namespace)
- 5 秒内自动回滚约束 (circuit_breaker) 由件二负责, 不在本 PR
- bin/ops/ 命名空间统一, 不新增 bin/_registry 重复登记 (复用已有 bionic_memory_consolidation.yaml)

## What to improve

- 当前 stub 用 sha256 派生 skill name, 实际应接 serGKI 的 SKILL-as-Code 萃取
- --auto 模式目前固定 timestamp, 应从 event-ledger 拉最近 done 任务
- 与 cockpit-ui 的 /refine 触发面板对接待 T7-04 anchor 工作继续

## Metrics

- Files added: 1 script (170 LOC)
- Tests: 0 (stub only; omo tests cover rollback)
- Appetite used: 0.5d
EOF
