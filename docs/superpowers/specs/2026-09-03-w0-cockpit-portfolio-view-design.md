---
schema_version: specification/v1
spec_version: 1.0.1
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-03
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T8-05
risk_level: L2
human_gate: false
value_indicator_policy: false
source_design_sha256: cbdee89004d0156e262daa63a1c38cfd660c0d5efbf0fce1a8eec8a92027c30b
source_proposal_sha256: 26bd1b3df552e693f2ac2684df255436522ff816d7844459523fafe130587100
source_amendment_sha256: 5b1bb03274d8f7383b67f88953cf0c7074a571a9a1d5aebb1ab68bb234042409
source_id_collision_amendment_sha256: 1a6a63d4fc20b6d3f385b27518018fdb633e5cd38ee9c171db1c08773eecd992
implementation_authorized: true
---

# W0 Cockpit Portfolio Read-Only View Design

## 1. Decision

### Implementation authorization (1.0.1)

Principal session authorization 2026-09-04 ("go，先pr合并提交。然后依次推进吧，需要人类的，我给你授权") releases human_gate and authorizes implementation for remaining W0 Portfolio children in safer order. T8-05 Cockpit remains a read-only consumer.


Expose Portfolio status through the existing Cockpit entry point. Cockpit
reads the digest-bound control projection and never becomes a Ledger, Goals,
OMO, Milestone, or KR writer.

## 2. Product surface

The existing `cockpit portfolio` command family provides:

```text
cockpit portfolio status
cockpit portfolio objectives
cockpit portfolio critical-path
cockpit portfolio blockers
```

Output prioritizes outcomes, current critical-path BETs, blockers, unavailable
evidence, and the next safe action. It hides internal graph and workflow
mechanics from ordinary users.

## 3. Repository boundary

Implementation is child-first in `projects/cockpit`:

- portfolio command module;
- focused command/projection tests;
- project interface declaration and user-facing help.

Only after the child PR, CI, main ancestry, and source tag are proven may the
root update the exact `projects/cockpit` gitlink in a standalone root-last
transaction.

## 4. Required behavior

- Missing projection returns `unavailable` and a recovery pointer.
- Digest mismatch fails closed.
- No command directly opens or writes the Ledger.
- No command completes a BET, KR, Milestone, Campaign, or Vision.
- The CLI and control projection report the same source digest.
- A non-expert can understand the critical path and blocker without knowing
  BOS, WorkPacket, workflow-run, or gitlink terminology.

## 5. Prospective write surfaces

- exact child portfolio command/test/interface paths selected during
  writing-plans after reading the current Cockpit constitution
- this Spec and its future implementation plan/retro
- root `projects/cockpit` gitlink only in a later dedicated pointer PR

## 6. Error and rollback contract

Unavailable, stale, malformed, or digest-mismatched projections never trigger
a fallback inference. Rollback removes the read-only command and root pointer
successor while preserving all Portfolio source and projection evidence.

## 7. Authority boundary

This accepted Spec establishes binding identity only. It does not authorize
writing-plans, child code, tests, interface changes, gitlink updates,
Ledger/OMO writes, W1-W6, or value evidence. Writing-plans requires a separate
post-binding authorization.

## 8. 验收标准

| ID | assertion | evidence_type | verifier |
|---|---|---|---|
| AC-T8-05-01 | Four Cockpit portfolio commands consume the same digest-bound projection | integration_test | focused command suite |
| AC-T8-05-02 | Missing, stale or mismatched projection returns explicit unavailable | negative_test | projection failure fixtures |
| AC-T8-05-03 | Cockpit has no direct Ledger, Goals or OMO state writer | static_and_runtime_test | direct-I/O lint plus hostile fixture |
| AC-T8-05-04 | Ordinary output explains critical path and blockers without internal platform terms | usability_report | fixed user-story review |
| AC-T8-05-05 | Child PR/CI/main/tag precede a root-only reachable gitlink update | delivery_receipt | child/root immutable ancestry report |
| AC-T8-05-06 | CLI source digest equals control-projection source digest | contract_test | exact digest assertion |

## 9. 反指标

- Number of commands, panels, fields or rendered rows.
- A visually attractive page backed by stale or inferred data.
- Direct access to Ledger presented as faster integration.
- Child tests passing without root gitlink reachability.
- Technical detail exposure mistaken for user transparency.

## 10. Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|---|---|---|
| 1 | 新 dashboard/service/database/dispatcher vs Cockpit command family | extend Cockpit | 复用既有入口和投影 SSOT，不建第二控制面 |
| 2 | direct Ledger read/write vs control projection | read-only projection | 保护真值边界 |
| 3 | stale fallback vs unavailable | unavailable | 不制造假状态 |
| 4 | root-first vs child-first | child-first/root-last | 保护多仓可达性 |
| 5 | expert telemetry vs product language | product language | 用户不应理解内部平台 |
