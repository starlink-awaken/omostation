---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-10
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.1.0 Wave A binding waiver
type: doc
---

# Claims Authority Bridge WP1 1.1.0 Wave A Binding Waiver

## Human authority and delegated decision

Acceleration approval, verbatim:

> 批准当前 Claims Authority Bridge WP1 启用 Accelerated Iteration v1。

Current authority extension, verbatim:

> 授权给你延迟到24点，继续

The current delegation is interpreted in Asia/Shanghai and expires at
`2026-09-11T00:00:00+08:00`. Under it, the Agent selects the reviewed plan's
12-day elapsed-delivery re-baseline and authorizes this exact repository-only
accepted-binding successor. It does not authorize false evidence,
force/history rewrite, `--no-verify`, secrets, destructive host action,
production activation, completion/value transition, WP2 or a path outside
this transaction.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
workflow start `20260910T055251Z-governance-state-mutation-ed91d6ba`.
Bootstrap, claims, edits, digest computation, validation, Git, CI and closeout
use default policy. The process-local interface
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state` is authorized
only for this atomic Spec/Ledger/waiver transaction's validation and hooks; it
does not expand the three claimed paths or skip a gate.

## Preconditions and predecessor evidence

Plan PR #3503 merged as
`a5840d0588ed6898c3d07e24927a5b9037e75106`; its plan SHA-256 is
`187cde6152f85f197ce68fbd173783bb48736adebc25bef042a2fc820ece76ba`.
The plan run is closed and all three plan locks are zero. PR #3507 restored a
schema-complete T15 task baseline on main
`80fce66d978098684fd0c935b25a975221fb3c99`; its required and complete
post-merge checks succeeded. No open PR collides with this Spec, Ledger or
waiver.

The first 1.1.0 binding attempt created reviewed commit
`35a8dbf515a037842bd18bfe67399aec76eb2f0b` and local annotated tag
`claims-authority-bridge-wp1-v110-binding-20260910-01`. Standard changeset
verification truthfully returned fixed-root `claim_scope_violation`. Its first
push command was rejected locally by malformed zsh refspec construction before
hooks or transport. A separately recorded corrected invocation then reached
the default pre-push hook, where `submodule-reachability` failed because the
MetaOS GitHub HTTPS fetch hit `LibreSSL SSL_ERROR_SYSCALL`. The remote branch,
tag and PR remained absent. The run closed blocked, all six locks reached zero
and the commit/tag/clone remain immutable evidence. They are not reused or
represented as delivered.

Read-only MetaOS probes after the failure passed 3/3 with default transport and
3/3 with HTTP/1.1, supporting an intermittent HTTPS transport diagnosis. They
do not independently prove the exact gitlink OID, which remains subject to the
default reachability hook. The previously merged 1.0.0 binding waiver records a
broader two-sweep result: default HTTP/2 passed 30/32 while HTTP/1.1 passed
32/32. Under the still-live Human delegation, the Agent selects this
evidence-backed mitigation and authorizes only the successor's one push process
to set `http.version=HTTP/1.1`, inherited by its default hook children. It changes no
Git config file, proxy, remote, push argv or governance rule and permits no
retry after another failure.

Attempt02's first full bootstrap timed out on the required Cockpit
`agent-workflow list` probe before any run or edit. The exact command then
passed in 3.48 seconds, its orphan was absent, and one evidence-driven full
bootstrap retry passed every required health check without `--skip-health`.

## Successor identity and exact scope

- Frozen root main: `80fce66d978098684fd0c935b25a975221fb3c99`.
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-authority-bridge-wp1-v110-binding-20260910-02/ws`.
- Provenance: `ready /
  53cd74125f80e1cb42eb108cd2bead7d5aba6931cf3326238f4ee4a7eb0f0768`.
- Readiness: `ready /
  af42885d3d5b158b479cc5045e6c933dc98b063d0f5fe3cb20f7f22adbb04c83`.
- Workflow: `20260910T055251Z-governance-state-mutation-ed91d6ba`.
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`.

As in the predecessor, onboard pinned `HEAD` and verified remote main at
`80fce66d` while leaving the clone-local `origin/main` at `7d47780a`. Before
diff-based gates, a guarded double-read proved the remote still equalled the
frozen base, and one ordinary fetch advanced only the tracking ref to
`80fce66d`. No source, index, commit or identity changed.

The run claimed exactly the Spec, `docs/plans/3y-bet-ledger.yaml` and this
waiver before editing. This transaction changes no implementation, test,
child repository, gitlink, runtime, host configuration, CI or branch
protection.

## Immutable 1.1.0 replacement

- Spec SHA-256:
  `032957ededf4b7ade8e9543ae38f322083908a99c840d7e8a52f7300dc2e16cf`.
- WorkPacket: `WP-BET-Y1Q4-T10-145`.
- WorkPacket SHA-256:
  `09395b02d0c917e3aa1bf25809de27b52c0d82e6395552547d613a45fe53f1ab`.
- Parent: `BET-Y1Q4-T10-143`.

The one current accepted binding replaces the plan path with exactly:

1. `projects/omo/src/omo/workflow/claims_authority.py`
2. `projects/omo/src/omo/workflow/lifecycle.py`
3. `projects/omo/tests/test_workflow_claims_authority_bridge.py`

The Ledger changes only T10-145 fields required for 1.1.0. Status remains
`candidate`; engineering is `NOT_STARTED`, operational/value are
`NOT_PROVEN`, overall is `evaluating`, and `value_indicator_policy=false`.
`appetite: 12 days` is elapsed D1–D15 time including the mandatory 24-hour
window, not a completion, operational or personal-value claim.

The Spec freezes the reviewed production boundary: integration-root stdio
only; durable run-scoped full-member claim batches; broker-only versions and
epochs; immutable v1 bytes; frozen/revalidated selected-candidate pruning with
no discovery rescan; separate authorization-bound unknown markers; remote
double-read only in descriptor-bound clone-lifecycle while the broker performs
no Git/`gh`; distinct requested shadow mode and active state; no degraded
bootstrap sample; and three distinct real workflow run IDs for graduation.

## Validation, publication and rollback

The exact successor bytes must reproduce the accepted Spec digest and fresh
WorkPacket hash, pass Ledger/strict Portfolio lint, default workflow
verify/compliance, local GaC and two digest-bound read-only reviews. Before
commit and push, remote main and the three base paths are double-read. Standard
v1 changeset verification must run and any fixed-root rejection is disclosed
as `changeset_claims_unverified` in an exact-commit external decision and PR.

Only one correctly delimited ordinary non-force branch/tag push is allowed,
with process-local HTTP/1.1 transport and all hooks enabled. Any hook/gate
failure, transport ambiguity, main/path drift or scope change stops without a
retry. Required contexts must be green before squash merge, followed by
exact-object, Spec-digest, WorkPacket and post-merge checks. The binding run
closes and every lock reaches zero before Wave A starts.

Rollback is an ordinary reviewed binding PR restoring version 1.0.0 and its
plan-only packet. It never rewrites history, fabricates evidence, mutates host
runtime or activates WP1.
