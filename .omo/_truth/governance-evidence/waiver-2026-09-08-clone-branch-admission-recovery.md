---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-09
last-reviewed: 2026-09-09
value_indicator_policy: false
title: A1 R0 dual-track independent-clone branch admission recovery
type: doc
---

# A1 R0 Dual-Track Independent-Clone Branch Admission Recovery

## Principal authorization, verbatim

> 批准 A1 R0 双轨恢复：第一事务仅将 /Users/xiamingxing/runtime/matrix.yaml 中 ollama 条目的 type: "daemon" 改为 type: "integrated"，保留其他服务、字段和运行态不变，记录修改前后 SHA-256，验证 Ollama 11434/API 健康与 matrix-consistency；失败立即恢复原值。第二事务保留且不提交已 blocked 的 a1-branch-recovery-20260908-01，从执行时最新 main 创建唯一 full successor attempt a1-branch-recovery-20260909-02；明确批准 A1 提案 SHA-256 9ab2f97095b365c54f7c9de25f78e87053b8f93a3080f261364f71db8fe27f77 第6节 R0 原文，允许 AGCP_REQUIREMENT_ITERATION_GATE=0 仅作为该 successor 一次 unbound start 的进程级命令前缀，之后 claim、verify、compliance、Git、CI、closeout 均使用默认门；人工 tracked 写面仍严格限于原三路径，全部 required checks 全绿后方可合并、exact-SHA 验证并退役 successor clone；不得进入 R1、修改 Ledger/BET、价值证据、其他治理规则或业务运行态。

This waiver binds the authorization to the two transactions below. It is not
a standing gate bypass and does not authorize R1, another attempt, or another
repository/runtime surface.

## Approved source

- Proposal:
  `/Users/xiamingxing/Documents/学习进化/基建架构/织星主权智能操作系统文档库/30-实施与协同/A1分支契约与恢复自举提案-v1.md`
- Proposal SHA-256:
  `9ab2f97095b365c54f7c9de25f78e87053b8f93a3080f261364f71db8fe27f77`
- Approved portion: Section 6, R0 only.

## Transaction 1 — host matrix classification

The pre-change `/Users/xiamingxing/runtime/matrix.yaml` SHA-256 was
`4bc2d3bbacabf4791f8f73e3228a43cf042ebb3ff9bd15da8f95718169170cd1`.
The only intended and retained byte change is the Ollama entry's
`type: "daemon"` to `type: "integrated"`. The post-change SHA-256 is
`6bf435224100e9bbacac41cfda5449ba1b64e2b9a236d8a75baa3be3ba9e8f41`.

Replacing only that current Ollama line with its original value reconstructs
the complete pre-change SHA exactly. Independent postflight confirmed the
cron-service remains `type: "daemon"`, no other service or field changed, and
there is exactly one Ollama `integrated` classification.

The first narrow patch matched the earlier cron-service daemon line rather
than the named Ollama block. It was detected before any downstream action,
immediately restored with name-scoped context, and independently checked by a
four-combination SHA reconstruction. The transient intermediate SHA was
`f9ce220140062057183db8bebeafed3c577cb241bf807d97f610cdaf9808d58d`;
it is not the final state and left no residual byte.

Before and after the transaction, the same Ollama PID `70060` listened on
`127.0.0.1:11434`; `/api/tags` returned HTTP 200 and valid JSON with one model;
the dynamic Ollama.app launchd label remained unchanged. The exact
`matrix-consistency --skip-launchd` result changed from one R1 error to
`errors=[]`, `warnings=[]`, `ok=true`. No service was restarted or otherwise
mutated.

## Transaction 2 — successor identity and workflow

- Immutable clone base:
  `9b3238d117a65fb10786bb12f68b5a7a66c10c0c`
- Actor: `codex-agent-os-recovery`
- Delivery attempt: `a1-branch-recovery-20260909-02`
- Branch:
  `agent/codex-agent-os-recovery--a1-branch-recovery-20260909-02`
