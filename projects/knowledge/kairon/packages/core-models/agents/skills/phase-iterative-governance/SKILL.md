---
title: SKILL
type: doc
---

---
name: multi-agent-phase-iterative
description: 用于多Agent持续迭代项目治理。适用于需要Phase关卡、WP拆解并行、严格验收、可审计复盘的任务；当用户要求“持续推进、阶段总结、严格关卡、跨Agent协作、共享状态一致”时触发。
---

# Multi-Agent Phase Iterative Skill

## Use When

- 任务不是一次性完成，而是多轮迭代
- 需要“到阶段末暂停总结，确认后再进入下一阶段”
- 需要可追溯证据链（dispatch/timeline/review/retro）

## Workflow

1. 读取 `references/operating-checklist.md`
2. 创建或更新当前 Phase 的 WP 队列
3. 执行并行任务，保持写域隔离
4. 每次收口刷新：
- `coordination/state/*`
- `coordination/dispatch/*`
- `coordination/timeline/*`
5. 阶段末生成：
- `phase-summary`
- `exit-evidence-pack`
6. 做 gate 判定；未通过则继续当前阶段

## Mandatory Artifacts

- 至少 1 个 active WP
- 每个完成 WP 都有 review + retrospective
- 阶段关卡证据包可一跳访问

## References

- `references/operating-checklist.md`
- `references/gate-rubric.md`
- `templates/phase-summary.md`
- `templates/exit-evidence-pack.md`
