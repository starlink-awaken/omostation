---
status: ACCEPTED
lifecycle: governance-audit
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0209-ledger-trim-and-adr-ssot-renumbering.md
  - 0203-requirement-iteration-workflow-mandatory.md
  - 0204-requirement-iteration-enforcement.md
  - 0211-p74-run-frequency-field-and-excluded-workflows-removal.md
supersedes: []
---

# ADR-0213 — ADR-0209 附录 A 收口（A2 / A4 / A6）

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **Parent**: ADR-0209（附录 A 登记 6 条治理补丁）

## Context

ADR-0209 将 session 自报 6 条治理补丁登记为附录 A，待拆 PR。A1/A3 已在 #391 落地，
A5 相关部分在 #390（P74 `run_frequency`）。本 ADR 收口剩余 **A2 / A4 / A6** 的可执行最小面。

## Decision

### D1 — A2 ledger self-heal（replay write path）

`observe` / compliance 路径上若发现 `ledger_missing_run`，**先**从 run yaml 重放
`agent_workflow_start`（及终态时的 `agent_workflow_close`）到 `events.jsonl`，
再判定 warn。重放事件带 `healed: true` + `heal_reason`。

**不做**：不猜测被 trim 的完整历史；不改 ledger 根路径；不静默吞掉 heal 失败。

### D2 — A4 read-only run 豁免 claim_policy write 语义

当 workflow `surfaces.write == []`（显式空写面，如 `observer-audit`）时，
`claim_coverage_report` 返回 `mode=read_only_exempt`，**不**因 worktree 上他人脏文件
要求 claim。缺失 `write` 键的遗留 workflow **不**自动豁免。

### D3 — A6 三类 finding 议题扩展

`gac-local-gate` 对下列 check 输出 `finding_topics[]` 结构化议题：

| check | topic |
|-------|--------|
| `governance-semantic-gate` | `governance-semantic` |
| `gac-compute-onboard-check` | `compute-onboard` |
| `bus-usage-report` | `bus-dormant-adapter` |

硬失败 → `severity=error, blocking=true`；JSON 内 soft findings（exit 0 但 ok=false/findings 非空）
→ `severity=warn, blocking=false`。门禁总 `ok` 仍由各 check returncode 决定。

## Consequences

- 只读审计不再被并发 dirty 误伤 claim 闸门
- ledger 被外部 trim 后 observe 可自愈到「可追踪」状态
- GaC 报告多一层 topic 分类，便于后续 dashboard / 工单路由

## Related

- A1/A3: #391
- A5 部分: #390 ADR-0211
- 战略定档: ADR-0210 ACCEPTED
