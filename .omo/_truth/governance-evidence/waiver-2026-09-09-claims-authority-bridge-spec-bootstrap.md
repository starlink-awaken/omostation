---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: Claims Authority Bridge draft Spec bootstrap waiver
type: doc
---

# Claims Authority Bridge Draft Spec Bootstrap Waiver

## Principal authorization, verbatim

> 批准 Claims Authority Bridge 提案 SHA-256
> b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c
> 与 A2 Resident Status Purity 提案 SHA-256
> acefb7211a66b7cbbe7506c70c27e74108fcd833e55922802d7e439e48123205
> 的全部架构裁决和授权边界；按 Claims Bridge 优先、A2 随后的顺序进入各自
> Workspace draft Spec 自举。每次仅允许对应 draft/unbound Spec 与 bootstrap
> waiver，不修改 Ledger、BET、实现代码、测试、registry、历史 evidence、运行态
> 或保留 clone；书面 Spec 经复核前不得转 accepted、binding 或实施。

This transaction consumes only the Claims Authority Bridge portion. The A2
authorization remains sequentially pending until this draft-Spec transaction
has completed.

## Approved design identity

- Documents proposal:
  /Users/xiamingxing/Documents/学习进化/基建架构/织星主权智能操作系统文档库/30-实施与协同/2026-09-09-Claims-Authority-Bridge机制BET提案-v1.md
- Proposal SHA-256:
  b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c
- Approved scope: all architecture decisions and authorization boundaries.
- Selected architecture: OMO canonical claims broker with clone-local
  non-authoritative projection.

## Bootstrap identity

- Actor: codex-agent-os-recovery
- Delivery attempt: claims-authority-bridge-spec-20260909-01
- Managed full clone:
  /Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-spec-20260909-01/ws
- Branch:
  agent/codex-agent-os-recovery--claims-authority-bridge-spec-20260909-01
- Frozen and execution-time remote main:
  5fb98bd3f4a342b77c5a0560eaf13bc02ed5d893
- Provenance status/digest:
  ready / 01308b6f4fe454a059071f1775478c4ff5cb62f51fba9339716414fb80ed41b2
- Readiness status/digest:
  ready / 9b37e83dbb65cb19740b048a1cb4ecc16818011742adae7a8760d9b81ccb09ec
- Workflow run:
  20260909T122246Z-governance-state-mutation-6faa811c
- Workflow binding: unbound draft bootstrap.
- Affected-graph receipt:
  3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7

Before onboarding, the proposal digest, remote main, target paths, attempt
directory, branch, tag and open PR state were rechecked. No collision was
observed. The full clone initialized all 16 top-level submodules and passed
identity/provenance/readiness guard checks.

## Bootstrap health observation

The first standard bootstrap completed with registry lint PASS but aggregate
health FAIL. Its non-JSON output did not identify the failed component.
No workflow run, claim or repository write had occurred.

The subsequent read-only doctor reported every required integration, adapter
and contract check healthy. One zero-change JSON bootstrap reproduction then
returned report_ok=true and health_ok=true. No configuration, dependency,
service or repository file was changed between the failed and passing reads.
The initial failure is therefore retained as an unattributed transient
observation, not silently rewritten as success and not treated as proof of a
specific root cause.

The draft bootstrap proceeded only after current doctor and bootstrap health
both passed.

## Exact waiver boundary

AGCP_REQUIREMENT_ITERATION_GATE=0 was supplied only to the process that created
the single unbound workflow run above. It was not exported and is not supplied
to claims, edits, verification, compliance, Git, CI or closeout.

The run claimed exactly:

1. docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md
2. .omo/_truth/governance-evidence/waiver-2026-09-09-claims-authority-bridge-spec-bootstrap.md

The draft Spec remains:

- spec_version: 0.1.0
- status: draft
- bet_id: unbound
- implementation_authorized: false
- value_indicator_policy: false
- SHA-256:
  724a32746eca6c57db2cdb7263c376abb27351456bc4f0ef20f0561f20da6f34

## Prohibitions and residual truth

This waiver does not authorize:

- Ledger or BET creation/change;
- accepted status, Spec binding or WorkPacket;
- implementation code, tests, registry, projection, CI or branch protection;
- workflow-broker, claims-store, PublishIntent or host-service deployment;
- historical receipt, A1/A3 evidence or retained-clone mutation;
- completion/value evidence or any statement that the bridge is operational;
- A2 draft-Spec work before this transaction completes.

Publication, review and merge of this two-path draft are permitted only through
the normal default gates. If the known claims-authority mismatch blocks normal
publication, execution must stop and obtain a new exact-commit degraded
authorization; this waiver is not that authorization.

## Temporary delegated authorization

Principal statement, verbatim:

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

Interpretation recorded at 2026-09-09 under Asia/Shanghai:

- delegation expires at 2026-09-10T10:00:00+08:00;
- it covers the fine-grained, in-scope authorizations needed to continue the
  already approved Claims Bridge first and A2 second draft-Spec sequence;
- every exercised authorization must be recorded before or with the affected
  transaction and remain bounded to exact artifacts and reversible operations;
- it does not permit false evidence, force push, history rewrite, destructive
  cleanup, secret access, unreviewed host mutation, or value/completion claims.

For this exact two-path draft transaction, the delegated decision authorizes
one non-force degraded direct publication if the known fixed claims-authority
policy again rejects the managed clone's otherwise valid claims. The exception
is limited to the final exact commit(s), one annotated tag, one branch push,
one unique PR, required CI, squash merge and exact post-merge verification.
The PR must disclose the failed claim-verification result and must not claim a
claim-verified changeset. This decision is not a general publication policy and
does not authorize Spec acceptance, Ledger/BET binding or implementation.
