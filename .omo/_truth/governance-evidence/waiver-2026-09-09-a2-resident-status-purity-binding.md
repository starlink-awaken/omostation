---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: A2 Resident Status Purity accepted child-binding waiver
type: doc
---

# A2 Resident Status Purity Accepted Child-Binding Waiver

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
`2026-09-10T10:00:00+08:00`. It covers related, fine-grained, reversible and
evidence-recorded decisions. It does not permit false evidence, force push,
history rewrite, destructive cleanup, secret access, unreviewed host mutation
or unsupported completion/value claims.

## Delegated accepted-binding decision

Claims Bridge parent PR `#3491` merged first at
`b60f3ad3c8db7219944a8bc6f4fb1a9b3e727f3a`. The A2 draft then received an
independent read-only pre-acceptance audit. The audit confirmed the CQS design,
A3 receipt boundary, RED matrix and value isolation, and identified one
mechanical gap: the current Ledger compiler cannot isolate child and root
stages if their paths are exposed together.

Under the temporary delegation, the gap is resolved before acceptance and the
following exact decision is recorded:

> Accept A2 Resident Status Purity as Spec 1.0.0 and bind collision-free
> candidate `BET-Y1Q4-T10-144`. Authorize only the four-path
> `WP-A2-CHILD` RED-to-GREEN implementation after this binding merges. Do not
> authorize the root gitlink, host canary, recovery command, service/database/
> process mutation, historical evidence rewrite, completion transition or
> value claim. After the child run closes and the merged child commit is proven
> reachable from authoritative child main, a later reviewed binding revision
> must replace the child paths with only `projects/omo`; it must never union the
> two scopes.

This transaction uses `AGCP_REQUIREMENT_ITERATION_GATE=0` only for its one
unbound workflow start. Claims, edits, verification, compliance, Git, CI and
closeout use default policy.

## Accepted design identity

- Documents proposal SHA-256:
  `acefb7211a66b7cbbe7506c70c27e74108fcd833e55922802d7e439e48123205`
- Draft merge PR/SHA:
  `#3486 / 7aaa87d619f2c04ff43fefdcc07b0ec6b031072b`
- Reviewed draft 0.1.0 SHA-256:
  `e848944e1b51518c540883cde98a83481a294fdf884176f948b59b4d013d0d98`
- Accepted 1.0.0 SHA-256:
  `8518e8ec12372d127a49965be651fd593be0030350cc454064ad3ee7a63b59b6`
- Accepted path:
  `docs/superpowers/specs/2026-09-09-a2-resident-status-purity-truth-recovery-design.md`
- Binding identity:
  `repo://docs/superpowers/specs/2026-09-09-a2-resident-status-purity-truth-recovery-design.md`
  / `1.0.0` /
  `sha256:8518e8ec12372d127a49965be651fd593be0030350cc454064ad3ee7a63b59b6`
  / `decision://accepted/BET-Y1Q4-T10-144`

## Dynamic collision and baseline proof

Immediately before clone creation and workflow start:

- remote `main` was stable across two reads at
  `b60f3ad3c8db7219944a8bc6f4fb1a9b3e727f3a`;
- the live Ledger contained 381 entries and `meta.total_bets=381`;
- `BET-Y1Q4-T10-144` was absent;
- no remote head matched T10-144, A2 Resident Status Purity or the binding
  attempt;
- no open PR modified the Ledger, the A2 Spec or its binding path;
- remaining open PRs modified unrelated gitlinks/registry/resident-generated
  surfaces and did not overlap this transaction.

This transaction adds exactly one candidate and derives
`meta.total_bets=382`. It does not reserve another ID or modify another BET.

## Bootstrap identity

