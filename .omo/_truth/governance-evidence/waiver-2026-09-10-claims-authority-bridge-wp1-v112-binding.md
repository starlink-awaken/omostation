---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-10
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.1.2 contract and binding recovery
type: doc
---

# Claims Authority Bridge WP1 1.1.2 Contract And Binding Recovery

## Human authority and exact scope

Current delegated authority, verbatim:

> 授权窗口，继续延长吧，延到9月15日24点之前。

The delegation is interpreted in Asia/Shanghai and expires at
`2026-09-16T00:00:00+08:00`. It authorizes this reversible repository-only
contract recovery because fixed-digest review of the 1.1.1 implementation
found authority, closure, source-truth and settlement ambiguities that could
otherwise create a false-green publication.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260910T150555Z-governance-state-mutation-3354a087`. Claims, edits,
verification, Git, CI and closeout use default policy. An earlier run,
`20260910T150531Z-governance-state-mutation-a1e8e390`, defaulted its actor to
the OS username and was closed `blocked` before any claim or edit; it is not
delivery authority.

The binding is an intentional, non-union three-lane transaction. The
process-local gate declaration is exactly
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`; it matches the
three claimed paths and adds no path, mutation authority or skipped check. The
managed `governance` clone profile omitted `projects/cockpit-ui`; after the
first local GaC reported only its missing static asset dependency, that exact
gitlink was initialized at root HEAD
`4ea84178198855c69e17d8a36d9b1ecc491fc305`. This changed no tracked root
object and does not enter the delivery diff.

The only tracked paths in this binding transaction are:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

No implementation, test, plan, child repository, gitlink, runtime, store,
service, database, timer, CI workflow, branch protection, completion/value
evidence or user configuration is modified.

## Predecessor and stop evidence

The 1.1.1 binding merged at root main
`37afc2ae2d64ea3b99f107c76fec131dca23a05e`, with Spec SHA-256
`7a4cdbae6fb4ce5af09b77438cf56c0b57bddc50e94d3db824ad5d79f1104bae`
and WorkPacket SHA-256
`d844394dcbfb67dcea9e5a770696e12a69b75b36dc88c4fdde2a17140863b4d2`.

Its implementation run
`20260910T110304Z-bet-execution-74895d83` was closed `blocked` after two
fixed-digest reviews rejected publication. All five locks were released. The
preserved child checkout contains staged work but has no implementation
commit, tag, push or PR. Test and review evidence does not change BET,
completion, operational or value state.

The contract review identified four exact gaps:

1. two persistent operator evidence schemas existed in code but not in the
   accepted object contract;
2. the activation descriptor did not carry the complete root, policy,
   gitlink, dependency and managed-Python closure;
3. a clone-local, internally consistent WorkPacket could pass without an
   integration-root Ledger/Spec/Instruction rebuild; and
4. a lost settlement response could leave a durable reservation without a
   replayable settlement identity.

## 1.1.2 successor authority

Version 1.1.2 keeps exactly the same non-union Wave A implementation paths:

- `projects/omo/src/omo/workflow/claims_authority.py`
- `projects/omo/src/omo/workflow/lifecycle.py`
- `projects/omo/tests/test_workflow_claims_authority_bridge.py`

The final binding is:

- Spec version: `1.1.2`
- Spec SHA-256:
  `bc1de057c28ce91aec5120396bcdedebb3b93b1289fcdc8c81387554efd47192`
- WorkPacket SHA-256:
  `73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613`
- BET state: `candidate`
- completion state: engineering `NOT_STARTED`, operational/value
  `NOT_PROVEN`, overall `evaluating`
- value policy: `value_indicator_policy=false`

The two auxiliary recovery objects
`claims-operator-authorization/v1` and
`claims-stopped-process-proof/v1` are now explicit R0 cooperative contracts.
They cannot grant a claim, issue a fence, perform Git, change v1 state or
resolve another target. Their canonical paths are account-derived,
content-addressed and non-redirectable. Same-UID adversarial writes remain
outside R0, but file presence and self-digest alone are not sufficient: every
principal/decision/observer, unknown receipt, target, process, time and
outcome binding must match. This Wave A binding creates no production evidence
writer; missing provenance remains fail-closed.
Structurally valid files cannot produce a positive production resolution under this
binding. Production activation and positive recovery remain prohibited until a later
accepted binding names and closure-binds the exact principal-decision and independent
process-observer verifier interfaces. Wave A positive recovery tests are restricted to
`test:<uuid>` stores.

Activation must bind and independently double-read the exact root commit,
policy blob, child gitlink, dependency entries/closure and managed-Python
receipt/executable identity. Production claim observation must rebuild the
current WorkPacket from the passwd-derived integration-root Ledger, accepted
Spec and Instruction Pack. Settlement response loss may only confirm the same
request ID and canonical body; it never repeats a v1 mutation or Git effect.

Because no production store exists, 1.1.2 may add the frozen
`settlement_request_id` columns while retaining `PRAGMA user_version=1`. This
does not authorize a live migration, store initialization or shadow
activation.

## Clone and verification boundary

- Frozen root main:
  `37afc2ae2d64ea3b99f107c76fec131dca23a05e`
- Managed governance clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/claims-wp1-v112-binding-20260910-01/ws`
- Provenance:
  `ready / 841e1de21b48f071bd7ca58a7ff2b14808af626c84b4f6afaf88f96c96e02583`
- Readiness:
  `ready / 40dc81a4d604b9307e2aeddbf79c402cc6fb943ae1d7103a9bb16c79b7615349`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`

For verification only, the clone was completed to a recursive checkout at the
exact root gitlinks after the governance profile omitted dependencies required
by strict doctor checks. No gitlink changed. With the exact three-lane
declaration, standard GaC passed 58/58 and strict GaC passed 75/75.

Before publication, Ledger lint, portfolio lint, exact Spec/WorkPacket
recomputation, workflow verify/compliance, local GaC and two digest-bound
read-only reviews must pass. Publication permits one normal non-force attempt
and one unique PR. Required contexts must be green before squash merge.
Post-merge exact objects, Spec/WorkPacket digests and zero locks must be proven.

The implementation plan is deliberately excluded from this transaction. It
must converge in a separate two-path governance transaction after this binding
merges. Only after both runs close and all locks are zero may a fresh Wave A
implementation successor replay the reviewed three-path patch onto current
child main.

Any scope union, implementation/plan/runtime edit, completion/value expansion,
old WorkPacket reuse, missing operator binding, incomplete closure, local-only
WorkPacket authority, non-idempotent settlement confirmation, failed gate,
unknown remote result or stale base stops this transaction. Rollback must be an
ordinary reviewed PR creating a new successor binding with
`implementation_authorized=false` and a newly computed safe WorkPacket. It must never
restore 1.1.1 as the current accepted binding, erase the review findings or authorize
implementation under 1.1.1.
