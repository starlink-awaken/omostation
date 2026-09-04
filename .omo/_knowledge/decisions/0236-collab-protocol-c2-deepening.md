---
id: ADR-0236
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last_updated: 2026-07-25
related:
  - 0235-role-catalog-c1-research-delivery.md
  - 0229-role-framework-three-roles.md
  - STRAT-P81-strategic-roadmap.md
supersedes: []
amends: []
---

# ADR-0236: C2 协作协议加深 — 多轮协商 + 冲突消解 + 任务分解

## Context

STRAT-P81 Batch3 C2 要求协作深度从单向分派 (assign→handshake→verify) 升级到：
(a) 多轮协商握手；(b) 冲突消解规则；(c) 大任务分解→子任务再组合。
C1 (ADR-0235) 已加 research/delivery + governance dispatch 能力，为多轮协商铺路
(research_request/result 往返)。metaos 编排层 (TS) 调用本协议层属跨语言桥，后续轮。

## Decision

在 `bin/_archive/2026-08-conv3/role_framework.py` 加三个 C2 函数（协议层，Python，复用 RoleProtocolBus）：

1. **`run_multi_round_negotiation(max_rounds, satisfy_after)`**：
   governance ↔ research 多轮 research_request/result 往返，直到 `satisfy_after` 轮满意
   或 `max_rounds` 耗尽。比单向 handshake 深——允许基于研究结果追问/调整。
2. **`resolve_message_conflict(messages)`**：同 task_ref+type 多角色消息按优先级取胜者。
   优先级（低→高）：research < delivery < engineering < audit < governance。
   governance 仲裁；audit 证据优先于实现；空 list 返回 None。
3. **`decompose_into_subtasks(task_ref, subtask_refs)`**：大任务 → 子任务列表，每个子任务
   走 3-role handshake（`run_backlog_collab` 骨架），返回 per-subtask 完成度 + aggregate rate。

**回放能力**：RoleProtocolBus.history 天然记录每轮交互（C2 验收"每轮交互可回放"）。

## Confirmation

- 多轮协商：satisfy_after=2 → 2 轮满意；satisfy_after>max_rounds → 耗尽未满意
- 冲突消解：audit > research；governance 最高；空 list → None
- 任务分解：3 子任务全完成 rate=1.0；空 subtasks → rate=0.0
- `tests/test_role_framework_c2.py` **7 tests pass**（+ C1 8 tests 回归不破坏）

## Status

**ACCEPTED** for Batch3 C2 protocol deepening (2026-07-25)。metaos TS 编排层调用桥
（跨语言）+ 真实复合任务端到端跑通（≥3 角色 + ≥2 轮协商）后续轮。
