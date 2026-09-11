---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.2.0 Wave B1 binding
type: doc
---

# Claims Authority Bridge WP1 1.2.0 Wave B1 Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.2.0` (Wave B1 six root paths only), then continue Claims Bridge landing
under subsequent non-union accepted bindings. Constitutional boundaries remain:
OMO sole control plane; no Orca/Multica/Ruflo writers; no shared Workspace
writes; `value_indicator_policy=false`; operational/value stay `NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T064726Z-governance-state-mutation-407c49b5`. Claims, edits,
verification, Git, CI and closeout use default policy. An earlier mistaken
bet-bound start `20260911T064635Z-governance-state-mutation-ac8ea610` was closed
`blocked` with `WORK_PACKET_SCOPE_MISMATCH` before any binding-path claim
succeeded under the stale 1.1.2 Wave A WorkPacket; it is not delivery authority.

The process-local gate declaration for this three-path binding is exactly
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

The only tracked paths in this binding transaction are:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

No implementation, test, plan body, child repository, gitlink, runtime, store,
service, database, timer, CI workflow, branch protection, completion/value
evidence or user configuration is modified by this binding PR.

## Predecessor and Wave A proof

- Root frozen main for this clone: `b9966e79640ef52340bd35ae3ef78233e1f1aec4`
- Wave A child main: `15ee4ab1d26199e361d471963be07f193b6704f9`
- Exact Wave A blobs:
  - `claims_authority.py` `3f011c43db1f32c8fbb1662cca6f85490f1d86ce`
  - `lifecycle.py` `80e5a2791eed2f1f769c24cbd6f52c4ac6e7d14a`
  - `test_workflow_claims_authority_bridge.py` `4e508bc95453deaad332c29193f486d272911592`
- Wave A run `20260911T055655Z-bet-execution-664be1ac` status `ok`, locks zero
- Root `projects/omo` gitlink remains `edf2301e9344cbfbeb90599f405acb8cc29d9301`
  (pre-Wave A), as required for Wave B1 lazy adapter semantics

## 1.2.0 successor authority

- Spec version: `1.2.0`
- Spec SHA-256: `29bc960280008eee64285302f06e5c89b4b5f25167633a3de53d370d4ffa2996`
- WorkPacket SHA-256: `97dacefc51984fb00da82fd8cb9f209ae0675e3ab74dc4f9353ba74700f0d43a`
- WorkPacket full: `sha256:97dacefc51984fb00da82fd8cb9f209ae0675e3ab74dc4f9353ba74700f0d43a`
- Current write surfaces (sorted / WorkPacket order):

```text
.omo/_truth/registry/swarm-coordination.yaml
bin/agent-workflow.py
bin/gac/agent-clone.py
bin/gac/clone-lifecycle.py
tests/test_agent_workflow.py
tests/test_clone_lifecycle.py
```

- BET state: `candidate`
- completion: engineering `NOT_STARTED`, operational/value `NOT_PROVEN`, overall `evaluating`
- value policy: `value_indicator_policy=false`
- Prior Wave A WorkPacket `sha256:73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613` is rejected

This binding authorizes only Wave B1. It does not authorize Wave B2–D, root
gitlink bump, production shadow activation, WP2, or value completion.

## Clone and verification boundary

- Managed governance clone:
  `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v120-binding-20260911-01/ws`
- Frozen root: `b9966e79640ef52340bd35ae3ef78233e1f1aec4`
- Affected graph receipt hash:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`
- After first GaC reported missing `projects/cockpit-ui` static assets, that exact
  gitlink was initialized at root HEAD `4ea84178198855c69e17d8a36d9b1ecc491fc305`.
  This changed no tracked root object and does not enter the delivery diff.
- With the exact three-lane declaration, standard GaC passed 58/58.

## Stop conditions

Any scope union with Wave A child paths, implementation edit in this PR, root
gitlink mutation, second dispatcher registration, completion/value expansion,
reuse of the 1.1.2 WorkPacket hash, failed Binding QA, unknown remote result or
stale base stops this transaction. Rollback must be a new successor binding with
`implementation_authorized=false`, never restoring 1.1.2 as current authority
while erasing Wave A evidence.
