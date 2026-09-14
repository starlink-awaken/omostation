---
id: ADR-0255
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-07-28
related:
  - 0253-p84-collab-mode-routing-after-k4.md
  - 0254-p84-w22-cclass-collab-detectors.md
  - .omo/_knowledge/audits/2026-07-28-p84-k4-batch34-control-experiment.md
supersedes: []
amends:
  - 0253-p84-collab-mode-routing-after-k4.md
type: ssot
---

# ADR-0255: K4 批次3/4 对照结果 — 强化 ADR-0253 路由表

## Context

K4 批次3（冲突）/ 批次4（失败注入）能力轨对照 harness 已跑（3 次中位墙钟）。

| 批次 | n | 协作中位 | 单中位 | T_s/T_c | 判定 |
|------|---|----------|--------|---------|------|
| 3 冲突 | 90 | 1.51s | 1.07s | **0.71** | 🔴 协作劣 |
| 4 失败注入 | 19 | 0.46s | 0.14s | **0.31** | 🔴 协作劣 |

silent_loss=0 双模式; pass 率持平。

## Decision (amends ADR-0253)

1. **不掩盖**批次3/4 协作墙钟劣（P84 §F）。
2. **路由表补充**:
   - 细粒度 CPU 场景/微任务 fan-out（本 harness 类）→ **单 agent 顺序**（线程池开销 > 并行收益）
   - 独立 **I/O 或 LLM 绑定** 批量（历史 DOC_CLAIMS 5.4x）→ **协作并行**
   - 冲突/失败：优先 **机制检测**（ADR-0254），并行 fan-out **默认关**，除非任务粒度为重 I/O
3. harness 入仓: `bin/collab/control_experiment.py` + 回归测试。

## Status

**ACCEPTED** 2026-07-28。
