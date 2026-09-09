---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: Claims Authority Bridge draft R0 closure amendment waiver
type: doc
---

# Claims Authority Bridge Draft R0 Closure Amendment Waiver

## Original Principal authorization, verbatim

> 批准 Claims Authority Bridge 提案 SHA-256
> `b6c54868a3cda277cfa27fd7643dd3a2cde118a34c51c9f56d1b567f3d41d14c`
> 与 A2 Resident Status Purity 提案 SHA-256
> `acefb7211a66b7cbbe7506c70c27e74108fcd833e55922802d7e439e48123205`
> 的全部架构裁决和授权边界；按 Claims Bridge 优先、A2 随后的顺序进入各自
> Workspace draft Spec 自举。每次仅允许对应 draft/unbound Spec 与 bootstrap
> waiver，不修改 Ledger、BET、实现代码、测试、registry、历史 evidence、运行态
> 或保留 clone；书面 Spec 经复核前不得转 accepted、binding 或实施。

The original Claims Bridge draft merged in PR #3485 at
`e1d36dc8f36b2acdf1a8beea4c289a16d9aae045`. Its exact Spec SHA-256 was
`724a32746eca6c57db2cdb7263c376abb27351456bc4f0ef20f0561f20da6f34`.
The A2 draft then completed in PR #3486 at
`7aaa87d619f2c04ff43fefdcc07b0ec6b031072b`. Both bootstrap clones retired
with external proof/delete-intent/settlement chains.

## Independent acceptance audit

After the original draft landed, an independent read-only audit returned
`NEEDS_AMENDMENT`. It found that the draft itself prohibited acceptance until
five R0 questions were closed, while those questions remained open. It also
found contradictory v1 shadow language, an incorrect WP count, missing object
and durability contracts, an unspecified Git effect owner, incomplete
brownfield write surfaces, no measurable cutover gate, and no redacted
Dashboard observer contract.

The audit did not reject the one-OMO architecture, R0/R1 separation or
one-shot intent model. It required those choices to become executable and
internally consistent before any accepted transition. Therefore the draft is
amended rather than accepted as-is.

## Temporary delegated authorization

Principal statement, verbatim:

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

Interpretation recorded on 2026-09-09 under Asia/Shanghai:

- delegation expires at `2026-09-10T10:00:00+08:00`;
- it covers related fine-grained, reversible and evidence-recorded decisions
  needed to continue the already approved execution-environment recovery;
- it does not permit false evidence, force push, history rewrite, destructive
  cleanup, secret access, unreviewed host mutation, or completion/value claims;
- an existing draft may be clarified under a new exact waiver, but it cannot be
  silently marked accepted, bound or implemented.

## Delegated amendment decision

Under that delegation, the following exact amendment is authorized:

> Advance the Claims Authority Bridge draft from 0.1.0 to 0.2.0 while keeping
> `status: draft`, `bet_id: unbound`, `implementation_authorized: false` and
> `value_indicator_policy: false`. Resolve only the independent R0 acceptance
> findings in the existing Spec and record this waiver. Do not modify Ledger,
> BET, implementation code, tests, registry, gitlink, historical receipts,
> branch protection, service/database state or user configuration. Use
> `AGCP_REQUIREMENT_ITERATION_GATE=0` only for one fresh unbound workflow start;
> claims, edits, verification, compliance and Git use default policy. Require a
> new independent review before any accepted-binding transaction.

The exact human-authored tracked paths are:

1. `docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md`
2. `.omo/_truth/governance-evidence/waiver-2026-09-09-claims-authority-bridge-draft-amendment.md`

## R0 decisions recorded

The amendment makes these bounded personal-MVP decisions:

1. `omo-claims-authority-r0` uses a dedicated `0700` authority directory, DB,
   high-water sidecar and three-backup rotation under the passwd-resolved
   account home; production resolution ignores environment, cwd, clone and CLI
   path overrides without chmod of shared ancestors.
2. R0 uses a one-request canonical stdio subprocess from the account
   integration root. No daemon, UDS, LaunchAgent or host install is added.
3. The claims command dispatches before non-stdlib Workspace imports. A
   non-self-referential descriptor closure binds every critical local object,
   gitlink and runtime receipt. Test stores create `test:*`, non-publishable
   receipts and cannot enter production verification.
4. `clone-lifecycle integrate --apply` remains the sole Git effect owner. The
   broker moves intent and claim into durable `publishing`, freezes competing
   mutations, and settles but never runs Git.