- Workflow run:
  `20260909T022611Z-governance-state-mutation-1a5b71e9`
- Workflow binding: unbound; final closeout must be `blocked`.
- Full-profile provenance digest:
  `218018f331def274aa5baaef79647db3967c26949b5f39ca14d22b4eb30bc661`
- Full-profile readiness digest:
  `19c127bbf6da0d21584941024c1063ae6097432bf6eec744f480db5b8b654561`

Preflight proved the attempt directory, local/remote branch, and every PR for
the target head were absent. No open PR touched the three authorized paths,
and the live base still carried the slash-only policy with neither the test
nor this waiver. Managed onboarding initialized all 16 root gitlinks and
verified clean root/child state, provenance, manifest, and readiness.

The initial `onboard` invocation included an unsupported display-only
`--json` option and exited at argument parsing before creating a clone or
artifact. The corrected canonical command then created the single successor;
there was no duplicate resource or second attempt.

Bootstrap was executed before start. Its required `gac` health probe was
degraded because the naked executable resolves to Xcode Python 3.9 and cannot
import `datetime.UTC`; the same validator under the tracked managed-Python
runner returned exit 0. This is the already separated A3 prerequisite and is
not represented as an A1 success or silently ignored.

The executor attests that `AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only
to the process that created the single unbound run above and was not passed to
clone onboarding, claims, tests, or any subsequent command. Current tooling
does not produce an independent environment-bound receipt, so this execution
boundary remains independently `UNPROVABLE`; this document does not claim to
prove whether a parent shell ever exported the variable. It records the exact
authorized invocation boundary and the default-gate observations that follow.

The run claimed exactly:

1. `.omo/_truth/registry/branch-prefix-policy.yaml`
2. `tests/unit/gac/test_clone_branch_policy_contract.py`
3. this waiver evidence file

The workflow-generated affected-graph receipt is restricted to
`.omo/evidence/a1-branch-recovery-20260909-02/affected-graph-receipt.json`.
All other run, event, lock, identity, provenance, manifest, and readiness
records are tool-generated inside the named attempt and were not hand-edited.

## TDD evidence

The test file was added before the policy mutation. Against the original
policy, the focused suite produced the intended RED result:

- `3 failed, 7 passed`;
- a branch emitted by a real `agent-clone.py create` fixture was rejected;
- the legacy `$` anchor accepted a newline-suffixed slash branch;
- a dynamic differential test found a producer-valid `agent/0--0` branch
  rejected by policy.

Only `naming.agent`, `prefixes.agent.pattern`, and the matching agent
description were then changed. The same focused suite produced GREEN:
`10 passed`. Independent review then required fixed identity-edge cases for an
actor ending in `.lock`, internal multiple `--` separators, and the same
branch string's two valid actor/attempt splits. Adding those tests without
changing policy or production code produced the final focused result:
`14 passed`.

The tests consume the real `AGENT_ID_RE`, `validate_clone_identity`, policy
loader/checker, `git check-ref-format`, and an actual local clone creation.
They dynamically derive the producer's singleton characters and maximum
length rather than copying its regex. They preserve the slash worktree
namespace, reject Git-invalid refs and trailing newlines, and prove that
policy admission cannot substitute for v2 clone identity validation. The
fixed edge cases also prove that policy performs existential language
admission rather than splitting a branch back into an inferred identity.

## Exact delivery boundary

Only the three claimed repository paths may be committed. This operation does
not authorize changes to the Ledger, any BET or Spec, completion/value
evidence, another policy entry, production checker, clone/identity/lifecycle
code, hook source, TTL/prune logic, CI, branch protection, gitlinks, services,
databases, timers, or business runtime state.

The blocked `a1-branch-recovery-20260908-01` attempt remains unsubmitted and
untouched. Its generic authorization, unprovable environment boundary, failed
gate, closed run, and released locks remain historical evidence and are not
reused by this successor.

The workflow declares `.omo/**` and `spaces/**` write surfaces but not the
authorized test path, while exact claim coverage accepts all three paths.
This pre-existing workflow-surface gap is recorded but not repaired here.
The shared agent metadata also still reports `requires_worktree: true` for
both admitted agent branch topologies; no current enforcement consumer was
found, so that schema split remains a separate follow-up.

Merge requires focused and lifecycle regression tests, direct branch and
identity canaries, default workflow verification/compliance, full GaC, all
required PR contexts, immutable merge-tree equality, and post-merge replay.
Any failure stops the transaction without widening this waiver.

## Rollback

Before merge, close the unique PR and preserve its branch, tag, and evidence
if a required check fails. After merge, an R0-caused regression requires a
separate exact-scope revert PR. The host classification can be rolled back by
restoring only the Ollama type line and proving the full file returns to
`4bc2d3bbacabf4791f8f73e3228a43cf042ebb3ff9bd15da8f95718169170cd1`.
No rollback may alter another service, the blocked attempt, Ledger/BET truth,
or personal-value evidence.

## Attempt02 failure chain and preserved evidence

Attempt02 remains preserved as failed evidence and is not modified by this
successor.

- Attempt02 path:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a1-branch-recovery-20260909-02/ws`
- Exact commit: `e40dc96d3f7a1c3df69a8228052987a7c143d94b`
- Annotated tag: `a1-branch-recovery-20260909-02`
- Clone-local run:
  `20260909T022611Z-governance-state-mutation-1a5b71e9`, closed
  `blocked` with zero locks.

Attempt02's clone-lifecycle claim verification could not produce
`all_covered=true` because trusted claims authority is fixed to
`/Users/xiamingxing/Workspace` while the authorized run and claims were
clone-local. No claim-verified changeset or integrate receipt is claimed.

Its one authorized non-force push was attempted once and rejected by pre-push
`gitlink-ancestry`: attempt02 inherited Cockpit
`87a9b9cb4cce...`, while current main had advanced to
`31898e343423...`. No remote branch, remote tag, or PR was created, and
there was no retry.

## Attempt03 successor scope

This successor is based exactly on frozen base
`91368ab384957cd35329a200226f9328a59d027b`.

- Branch:
  `agent/codex-agent-os-recovery--a1-branch-recovery-20260909-03`
- Active workflow run:
  `20260909T034755Z-governance-state-mutation-b64ae175`
- Actor: `codex-agent-os-recovery`
- Provenance digest:
  `dfa003dbd9c484a6598c4f610f91a5ca137ffb211c254144edf62d01094d9ada`
- Readiness digest:
  `cbe6848b7e6fa3b172e8e01c1cbde59c241aa8e7b751f6abdbd94f1ef645bef8`

Its direct publish is an explicit one-time, non-precedent path. The gitlink
range semantics and claim-authority bridge remain separate future mechanism
BETs.

## Attempt03 principal authorization, verbatim

> 批准 A1 R0 attempt03 successor recovery：保留并不得修改 attempt02、commit `e40dc96d3f7a1c3df69a8228052987a7c143d94b` 及原 annotated tag。等待当前 `root-gate` 合法释放后，以执行时 `git ls-remote` 返回的最新 main exact SHA 创建唯一 full successor `a1-branch-recovery-20260909-03`；允许 `AGCP_REQUIREMENT_ITERATION_GATE=0` 仅作为一次 unbound workflow start 的进程级前缀，随后 claim、测试、验证、Git、CI、closeout 全部恢复默认门。人工 tracked 写面仍严格限于 `.omo/_truth/registry/branch-prefix-policy.yaml`、`tests/unit/gac/test_clone_branch_policy_contract.py`、`.omo/_truth/governance-evidence/waiver-2026-09-08-clone-branch-admission-recovery.md`；前两路径重放已验证内容，waiver 追加 attempt02 的 claims-authority 缺口、唯一 push 被 stale-base gitlink gate 拒绝的事实及本授权。不得修改任何 gitlink、Ledger/BET、completion/value evidence、生产 checker、clone-lifecycle、hook、CI、branch protection、运行态或其他治理规则。允许为 attempt03 再执行一次明确记录为非先例的 degraded direct publish：生成新 commit 和 annotated tag，经默认本地门通过后一次非 force push并创建唯一 PR；PR diff 必须仅含上述三路径。只有 `phase-gate`、`bet-done-transition`、`gac-gate` 全绿后方可 squash merge；随后执行三路径 exact-object 验证、blocked closeout、锁归零并退役 attempt03。任一实际门禁拒绝即停止，不重试、不扩面。attempt02 暂保留为失败证据。`check-submodule-rewind` 的 merge-base 语义修复与 claim-authority bridge 分别另立机制 BET。

## Attempt03 TDD evidence

The contract test was created before the policy mutation. The first runnable
focused invocation used the managed environment with PyYAML and pytest and,
against the unchanged slash-only policy, produced the intended RED:
`7 failed, 7 passed`. The seven assertions covered the real clone-produced
double-hyphen branch, the newline anchor, three valid identity edge cases, the
ambiguous separator, and the producer/policy boundary differential.

Only `naming.agent`, `prefixes.agent.pattern`, and the corresponding agent
description were changed to the verified attempt02 content. The same focused
command then produced GREEN: `14 passed`.

## Attempt03 review-artifact recovery

The first attempt03 workflow run
`20260909T034755Z-governance-state-mutation-b64ae175` completed its scoped
verification before review with all 57 GaC checks green. Commit
`dfd8186666581cb5e15127a155647e6fbe156932` then received an independent
read-only review with both specification-compliance and code-quality verdicts
approved.

The review-package helper subsequently created the ignored clone-root directory
`.superpowers/sdd` at `2026-09-09T12:00:15+08:00`. A fresh default workflow
verification then failed only at `gac-local-gate`: root-directory governance
reported one unregistered ignored root directory. The scanner contract treats
an ignored, untracked root directory as a violation unless the directory is
policy-allowed. The earlier verification preceded this directory and passed;
the later verification followed it and failed. No tag, push, PR, merge, retry,
tracked remediation, or governance allowlist change occurred. The run was
closed `blocked` at `2026-09-09T04:06:34Z`, releasing all six locks.

Before externalization, the two generated files had these complete SHA-256
digests:

- `.superpowers/sdd/review-91368ab38..dfd818666.diff`:
  `321882154db527386ba72dab312dd9d4e35778e7ee8d62add1aba34b6b8e3f52`
- `.superpowers/sdd/.gitignore`:
  `cdbcae15105d6b781e620813c79c7e868740d4e9cc53ce6f5fcbbc12387adf4b`

Under the authorization below, the complete `.superpowers` directory was moved
without deletion to:

`/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a1-branch-recovery-20260909-03/review-evidence/superpowers`

Both file digests were identical after the move, the clone-root source became
absent, and the tracked worktree remained clean. This recovery does not admit
`.superpowers` into root-directory policy. The fresh recovery workflow run is
`20260909T041102Z-governance-state-mutation-a9ad301f`; it claimed the same three
paths and no others.

## Attempt03 review-artifact recovery authorization, verbatim

> 批准 A1 attempt03 review-artifact recovery：保留 commit `dfd8186666581cb5e15127a155647e6fbe156932`；记录 `.superpowers/sdd` 内文件完整 SHA-256 后，仅将整个 ignored `.superpowers` 目录移动到 attempt03 的 clone 外证据目录，不删除内容。允许在同一 attempt03 创建一次 fresh unbound workflow run，`AGCP_REQUIREMENT_ITERATION_GATE=0` 仍只用于该 start；claim 仍限原三路径。仅允许在既有 waiver 路径追加本次授权、review-package 导致 gate 失败及外移证据，不修改 policy、test 或其他文件；创建一个后续 waiver-only commit。随后使用 clone 外 review artifact 完成独立复核，运行 focused test、默认 workflow verify/compliance 和 GaC；全部通过后创建 annotated tag、执行一次非 force push和唯一 PR。PR diff仍必须只含原三路径；`phase-gate`、`bet-done-transition`、`gac-gate` 全绿后方可 squash merge，再做 exact-object 验证、blocked closeout、锁归零和 clone retirement。任一实际门禁再次拒绝即停止，不重试、不扩面。此恢复不授权 `.superpowers` 加入治理白名单；review-package 输出位置兼容问题另立机制 BET。

## Attempt04 managed successor authorization and bootstrap-cycle evidence

### Human authorization — verbatim

> 批准 A1 R0 attempt04 与 gitlink draft-Spec successor 双事务恢复。第一事务保留 attempt02、attempt03及当前未提交草案，从执行时最新 main 创建唯一 managed full clone `a1-branch-recovery-20260909-04`；允许 `AGCP_REQUIREMENT_ITERATION_GATE=0` 仅用于一次 unbound start，claim 仅限原 A1 policy、contract test、原 waiver 三路径，policy/test 必须分别重放 blob `0ecbb258d7d62551c12b4fb0019f7a3a0f973bd1` 与 `8e77200d397123091816a073539a7768d491c132`，waiver 追加本授权和 clone-identity 自举阻塞。允许提交后一次 guarded latest-main fetch/rebase、recursive checkout 与完整重验，再执行一次正常、非 force、不得 `--no-verify` 的 push和唯一 PR；任何门禁拒绝即停止。required contexts 全绿后 squash merge、exact-object 验证、锁归零并退役 attempt04。不得修改其他路径、Ledger/BET、gitlink、运行态或用户配置。
>
> 仅在第一事务完成后，允许从新 main 创建唯一 managed full draft-Spec successor；第二次 `AGCP_REQUIREMENT_ITERATION_GATE=0` 仍仅用于该 successor 的一次 unbound start，claim 仅限当前两条 draft 路径，重放 Spec SHA-256 `260fc96ce887eb95b9ff3b8cf8dbe6180cf0fe50f6047da6bc180dab99f5be88` 并更新 waiver 的真实 successor 身份；默认门、独立复核、唯一 PR和required checks通过后合并。仍不得转 accepted、建立 BET binding或实施代码。

### First-transaction identity

- Execution-time root main:
  `b7dfeca9f91e072c7f01ae29ec826fa16b1b80d6`.
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a1-branch-recovery-20260909-04/ws`.
- Working branch:
  `agent/codex-agent-os-recovery--a1-branch-recovery-20260909-04`.
- Clone provenance status/digest:
  `ready` /
  `5e668114a541f737f44f47cdcd7a034a67b1c73ce84adc53fb52075b5eab07fb`.
- Clone readiness status/digest:
  `ready` /
  `7b05c3e962e56a2031af0fcf88cfad9ced8d354d20db20a5733a797caea7201b`.
- Workflow run:
  `20260909T053032Z-governance-state-mutation-05b4c1dd`.
- The requirement-gate override was process-local to that single unbound
  `start`; subsequent claims and commands use the default gate.
- Affected-graph receipt hash:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`.
- Claims are exactly the branch policy, the focused contract test, and this
  waiver path.

### Preserved draft-Spec bootstrap blocker

The separately preserved draft clone is:

`/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a1-gitlink-ancestry-spec-20260909-01/ws`.

It contains exactly two untracked reviewed files, including draft Spec
SHA-256 `260fc96ce887eb95b9ff3b8cf8dbe6180cf0fe50f6047da6bc180dab99f5be88`.
Its workflow
`20260909T045656Z-governance-state-mutation-41dc14fc` was closed
`blocked` with five locks released. The default writer-identity preflight
returned `clone_identity_required` when run with
`AGENT_ID=codex-agent-os-recovery`: a raw full clone on the current
policy-compliant slash branch has no managed clone identity. Omitting
`AGENT_ID` classified the agent as `human_operation_allowed`; that route
was rejected as an identity bypass. No stage, commit, tag, push, or PR was
created from that draft clone.

This evidence explains the dependency cycle; it does not widen attempt04.
The first transaction still changes exactly the original three A1 paths and
does not publish or accept the draft Spec. The second transaction remains
strictly contingent on attempt04 merge and post-merge proof.

### First-transaction content invariants

- Policy working-tree blob:
  `0ecbb258d7d62551c12b4fb0019f7a3a0f973bd1`.
- Test working-tree blob:
  `8e77200d397123091816a073539a7768d491c132`.
- The execution-time main had the original policy blob
  `c229bd8c27981aa33edc7d103f67d6b6046fabff`; the focused test and this
  waiver path were absent.
- attempt02, attempt03, and the draft clone remain preserved and unmodified.
- No Ledger/BET, other registry entry, implementation, other test, hook, CI,
  branch-protection, gitlink, service, runtime, or user configuration is
  authorized by this successor.

The one guarded latest-main synchronization is allowed only after the scoped
commit exists. Any target-path drift, content drift, unexpected file, default
gate rejection, non-fast/non-clean rebase, recursive checkout failure, or
required-context failure stops the transaction without retry or expansion.

### Attempt04 pre-commit verification

- Focused contract suite: `14 passed` under the managed Python/PyYAML/pytest
  environment; the independent reviewer repeated it with the same result.
- Workflow verify for
  `20260909T053032Z-governance-state-mutation-05b4c1dd` reported complete
  three-path claim coverage and PASS for doc SSOT lint, SSOT guardian, and the
  default 57-check GaC local gate. The report retained six known-unavailable
  checks as skipped; this successor does not represent them as strict proof.
- Workflow compliance returned `ok=true`, `decision=continue`, zero stale
  locks, zero P74 silent-workflow warnings, and confirmed the requirement
  iteration override was no longer active.
- Independent read-only review returned `codeQualityStatus=CLEAR`,
  `recommendation=APPROVE`, and no critical/high/medium/low findings. Its
  ignored review artifact is
  `.omo/evidence/a1-branch-recovery-attempt04-code-review.md`, SHA-256
  `786ade95e05387c6247cfc08cdbb65878d2b6529bce6c474ac66b560d57e5a84`.
- `git diff --check` passed, the delivery tree contained exactly the three
  authorized paths, and no root gitlink changed.

These are working-tree observations until the scoped commit, guarded
latest-main synchronization, final re-verification, normal push, required PR
checks, merge, and post-merge exact-object proof complete.
## Attempt05 immutable successor authorization and bootstrap

### Human authorization — verbatim

> 批准 A1 R0 attempt05 immutable-successor：保留 attempt02–04及 draft clone，不修改或重绑其 identity/provenance/readiness；从执行时最新 main 创建唯一 managed full clone `a1-branch-recovery-20260909-05`，允许只读使用 attempt04 作为无 persistent alternates 的 transport acceleration。`AGCP_REQUIREMENT_ITERATION_GATE=0` 仅用于一次 fresh unbound start，claim 仍限原 policy、contract test、waiver 三路径；policy/test 精确重放 blobs `0ecbb258d7d62551c12b4fb0019f7a3a0f973bd1`、`8e77200d397123091816a073539a7768d491c132`，waiver 追加本授权、attempt04 provenance rejection和 pre-rebase mode 事实。attempt05 禁止 rebase、merge、pull或吸收上游历史；完成测试、默认 verify/compliance、GaC、独立复核及提交后，双读远端 main，只有远端 main 仍等于 frozen base且三路径无并发漂移时才创建 annotated tag并执行一次正常非 force、不得 `--no-verify` 的 push和唯一 PR。任一条件或门禁失败即停止，不创建 attempt06。required contexts 全绿后 squash merge、exact-object/post-merge 验证、锁归零并退役 attempt05；不得修改其他路径、Ledger/BET、gitlink、hook、CI、运行态或用户配置。

### Attempt05 identity and exact scope

- Execution-time remote `main`:
  `2e7c16e60cc82cdf05ba306d570f9c47c3ac8b74`.
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/a1-branch-recovery-20260909-05/ws`.
- Working branch:
  `agent/codex-agent-os-recovery--a1-branch-recovery-20260909-05`.
- Clone provenance status/digest:
  `ready` /
  `2c87377635bda7f4b98666cfaebffce598b009e17e0bc5330b0d412d220f11b0`.
- Clone readiness status/digest:
  `ready` /
  `f24142b0c428dccea2e336c2157dc186d0c1faab1c12cbde2430ca14afcf6982`.
- Workflow run:
  `20260909T060102Z-governance-state-mutation-501cb3fd`.
- Affected-graph receipt hash:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`.
- The requirement-iteration override was process-local to the single
  unbound `start`; all claims and later commands use the default gate.
- Claims are exactly the branch policy, the focused contract test, and
  this waiver path.

The optional attempt04 transport acceleration was not used. The clone creator
requires local acceleration mappings for every selected full-profile gitlink;
rather than widen the declared local transport set, attempt05 was cloned
directly from the authoritative GitHub repository at the exact frozen SHA.

The policy and contract test must retain these exact Git object identities:

- policy blob: `0ecbb258d7d62551c12b4fb0019f7a3a0f973bd1`;
- contract-test blob: `8e77200d397123091816a073539a7768d491c132`.

### Attempt04 provenance rejection

Attempt04 is preserved unchanged at commit
`8255e9aab1c6f2b983f152bc86e88334caa2a057`. Its one authorized guarded
latest-main rebase completed, after which the default writer guard returned
`clone_provenance_mismatch`. Repository identity, clone author identity, and
the frozen-root ancestry check all matched. The only failing predicate was
`commit_identities_match(frozen_root..HEAD)`: rebase imported platform main
commit `2e7c16e60cc82cdf05ba306d570f9c47c3ac8b74`, whose GitHub platform
author/committer identity cannot equal the clone-bound agent identity required
by the ordinary writer guard.

No receipt was edited or rebound, and no identity bypass was attempted.
Attempt04 created no tag, remote branch, PR, or merge after this rejection.
Its workflow was closed `blocked` and all six locks were released. This is a
mechanism-level incompatibility between rebase-imported platform commits and
the ordinary frozen-root-to-HEAD provenance predicate; it is not represented
as delivery or product failure.

### Canonical pre-rebase executable-mode fact

The tracked `.githooks/pre-rebase` object is blob
`4172b06d84138c0f8c4fffc7997140f89c55ad56` with Git mode `100644` on
canonical main and attempt04. Git therefore skipped the hook that would have
rejected rebasing an immutable `agent/*` writer branch. Matching object modes
across main and the clone prove this is a canonical repository baseline defect,
not a clone transport permission loss. This waiver records but does not repair
the hook, its mode, or any related CI/governance surface.

### Immutable successor and publish boundary

Attempt05 must not rebase, merge, pull, or absorb any upstream history. After
the exact three-path commit is independently reviewed and passes the focused
tests plus default workflow verify/compliance and GaC, publication is allowed
only if two independent remote-main reads still equal the frozen SHA and the
three target paths have not concurrently drifted. Any mismatch or gate failure
halts this attempt without retry or attempt06. Required PR contexts, squash
merge, exact-object/post-merge proof, blocked closeout, zero locks, and managed
clone retirement remain mandatory before A1 R0 can be reported complete.