- Actor: `codex-agent-os-recovery`
- Delivery attempt: `a2-resident-status-purity-binding-20260909-01`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a2-resident-status-purity-binding-20260909-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--a2-resident-status-purity-binding-20260909-01`
- Frozen main:
  `b60f3ad3c8db7219944a8bc6f4fb1a9b3e727f3a`
- Manifest digest:
  `0d377182bd7d21d3bc3362309a3634ce77872945b92968d363676f5f4f6a9b9b`
- Provenance status/digest:
  `ready / 330dcfa2b703dcc336f0746b68af8b6c20318d75534c86994de16f8bfdca162c`
- Readiness status/digest:
  `ready / d29da61dee5b2ea8cfb68cbf533b40656d0e14e83d168011fa7ac59406f10378`
- Workflow run:
  `20260909T150325Z-governance-state-mutation-52d459e8`
- Workflow binding: unbound accepted-binding bootstrap.
- Affected-graph receipt:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

The clone initialized all 16 top-level submodules and passed manifest,
provenance and readiness verification. The first acceleration attempt was
rejected before clone creation with `submodule_source_set_mismatch` because a
full profile requires exact transport mappings for every selected root
gitlink. No incomplete clone or workflow state was created; the successful
attempt used an ordinary authoritative full clone without acceleration.

## Exact binding and implementation boundary

The unbound binding run claims exactly:

1. `docs/superpowers/specs/2026-09-09-a2-resident-status-purity-truth-recovery-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. `.omo/_truth/governance-evidence/waiver-2026-09-09-a2-resident-status-purity-binding.md`

The generated 1.0.0 WorkPacket must expose only:

1. `projects/omo/src/omo/resident/status.py`
2. `projects/omo/src/omo/resident/ledger_check.py`
3. `projects/omo/tests/unit/test_resident_status.py`
4. `projects/omo/tests/unit/test_ledger_check.py`

`projects/omo` is intentionally absent. A root-only amendment requires a new
accepted Spec digest, a replacement write set, a new WorkPacket hash and a
fresh run after the child run is closed and child-main reachability is proven.

`pasw_required` is explicitly `false`. The A2 child is delivered inside the
initialized `projects/omo` repository of a verified managed full independent
clone, with its own child PR. The retired `.subtrees` PASW topology must not be
created or used. The root repository remains untouched until the later
root-only replacement binding.

The corrected binding was measured before commit:

- generated WorkPacket:
  `WP-BET-Y1Q4-T10-144` /
  `sha256:7cecdb9f2ad856e3366e3e5af7b82eb011859681a595c767be82ffd88f3b4cfd`;
- a child claim for `projects/omo/src/omo/resident/status.py` validated;
- a root claim for `projects/omo` returned `WORK_PACKET_SCOPE_MISMATCH`;
- canonical Ledger lint reported `382 bets, 11 tracks, no errors`;
- T10-142 remained `candidate/evaluating`, with operational/value
  `NOT_PROVEN`.

Two independent final reviews returned `APPROVED / CLEAR`. One review first
identified `pasw_required:true` as a mechanical contradiction because it would
direct execution toward the retired `.subtrees` topology. Before commit, that
single field was corrected to `false`; a diff audit confirmed no other PASW
field changed, and the final review confirmed the contradiction was closed.

## Preserved truth boundaries

- `BET-Y1Q4-T10-142` remains candidate/evaluating with operational/value
  `NOT_PROVEN` and is not a Ledger dependency.
- Claims Bridge T10-143 is not misrepresented as a completed engineering
  dependency; its publication-route evolution remains separate.
- A3 contributes only its five exact engineering receipts already listed in
  the accepted Spec.
- T10-48 and T10-126 historical completion/value evidence is unchanged.
- Initial A2 matrix is engineering `NOT_STARTED`, operational/value
  `NOT_PROVEN`, overall `evaluating`, value policy false.

## Prohibitions

This waiver does not authorize:

- root `projects/omo` gitlink modification or a child/root union WorkPacket;
- root-scope binding amendment, root workflow or root PR in this transaction;
- host canary, `resident-recover`, checkpoint, kill, restart, `launchctl`,
  database repair or user/host configuration change;
- any path outside the four child paths during implementation;
- modification of another BET, historical receipt, completion/value evidence,
  registry, hook, CI or branch protection;
- force, force-with-lease, rebase, merge, pull, `--no-verify` or degraded direct
  publication;
- any claim that A2 engineering, operation, value or overall completion is
  already proven.

Publication of this exact three-path binding requires default verification,
independent review, normal non-force Git publication and all required CI.
