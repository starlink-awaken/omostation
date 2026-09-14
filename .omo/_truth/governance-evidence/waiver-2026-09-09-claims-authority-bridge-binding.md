---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: Claims Authority Bridge accepted binding waiver
type: doc
---

# Claims Authority Bridge Accepted Binding Waiver

## Principal authority chain

Original proposal approval, verbatim:

> 批准 Claims Authority Bridge 提案 SHA-256
> `b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c`
> 与 A2 Resident Status Purity 提案 SHA-256
> `acefb7211a66b7cbbe7506c70c27e74108fcd833e55922802d7e439e48123205`
> 的全部架构裁决和授权边界；按 Claims Bridge 优先、A2 随后的顺序进入各自
> Workspace draft Spec 自举。每次仅允许对应 draft/unbound Spec 与 bootstrap
> waiver，不修改 Ledger、BET、实现代码、测试、registry、历史 evidence、运行态
> 或保留 clone；书面 Spec 经复核前不得转 accepted、binding 或实施。

Temporary delegation, verbatim:

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

The delegation is interpreted under Asia/Shanghai and expires at
`2026-09-10T10:00:00+08:00`. It covers related fine-grained, reversible and
evidence-recorded authorization decisions. It does not permit false evidence,
force push, history rewrite, destructive cleanup, secret access, unreviewed
host mutation or completion/value claims.

## Delegated WP0 decision

The Claims Bridge draft was reviewed iteratively until two independent
read-only reviewers returned `APPROVED / CLEAR` and
`ACCEPTABLE_DRAFT / CLEAR`. Under the temporary delegation, the following
exact decision is recorded:

> Accept the reviewed Claims Authority Bridge R0 architecture as Spec 1.0.0 and
> bind exactly one collision-free candidate `BET-Y1Q4-T10-143`. This transaction
> is WP0 only. Keep `implementation_authorized: false`, engineering
> `NOT_STARTED`, operational/value `NOT_PROVEN`, overall `evaluating`, and
> `value_indicator_policy: false`. Do not create the authority store, implement
> WP1/WP2, modify a runtime, or claim completion/value. Use
> `AGCP_REQUIREMENT_ITERATION_GATE=0` only for the one unbound binding start;
> all later steps use default policy.

## Accepted design identity

- Documents proposal SHA-256:
  `b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c`
- Draft 0.2 merge PR/SHA:
  `#3488 / d0d6ccb12e8429f464d6e79df693ca2314316be3`
- Reviewed draft 0.2 SHA-256:
  `51ceb04cfab4985cee1a453ec132ea513ec36b46d923f418e002feb4984b4db9`
- Accepted 1.0.0 SHA-256:
  `a419e2fb3cd67026edebd39b25a1e1b77e6c92978ce1cf1be6b8e4be19cf8c58`
- Accepted path:
  `docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md`
- Binding identity:
  `repo://docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md`
  / `1.0.0` / `sha256:a419e2fb3cd67026edebd39b25a1e1b77e6c92978ce1cf1be6b8e4be19cf8c58`
  / `decision://accepted/BET-Y1Q4-T10-143`

## Dynamic collision and baseline proof

Immediately before the binding clone was created:

- remote main was
  `d0d6ccb12e8429f464d6e79df693ca2314316be3`;
- `BET-Y1Q4-T10-143` was absent from the remote Ledger;
- no remote head matched T10-143 or the binding attempt;
- no open PR modified `docs/plans/3y-bet-ledger.yaml` or matched the Claims
  Bridge binding;
- the Ledger contained 380 entries and `meta.total_bets` was 380;
- canonical Ledger lint returned no errors.

This transaction adds exactly one candidate and derives
`meta.total_bets=381`. It does not reserve another ID or modify another BET.

Immediately before commit/publication, remote `main` had advanced by one
unrelated documentation-only commit to
`e93612f00ad1958e036aa4dc79b1ab2db1f387d2`. The only intervening path was
`docs/architecture/ops-services-health.md`; none of this transaction's three
paths or any gitlink changed. Open PR `#3490` changed only `projects/cockpit`,
and the other open PRs were gitlink-only. No open Ledger writer or Claims
Bridge binding collision was observed. The immutable clone remains based on
its recorded frozen root and does not rebase or absorb the unrelated commit.

