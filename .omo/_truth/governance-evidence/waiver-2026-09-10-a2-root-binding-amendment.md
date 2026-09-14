---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: A2 root-only accepted binding replacement waiver
type: doc
---

# A2 Root-Only Binding Replacement Waiver

## Temporary principal delegation

Verbatim authority:

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

This delegation is interpreted in Asia/Shanghai and expires at
`2026-09-10T10:00:00+08:00`. It authorizes this reversible repository-only
accepted-binding replacement because it is the predeclared next stage of A2
after child delivery. It does not authorize the pointer change in this PR,
host/runtime mutation, recovery/restart/kill, completion/value transition,
force/history rewrite, or false evidence.

Frontmatter dates use the UTC calendar date; the filename uses the concurrent
Asia/Shanghai date.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
workflow start `20260909T183506Z-governance-state-mutation-7903b382`. Claims,
validation, Git, CI and closeout use default policy.

The Spec, machine Ledger binding and authorization record form one atomic
cross-lane contract. The official process-local interface
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state` is authorized
only for this transaction's validation and Git hooks. Advisory mode,
`--no-verify`, persistent environment changes or additional lanes are not
authorized.

## Why a replacement is required

The WorkPacket compiler copies the complete Ledger `write_surfaces` list and
has no stage-aware path fence. Accepted Spec 1.0.0 and its immutable child runs
therefore exposed exactly four OMO source/test paths. Appending the root
gitlink would authorize an unsafe child/root union.

The child stage is now directly proven:

- prerequisite RLM baseline PR #151 merged as
  `e2a75531b5f1926d56b3badd9c43b86c22ba864c` with required and post-merge CI
  green;
- A2 child PR #152 merged as
  `edf2301e9344cbfbeb90599f405acb8cc29d9301` with required and post-merge CI
  green;
- authoritative child main equals `edf2301e9344cbfbeb90599f405acb8cc29d9301`;
- reviewed A2 four-path aggregate SHA-256 is
  `012a978e3a4716ea3d85fb9f05517ac15a2ee147d7bb905e1327f599db94f42b`;
- final child run `20260909T181237Z-bet-execution-c8a91b9c` closed blocked
  after delivery and released all six locks.

These facts are engineering prerequisites only. They are not copied into the
completion matrix and do not prove host operation or personal value.

## Version decision

Version 1.1.0 is used instead of 1.0.1. Repository precedent reserves patch
versions for corrections that do not add an implementation surface; this
amendment materially revokes four child paths for new runs and authorizes a
new root gitlink stage with a new WorkPacket hash. Historical 1.0.0 runs and
evidence remain immutable and readable.

## Exact scope

1. `docs/superpowers/specs/2026-09-09-a2-resident-status-purity-truth-recovery-design.md`
2. `docs/plans/3y-bet-ledger.yaml`, only the complete
   `BET-Y1Q4-T10-144` entry fields required for the replacement
3. this waiver

This transaction must not change `projects/omo` or any other gitlink.

## Clone, workflow and collision proof

- Root baseline: `0941c21d5eca3580af928d6a930afded8645f676`
- Root gitlink before amendment:
  `projects/omo=db7217913dc95f727f26d66b9f7df5675404077b`
- Full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a2-root-binding-replacement-20260910-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--a2-root-binding-replacement-20260910-01`
- Provenance: `ready /
  8aef8e65e1003df2cd979c838ec4585ecaa19cd3e073f65e5287c3311acf371b`
- Readiness: `ready /
  a09fbb98e88dc984b5d0e69b1530ecbc12d1f2a58c37255492429ac6f6767595`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

Execution-time root main was read as the exact baseline. The three open root
PRs (#3472, #3464 and #3447) were inspected and none touches this Spec, the
Ledger, this waiver, or `projects/omo`. No active writer or lock overlapped the
three paths before start.

## Old and new immutable binding

| Field | Delivered child binding | Root replacement binding |
|---|---|---|
| Spec version | `1.0.0` | `1.1.0` |
| Spec SHA-256 | `8518e8ec12372d127a49965be651fd593be0030350cc454064ad3ee7a63b59b6` | `e0b0c3949fea84a85121a70e2da2bd9c02884eeba40425d4907f7743cdb87126` |
| WorkPacket hash | `sha256:7cecdb9f2ad856e3366e3e5af7b82eb011859681a595c767be82ffd88f3b4cfd` | `sha256:d3c20409ee196964a8f9c9760945e29c24b0b936898e6aa71b29aa0d19a05f24` |
| New-run write surfaces | four child source/test paths | exactly `projects/omo` |

The Ledger retains one accepted-specification binding and the same decision
reference. It replaces, rather than appends, the version/digest and
`write_surfaces`. The compiled 1.1.0 packet was inspected and contains exactly
`["projects/omo"]`; none of the four child paths survives.

The following remain byte-semantically unchanged: `status: candidate`, no
`done_at`, `depends_on: []`, completion engineering `NOT_STARTED`, operational
and value `NOT_PROVEN`, overall `evaluating`, value-indicator policy false,
and every T10-142 field/evidence.

## Verification and next transaction

Ledger lint passes with `382` BETs and `11` tracks. Before publication this
transaction must also pass exact Spec digest recomputation, WorkPacket
recompilation, replacement/negative-union assertions, default workflow
verify/compliance, local GaC, independent review and all required PR checks.

Only after this binding PR merges may a new managed full clone start a fresh
bound T10-144 run, claim only `projects/omo`, and publish a one-gitlink root
pointer PR. The pointer must target `edf2301e9344cbfbeb90599f405acb8cc29d9301`
or a re-proven authoritative child-main descendant containing it. A 100/100
host canary remains a separate third transaction and requires its own
operation-specific authorization record.

## Stop and rollback

Stop if the three-path diff expands, the compiled packet contains any child
source/test path, Spec/WorkPacket digests drift, candidate/completion/value or
T10-142 changes, the root gitlink changes in this PR, child main no longer
contains both merges, a writer collides, or a default/required gate fails.
Rollback is an ordinary reviewed binding PR restoring version 1.0.0 and its
four child paths; it does not rewrite the already closed child runs.
