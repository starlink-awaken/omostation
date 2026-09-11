---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-11
last-reviewed: 2026-09-11
value_indicator_policy: false
title: Claims Authority Bridge WP1 1.5.0 Wave B4 binding
type: doc
---

# Claims Authority Bridge WP1 1.5.0 Wave B4 Binding

## Human authority and exact scope

Current Principal authorization, verbatim:

> 给你全权授权，推进目标规划落地吧

Interpreted for this transaction as reversible repository-only authorization to
replace the accepted Spec/Ledger binding of `BET-Y1Q4-T10-145` with version
`1.5.0` (Wave B4 five cloud-automation paths only), then continue Claims Bridge
landing under subsequent non-union accepted bindings. Constitutional boundaries
remain: OMO sole control plane; no Orca/Multica/Ruflo writers; no shared
Workspace writes; `value_indicator_policy=false`; operational/value stay
`NOT_PROVEN`.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to the fresh unbound
`governance-state-mutation` start
`20260911T121510Z-governance-state-mutation-72463c14`. Claims, edits,
verification, Git, CI and closeout use default policy.

The process-local gate declaration for this three-path binding is exactly
`AGENT_WORKFLOW_ALLOWED_LANES=docs,docs_data,governance_state`.

The only tracked paths in this binding transaction are:

1. `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
2. `docs/plans/3y-bet-ledger.yaml`
3. this waiver

No implementation, test, plan body, child repository, gitlink, runtime, store,
service, database, timer, CI workflow body (beyond the Spec/Ledger declaration),
branch protection, completion/value evidence or user configuration is modified
by this binding PR.

## Predecessor and Wave B3 proof

- Root frozen main for this clone: `ff63d9171b2d0bb2f21cb91019f8a5fc6df36e2a`
- Wave B3 root merge: `ff63d9171` feat(gac): Claims WP1 Wave B3 close API/shim publication bypasses (#3564)
  (source `941ac9c5c`)
- Exact Wave B3 blobs on frozen HEAD (MATCH):
  - `bin/_registry/scripts/governance/gh-api-push.yaml` `5ada5b059fcd9b3c7c919df2b7633a047db613f5`
  - `bin/gac/gh-api-push.sh` `fbc57e84609d8f3eb02543a821e599688698e8a6`
  - `bin/gac/git-shim` `6242992f4e435ab267d3a030a1d00ab1533a3b2e`
  - `bin/gac/swarm-git` `1944c8e3f24eeac00d779cabb2793edae4b6db85`
  - `docs/plans/AGENT-BRIEF.md` `9ebb5a71537206625254fcb6d2a74cc48f386275`
  - `tests/integration/test-git-shim.sh` `25c82456eccdd309539261123f25beb53b75c70e`
  - `tests/test_git_publication_effect_owner.py` `a82ea05705755f2722ba2949d96fa64e74e1edfd`
  - `tests/test_swarm_discipline.py` `3470f7f83f6073f610ff73509e62d8bffe92a754`
  - `tests/unit/gac/test_immutable_writer_git_policy.py` `0150f65c307780e5f1dff11248e0ca65a89ab98c`
- Wave B3 run `20260911T114307Z-bet-execution-547b208b` status `ok`
- This binding clone holds zero live B3 path locks
- Root `projects/omo` gitlink was not bumped by Wave B3

## 1.5.0 successor authority

- Spec version: `1.5.0`
- Spec SHA-256: `e0e0301c934c112cb595b4ed1f02fd28201a1024db9dfaa0fb8e1babc4405e09`
- WorkPacket SHA-256: `4e7b88d23c8a110181b38b15a183c93f01543243b60276b69daaaa89fce0a2d8`
- WorkPacket full: `sha256:4e7b88d23c8a110181b38b15a183c93f01543243b60276b69daaaa89fce0a2d8`
- Current write surfaces (sorted / WorkPacket order):

```text
.github/workflows/omo-autopilot.yml
.github/workflows/reusable-submodule-bump-pr.yml
.github/workflows/submodule-autobump.yml
.github/workflows/submodule-freshness-gatekeeper.yml
tests/test_github_publication_effect_owner.py
```

- BET state: `candidate`
- completion: engineering `NOT_STARTED`, operational/value `NOT_PROVEN`, overall `evaluating`
- value policy: `value_indicator_policy=false`
- Prior Wave B3 WorkPacket
  `sha256:1cbe5402fcc4c3d08e1f967c19dd52dee88bb02e29c1e65c750c28bc9fbe441c` is rejected

This binding authorizes only Wave B4. It does not authorize Wave C–D, root
gitlink bump, production shadow activation, WP2, or value completion.

## Clone and verification boundary

- Managed governance clone:
  `/Users/xiamingxing/agents/grok-agent-os-recovery/attempts/claims-wp1-v150-binding-20260911-01/ws`
- Frozen root: `ff63d9171b2d0bb2f21cb91019f8a5fc6df36e2a`
- Delivery attempt: `a20260911T121426Z-v150bind`
- Binding run: `20260911T121510Z-governance-state-mutation-72463c14`

## Stop conditions

Any scope union with Wave B3 paths, implementation edit in this PR, root
gitlink mutation, second dispatcher registration, completion/value expansion,
reuse of the 1.4.0 WorkPacket hash, failed Binding QA on T10-145 surfaces,
unknown remote result or stale base stops this transaction. Rollback must be a
new successor binding with `implementation_authorized=false`, never restoring
1.4.0 as current authority while erasing Wave B3 evidence.