## Canonical WorkPacket semantics and reviewer correction

The stricter independent review found that the current Ledger compiler copies
all BET `write_surfaces` into one canonical WorkPacket and the claim validator
checks only membership in that union. It has no stage field or stage-aware
fence. Therefore prose could not truthfully prevent WP1 from claiming a WP2
path.

Under the temporary delegation, the stricter finding is adopted and the
changeset is corrected before commit:

- `BET-Y1Q4-T10-143` is a portfolio-only parent;
- its canonical `WP-BET-Y1Q4-T10-143` has an empty implementation write set;
- WP1 and WP2 are future child BETs with independent accepted Specs and exact
  WorkPackets;
- WP1 is proposed only after this parent binding merges;
- WP2 is not materialized in the Ledger and has no binding until WP1 is done;
- `depends_on` records the later graph edge but is not misrepresented as the
  sole workflow-start fence;
- R1 remains a separate future Spec/BET/host authorization.

This is the minimal mechanism-compatible model: the parent cannot claim an
implementation path, and no later-stage executable identity exists early.

The corrected contract was measured before commit:

- accepted Spec SHA-256:
  `a419e2fb3cd67026edebd39b25a1e1b77e6c92978ce1cf1be6b8e4be19cf8c58`;
- generated WorkPacket:
  `WP-BET-Y1Q4-T10-143` /
  `sha256:8f709dc8f236545f2b12f3f689e740ba4b9bbd98eec6515ac6d27550d330d9be`;
- generated `scope.write_surfaces`: `[]`;
- a validation probe for `bin/agent-workflow.py` returned
  `WORK_PACKET_SCOPE_MISMATCH`;
- canonical Ledger lint reported `381 bets, 11 tracks, no errors`;
- the stricter independent reviewer returned `APPROVED / CLEAR` after the
  correction;
- a second independent acceptance audit also returned `APPROVED / CLEAR` and
  confirmed that no WP1/WP2 Ledger identity, binding or unsupported
  `work_packets` field exists.

## Bootstrap identity

- Actor: `codex-agent-os-recovery`
- Delivery attempt: `claims-authority-bridge-binding-20260909-01`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-binding-20260909-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--claims-authority-bridge-binding-20260909-01`
- Frozen main:
  `d0d6ccb12e8429f464d6e79df693ca2314316be3`
- Provenance status/digest:
  `ready / d05d91f286e482347a8469bab2f8203bf2ceef910b83d2219c58bd30f63225ff`
- Manifest digest:
  `94c70e1918d97e1fdd3b025c5262ff82b6ab2caeba0728258893148229a87240`
- Readiness status/digest:
  `ready / 31342ffac9b3fb1c607ae4ee1889c545c7430a678744ff0c92327f52bdf2aa05`
- Workflow run:
  `20260909T141753Z-governance-state-mutation-68fa5002`
- Workflow binding: unbound WP0 bootstrap.
- Affected-graph receipt:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

The full clone initialized all 16 top-level submodules and passed
identity/provenance/readiness verification.

## Exact scope and gate boundary

The run claims exactly:

1. `docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. `.omo/_truth/governance-evidence/waiver-2026-09-09-claims-authority-bridge-binding.md`

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the process that
created the single unbound run. It was not exported and is not supplied to
affected-graph generation, claims, edits, verification, compliance, Git, CI or
closeout.

## Prohibitions

This waiver does not authorize:

- WP1/WP2 implementation or `implementation_authorized: true`;
- authority DB/high-water/backup creation or broker activation;
- code, test, registry, gitlink, hook, CI or branch-protection changes;
- v1 drain, v2 cutover, Git canary, service/database/host/user-config mutation;
- another BET, multiple accepted bindings or a `work_packets` Ledger field;
- implementation write surfaces on the parent or pre-materialization of a WP1
  or WP2 child in this transaction;
- modification of T10-142, historical receipts, completion/value evidence;
- R1 design/host work;
- any statement that Claims Bridge engineering or operation is proven.

Publication of this exact three-path WP0 transaction requires default
verification, independent review and required CI. If the fixed claims-authority
policy rejects normal publication, the exact failure and one-time delegated
publication decision must be appended before publication.
