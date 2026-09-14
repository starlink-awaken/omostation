---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.4.0 Wave B3 binding
type: doc
---

# Claims Authority Bridge WP1 1.4.0 Wave B3 Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.4.0` (Wave B3 nine API/shim bypass-closure paths only), then continue Claims
Bridge landing under subsequent non-union accepted bindings. Constitutional
boundaries remain: OMO sole control plane; no Orca/Multica/Ruflo writers; no
shared Workspace writes; `value_indicator_policy=false`; operational/value stay
`NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T112607Z-governance-state-mutation-acbf40b5`. Claims, edits,
verification, Git, CI and closeout use default policy.

The process-local gate declaration for this three-path binding is exactly
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

The only tracked paths in this binding transaction are:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

No implementation, test, plan body, child repository, gitlink, runtime, store,
service, database, timer, CI workflow, branch protection, completion/value
evidence or user configuration is modified by this binding PR. Unrelated
`BET-Y1Q4-T16` ledger lint debt present on `origin/main` before this clone is
not repaired here.

## Predecessor and Wave B2 proof

- Root frozen main for this clone: `82d22f97eaff38b5af8e1e497d35399ab10fc7bc`
- Wave B2 root merge: `654b13439` feat(gac): Claims WP1 Wave B2 publication effect-owner convergence (#3554)
  (source `df114e6d7`)
- Exact Wave B2 blobs on frozen HEAD (MATCH vs merge `654b13439`):
  - `bin/gac/gac-worktree.sh` `b2634981a0cf63d6a76e036eac37c023cd031986`
  - `bin/gac/git-retry.sh` `dc02002a244eb77f729fb8165e25db77f10077b8`
  - `bin/gac/gitlink-drift-protect.py` `7ce0e8ef16619e0129dd4f903965cf8f17fe0ca0`
  - `bin/ssot/sync-submodules-push.sh` `5202b83d7b6d36e531e86a532243222506d98433`
  - `bin/sync-submodules.sh` `6c244c94f71201ff5f51bae75789694eb9fde70b`
  - `scripts/wait-and-bump-cockpit.sh` `461215e46de233e53ee2ce1959fcc54d406dd60d`
  - `tests/test_gac_worktree_claim_pasw.py` `6cde1e2f40783ce51ef0048f0c7c5de7b5ac013a`
  - `tests/test_git_publication_effect_owner.py` `2eed80491a4f5ce530ad2e11f7383fff4d50c4e1`
  - `tests/unit/gac/test_submodule_pointer_transaction.py` `20de05ba369c381b3eaddff9d668a5884cb5c2d0`
- Wave B2 run `20260911T103242Z-bet-execution-37d616a4` status `ok`
- This binding clone holds zero live B2 path locks and zero `BET-Y1Q4-T10-145` bet lock
- Root `projects/omo` gitlink was not bumped by Wave B2

## 1.4.0 successor authority

- Spec version: `1.4.0`
- Spec SHA-256: `2733d7b47ebb4cf5e8f221b5964f681b03e2953d90fa348e166e0c8557862851`
- WorkPacket SHA-256: `1cbe5402fcc4c3d08e1f967c19dd52dee88bb02e29c1e65c750c28bc9fbe441c`
- WorkPacket full: `sha256:1cbe5402fcc4c3d08e1f967c19dd52dee88bb02e29c1e65c750c28bc9fbe441c`
- Current write surfaces (sorted / WorkPacket order):

```text
bin/_registry/scripts/governance/gh-api-push.yaml
bin/gac/gh-api-push.sh
bin/gac/git-shim
bin/gac/swarm-git
docs/plans/AGENT-BRIEF.md
tests/integration/test-git-shim.sh
tests/test_git_publication_effect_owner.py
tests/test_swarm_discipline.py
tests/unit/gac/test_immutable_writer_git_policy.py
```

- BET state: `candidate`
- completion: engineering `NOT_STARTED`, operational/value `NOT_PROVEN`, overall `evaluating`
- value policy: `value_indicator_policy=false`
- Prior Wave B2 WorkPacket
  `sha256:8ff37c0a02ad75b725df9d8f3de0b3343395fb332b60c34f751faec4eba58045` is rejected

This binding authorizes only Wave B3. It does not authorize Wave B4–D, root
gitlink bump, production shadow activation, WP2, or value completion.

## Clone and verification boundary

- Managed governance clone:
  `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v140-binding-20260911-01/ws`
- Frozen root: `82d22f97eaff38b5af8e1e497d35399ab10fc7bc`
- Delivery attempt: `a20260911T112518Z-v140bind`
- Binding run: `20260911T112607Z-governance-state-mutation-acbf40b5`
- After first GaC reported missing `projects/cockpit-ui` static assets, that exact
  gitlink may be initialized at root HEAD without changing tracked root objects.

## Stop conditions

Any scope union with Wave B2 paths, implementation edit in this PR, root
gitlink mutation, second dispatcher registration, completion/value expansion,
reuse of the 1.3.0 WorkPacket hash, failed Binding QA on T10-145 surfaces,
unknown remote result or stale base stops this transaction. Rollback must be a
new successor binding with `implementation_authorized=false`, never restoring
1.3.0 as current authority while erasing Wave B2 evidence.
