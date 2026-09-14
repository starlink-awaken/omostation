---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.3.0 Wave B2 binding
type: doc
---

# Claims Authority Bridge WP1 1.3.0 Wave B2 Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.3.0` (Wave B2 nine effect-convergence paths only), then continue Claims
Bridge landing under subsequent non-union accepted bindings. Constitutional
boundaries remain: OMO sole control plane; no Orca/Multica/Ruflo writers; no
shared Workspace writes; `value_indicator_policy=false`; operational/value stay
`NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T100737Z-governance-state-mutation-1b2bfc94`. Claims, edits,
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

## Predecessor and Wave B1 proof

- Root frozen main for this clone: `8858d1bb0e47b51bbd0bf2483c8504dea9ad31d7`
- Wave B1 root merge: `a02dbc6a4` feat(gac): Claims WP1 Wave B1 root shadow adapter and fence owner (#3535)
  (source `62938ca13`)
- Exact Wave B1 blobs on `origin/main` (MATCH):
  - `.omo/_truth/registry/swarm-coordination.yaml` `76475f855845a102bfcccfdcb2fb86da75572639`
  - `bin/agent-workflow.py` `11448d7adbefb3cc219dfd61360fbaf26db9edc9`
  - `bin/gac/agent-clone.py` `192873267769f45706866d6b5b812156970daefa`
  - `bin/gac/clone-lifecycle.py` `bb9c5b47df171ec83b5e4630d6a4d4511e9e0eb5`
  - `tests/test_agent_workflow.py` `662fed485ca106161884758a25f0f777fc3e67b8`
  - `tests/test_clone_lifecycle.py` `c36a1ecc68c8c0fbeaaff0055d93fb909dbbbc15`
- Wave B1 run `20260911T072032Z-bet-execution-dbac7234` status `ok`
- This binding clone holds zero live B1 path locks and zero `BET-Y1Q4-T10-145` bet lock
- Root `projects/omo` gitlink was not bumped by Wave B1

## 1.3.0 successor authority

- Spec version: `1.3.0`
- Spec SHA-256: `aa4cb61e10c38ed94e4b6b52a9e0160422ad1079c5bae6ab6d90b2ecd01340ab`
- WorkPacket SHA-256: `8ff37c0a02ad75b725df9d8f3de0b3343395fb332b60c34f751faec4eba58045`
- WorkPacket full: `sha256:8ff37c0a02ad75b725df9d8f3de0b3343395fb332b60c34f751faec4eba58045`
- Current write surfaces (sorted / WorkPacket order):

```text
bin/gac/gac-worktree.sh
bin/gac/git-retry.sh
bin/gac/gitlink-drift-protect.py
bin/ssot/sync-submodules-push.sh
bin/sync-submodules.sh
scripts/wait-and-bump-cockpit.sh
tests/test_gac_worktree_claim_pasw.py
tests/test_git_publication_effect_owner.py
tests/unit/gac/test_submodule_pointer_transaction.py
```

- BET state: `candidate`
- completion: engineering `NOT_STARTED`, operational/value `NOT_PROVEN`, overall `evaluating`
- value policy: `value_indicator_policy=false`
- Prior Wave B1 WorkPacket
  `sha256:97dacefc51984fb00da82fd8cb9f209ae0675e3ab74dc4f9353ba74700f0d43a` is rejected

This binding authorizes only Wave B2. Under 1.3.0, `gac-worktree submit` is
proposal-only (`MANAGED_SUCCESSOR_REQUIRED`) and must not cast a worktree as a
managed integrate clone. It does not authorize Wave B3–D, root gitlink bump,
production shadow activation, WP2, or value completion.

## Clone and verification boundary

- Managed governance clone:
  `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v130-binding-20260911-01/ws`
- Frozen root: `8858d1bb0e47b51bbd0bf2483c8504dea9ad31d7`
- Delivery attempt: `a20260911T100527Z-v130bind`
- After first GaC reported missing `projects/cockpit-ui` static assets, that exact
  gitlink was initialized at root HEAD `73af4bec6fb1cdb32ac0b18910f451ab3f3711d2`.
  This changed no tracked root object and does not enter the delivery diff.
- With the exact three-lane declaration, standard GaC passed 58/58.
- Binding run: `20260911T100737Z-governance-state-mutation-1b2bfc94`

## Stop conditions

Any scope union with Wave B1 paths, implementation edit in this PR, root
gitlink mutation, second dispatcher registration, completion/value expansion,
reuse of the 1.2.0 WorkPacket hash, failed Binding QA on T10-145 surfaces,
unknown remote result or stale base stops this transaction. Rollback must be a
new successor binding with `implementation_authorized=false`, never restoring
1.2.0 as current authority while erasing Wave B1 evidence.