5. During WP1, v1 remains effective only for its already accepted legacy
   roots; it never admits a managed clone. v2 is observation-only. Every v1
   Git effect receives a broker fence so its epoch can be drained safely.
6. WP1 graduation requires 24 hours, three lifecycle classes, the full RED
   matrix, no unexplained difference and no v2 false-allow.
7. WP2 first closes legacy-fence issuance and drains
   issued/publishing/unknown/operator_required effects or markers, then merges
   one requested-mode policy transaction and performs one
   descriptor-bound broker activation CAS. v2 becomes sole authority; v1
   becomes read-only. Rollback drains v2 and enters `human-degraded-only`, not
   back to v1 authority.
8. Receipt/intent/settlement/projection/status schema IDs, canonical JSON,
   SHA-256, UUID idempotency, lease/TTL, CAS and typed errors are fixed.
9. DB/high-water gaps fail closed; only a one-record complete crash tail may
   reconcile. Corruption never auto-restores.
10. The R0 canary uses one plain non-force push to a proven-absent unique
    attempt branch. Existing force-with-lease publication does not satisfy it.
11. Dashboard reads only a redacted 120-second status API with
    `instruction_capable=false`.
12. The parent contains WP0 binding, WP1 shadow and WP2 enforce. R1 is a
    separate future Spec/BET/host authorization.

## Bootstrap identity

- Actor: `codex-agent-os-recovery`
- Delivery attempt: `claims-authority-bridge-amendment-20260909-01`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-amendment-20260909-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--claims-authority-bridge-amendment-20260909-01`
- Frozen and execution-time remote main:
  `7aaa87d619f2c04ff43fefdcc07b0ec6b031072b`
- Provenance status/digest:
  `ready / 751b98c0b387890752a56aa5da9710449a0b4601caad1a907701f9f9225ff136`
- Manifest digest:
  `e2f536e2c406a0c4734cb64925a8f5fe8643ce0a4994486c9f31373831dce202`
- Readiness status/digest:
  `ready / 62211cfb2fbe29b1ea5f4b4ff94a2e5bb618428a2cdc04b77ea69cb4d8daab32`
- Workflow run:
  `20260909T132347Z-governance-state-mutation-47c610e8`
- Workflow binding: unbound draft amendment.
- Affected-graph receipt:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

The full clone initialized all 16 top-level submodules and passed root/child
manifest verification, repository provenance and full-profile readiness.

## Exact waiver boundary

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the process that
created the single unbound run above. It was not exported and is not supplied
to affected-graph generation, claims, edits, verification, compliance, Git,
CI or closeout.

Workflow records, locks and the ignored affected-graph receipt are transient
governance controls inherent in this authorized amendment. No business/service
runtime, database, scheduler or user configuration is modified.

The final amended Spec remains:

- `spec_version: 0.2.0`
- `status: draft`
- `bet_id: unbound`
- `implementation_authorized: false`
- `value_indicator_policy: false`
- SHA-256:
  `51ceb04cfab4985cee1a453ec132ea513ec36b46d923f418e002feb4984b4db9`

Two independent read-only reviewers challenged the first v0.2 draft. Their
findings drove explicit fixes for mode namespaces, production-unbound
rejection, policy/descriptor self-reference, critical import closure, durable
claim publication state, legacy v1 cutover fencing, bodyless status syntax,
heartbeat interval wording, dedicated-store permissions and the non-terminal
`operator_required` marker. After those amendments:

- reviewer 1 returned `APPROVED / CLEAR`;
- reviewer 2 returned `ACCEPTABLE_DRAFT / CLEAR`, with no contradictions,
  blocking ambiguity, missing R0 constraint or topology gap;
- neither reviewer edited files, fetched Git state, started a workflow or
  changed runtime state.

## Prohibitions

This waiver does not authorize:

- `status: accepted`, BET ID, Ledger entry or accepted-specification binding;
- implementation, test, registry, gitlink, hook, CI or branch-protection
  changes;
- creation, migration, backup or recovery of a claims store;
- broker execution, PublishIntent issue/consume, Git canary or Dashboard
  mutation;
- modification or deletion of A1/A2/A3 receipts or retained evidence;
- R1 design/host operations;
- completion/value evidence or any claim that the bridge is operational.

Publication of this two-path draft amendment may proceed only through default
verification, independent review and required CI. If fixed claims-authority
policy rejects normal publication, the exact failure and any one-time delegated
publication decision must be appended before publication.
