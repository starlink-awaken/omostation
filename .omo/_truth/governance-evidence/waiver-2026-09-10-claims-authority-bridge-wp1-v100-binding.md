---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-09
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.0.0 plan-only binding waiver
type: doc
---

# Claims Authority Bridge WP1 1.0.0 Plan-Only Binding Waiver

## Authority and delegated decision

Original approval, verbatim:

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

The delegation expires at `2026-09-10T10:00:00+08:00`. It covers related,
fine-grained, reversible and evidenced decisions, but not false evidence,
force/history rewrite, secrets, destructive host action, unsupported
completion/value claims or writes outside this exact transaction.

Under that delegation, the reviewed WP1 design is accepted as version 1.0.0
and allocated to unique candidate `BET-Y1Q4-T10-145`, child of the zero-write
parent `BET-Y1Q4-T10-143`. The initial WorkPacket authorizes only writing:

`docs/superpowers/plans/2026-09-10-claims-authority-bridge-wp1-shadow.md`

`implementation_authorized=false`, engineering is `NOT_STARTED`,
operational/value are `NOT_PROVEN`, overall is `evaluating`, and
`value_indicator_policy=false`. This transaction does not implement WP1,
create a store/receipt, activate v2, materialize WP2, change a runtime or claim
completion/value.

## Exact identities

- Draft PR/merge: `#3496` /
  `f9198ccf85aa844f44fc711e389782a9f863604a`.
- Draft SHA-256:
  `d271215e0b8c3fddbc24696eb1f46fb172e34599deeba8dcb15bf041b4851455`.
- Accepted Spec:
  `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`.
- Accepted SHA-256:
  `302bca4c509abc37b16e0cd1498de4217ffc961e7db9bc7231c3b1fb889aa2ba`.
- Binding:
  `repo://docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
  / `1.0.0` /
  `sha256:302bca4c509abc37b16e0cd1498de4217ffc961e7db9bc7231c3b1fb889aa2ba`
  / `decision://accepted/BET-Y1Q4-T10-145`.
- WorkPacket: `WP-BET-Y1Q4-T10-145` /
  `sha256:35654ba38b1b87803700e755a8d7d83ddc5c6a75f3c9e56e76bf9957fa9306b7`.
- Parent relation: `parent_bet_id: BET-Y1Q4-T10-143`.
- Execution dependencies: `depends_on: []`.

The transaction claims exactly the Spec, `docs/plans/3y-bet-ledger.yaml` and
this waiver. These three bootstrap paths are not copied into the plan-only
WorkPacket.

## Preserved failed attempts

Attempt01 produced commits `a3547e103a4733102cea16729fbe2e3d1b10bf35`
and `069d04deba60df587f46122334e80b9df05af219`. Attempt02 produced
`c41b285a9ee14dbd9f3e7aa8c52019cdc427c530`. Both passed Ledger/Portfolio
lint, 58/58 GaC and independent architecture/gate review. In both,
`clone-lifecycle changeset --verify-claims` truthfully returned the fixed-root
`claim_scope_violation` with `claim_verification.all_covered=false`; neither is
represented as a verified changeset or successful integrate.

Each attempt used its single authorized ordinary push. The default pre-push
hook stopped attempt01 on `projects/ecos` and attempt02 on `projects/metaos`,
both with proxied GitHub `LibreSSL SSL_connect: SSL_ERROR_SYSCALL`, before any
remote ref update. Both branches/tags were read back absent, main was unchanged,
their workflows closed blocked and all locks reached zero. Their clones and
external records remain evidence. Neither attempt was retried.

## New transport evidence and bounded amendment

Read-only diagnosis proved that this host's Git config forces GitHub HTTPS
through `127.0.0.1:7890`; direct GitHub transport timed out and is not a valid
fallback. Two alternating sweeps across all 16 submodule remotes measured:

- default HTTP/2 over the proxy: 30/32 success, one timeout and one
  `SSL_ERROR_SYSCALL` on different repositories;
- HTTP/1.1 over the same proxy: 32/32 success, no timeout or TLS error.

The failed repositories passed on another sweep, so the failure is transient
and not repository-specific. A per-command Git `http.version=HTTP/1.1` setting
is exported through `GIT_CONFIG_PARAMETERS` to hook child Git processes. This
evidence supports a single command-level mitigation; it does not prove a
permanent fix and does not authorize global Git/proxy changes.

The earlier no-attempt03 circuit breaker prohibited blind repetition. Under the
temporary delegation it is superseded only by this new, independently measured
hypothesis. Exactly one evidence-driven attempt03 is authorized with no
attempt04.

## Attempt03 identity and publication boundary

- Delivery attempt: `claims-authority-bridge-wp1-binding-20260910-03`.
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-wp1-binding-20260910-03/ws`.
- Frozen main: `f9198ccf85aa844f44fc711e389782a9f863604a`.
- Provenance: `ready /
  b41b4823b23189bfe55790bf104befc99941e5bb805c5929e876bdf946636ac6`.
- Readiness: `ready /
  19c68f9d38a2d9360f2efa511d0917392a240e576d06a9ad880b175579343b87`.
- Workflow: `20260909T222652Z-governance-state-mutation-a0af02c7`.
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`.
- Branch:
  `agent/codex-agent-os-recovery--claims-authority-bridge-wp1-binding-20260910-03`.
- Tag: `claims-authority-bridge-wp1-binding-20260910-03`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was used only on the one unbound start.
Claims, edits, validation, commit, tag, hook, CI and closeout use default policy.

Attempt03 may create one content commit. It must reproduce the accepted digest,
one-path WorkPacket, 383/383 Ledger, strict Portfolio, full GaC and independent
reviews, then run the standard changeset verifier. If and only if the sole
failure is the proven fixed-root `claim_scope_violation` with
`all_covered=false`, it may create one annotated tag and execute exactly one:

`git -c http.version=HTTP/1.1 push origin <branch-ref> <tag-ref>`

This is an ordinary non-force push. The default hook remains enabled and every
blocking check still executes; only the proxied HTTP transport version changes.
One unique PR may then be created. The PR must disclose unverified claims and
must not claim integrate success.

Any other local, hook, remote or CI failure stops with no push retry and no
attempt04. Only green `phase-gate`, `bet-done-transition` and `gac-gate` permit
squash merge. Exact three-path patch/digest/Ledger and exact merge-SHA workflows
must then pass before blocked closeout, six locks zero and settled retirement.

## Prohibitions

This waiver does not authorize the plan itself, `implementation_authorized=true`,
1.1.0+, WP1 code/tests/store/activation, WP2, another BET/binding, completion or
value evidence, gitlink/hook/CI/branch-protection changes, runtime/host/database/
user-config mutation, rebase, merge, pull, force, force-with-lease,
`--no-verify`, a global Git/proxy change, push retry or attempt04.
