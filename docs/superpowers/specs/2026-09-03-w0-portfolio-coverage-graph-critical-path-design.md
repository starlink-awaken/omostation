---
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T1-05
risk_level: L2
human_gate: true
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
implementation_authorized: false
---

# W0 Portfolio Coverage Graph and Critical Path Design

## 1. Decision

Build a pure, deterministic graph over the existing Ledger. It uses only two
machine edge types:

1. `depends_on` for execution order;
2. BET/Milestone `covers` relations for Key Result coverage.

`parent_bet` expresses portfolio ownership and never silently creates an
execution dependency.

## 2. Goal and hypothesis

If required KRs must retain at least one mandatory delivery or proven evidence
source, failed, removed, or superseded BETs cannot silently leave the Vision
uncovered.

Critical-path output must answer which BET should run next, what it blocks,
and which Milestone it advances. It must not calculate progress from the
number of BETs marked done.

## 3. Dependency and coverage rules

- `depends_on` must remain a DAG with no missing ID.
- Every required KR has at least one mandatory BET or immutable proven source.
- Every non-terminal v2 BET belongs to one Campaign and references at least one
  Objective and one KR.
- Failed BETs require a replacement or an explicit Campaign replan.
- Removing a BET recomputes coverage before the change can be admitted.
- Duplicate coverage is allowed only when the redundancy is intentional and
  carries a stated reason.

## 4. Critical-path rules

The result is derived from dependency depth, Milestone target window, current
terminal state, and blocked descendants. Stable input produces stable order.

The public report contains:

- ready critical-path BETs;
- blocked descendant count;
- unresolved KR coverage gaps;
- writer-lane conflicts;
- evidence age and unavailable status where applicable.

## 5. Prospective write surfaces

- `bin/plan/portfolio_graph.py`
- `bin/plan/bet-ledger.py`
- `tests/test_bet_portfolio_graph.py`
- this Spec and its future implementation plan/retro

## 6. Required verification

1. The current dependency baseline remains zero missing IDs and zero cycles.
2. A required KR with zero coverage fails with
   `REQUIRED_KR_UNCOVERED`.
3. A failed leaf without replacement fails coverage conservation.
4. A replacement with equivalent KR coverage restores the graph.
5. Parent ownership does not alter topological order.
6. A fixed fixture yields byte-stable critical-path JSON.
7. No progress percentage is derived from raw BET counts.

## 7. Error and rollback contract

Missing references or cycles halt without modifying Ledger state. A graph
failure does not auto-create a BET, replacement, dependency, or evidence row.
Rollback removes the new query/validation path while preserving all source
Ledger data.

## 8. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, implementation, migration, projections, status changes,
W1-W6, or value evidence. Writing-plans requires a separate post-binding
authorization.

## 9. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T1-05-01 | Implementation-time dependency graph has no missing ID or cycle | structured_report | portfolio graph report |
| AC-T1-05-02 | Every required KR retains mandatory BET or proven-source coverage | negative_test | zero-coverage fixture |
| AC-T1-05-03 | Failed leaf without replacement fails; equivalent replacement restores coverage | negative_test | replacement fixture pair |
| AC-T1-05-04 | Parent ownership never changes execution topological order | unit_test | parent/dependency separation fixture |
| AC-T1-05-05 | Fixed input produces byte-identical critical-path JSON | replay_receipt | repeated deterministic run |
| AC-T1-05-06 | No progress value is derived from raw BET counts | contract_test | output schema and forbidden-field assertion |

## 10. 反指标

- Number of graph nodes, edges or rendered lines.
- Percentage of BETs marked done.
- A visually complete graph with an uncovered required KR.
- Faster output achieved by skipping missing-reference or cycle validation.
- Duplicate coverage without an explicit redundancy rationale.

## 11. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 图数据库/service/dispatcher vs pure Ledger graph | pure deterministic graph | 复用唯一 Ledger SSOT，不增加状态库或调度面 |
| 2 | 多种关系类型 vs two machine edges | `depends_on` + `covers` | 保持模型最小 |
| 3 | parent 隐式依赖 vs 显式分离 | parent only owns portfolio | 避免 child 死锁 |
| 4 | done count progress vs KR coverage | KR coverage | 活动量不是结果量 |
| 5 | failed BET 自动忽略 vs replacement conservation | replacement required | 防止目标暗缺口 |
| 6 | graph 自动写回 vs read-only report | no graph writer | 派生图没有真值修改权限 |
| 7 | missing ref/cycle 时输出部分图 vs typed halt | typed fail closed | 不用残缺拓扑误导关键路径 |
