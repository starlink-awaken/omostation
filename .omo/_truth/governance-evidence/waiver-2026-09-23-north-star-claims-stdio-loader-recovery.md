---
schema_version: governance-bootstrap-waiver/v1
type: governance-evidence
title: North-star Claims stdio loader recovery bootstrap waiver
status: active
lifecycle: contract
owner: governance-team
created: '2026-09-23'
last-reviewed: '2026-09-23'
bet_id: BET-Y2Q2-T4-01
operation_id: north-star-claims-stdio-loader-recovery-bootstrap-v1
principal_decision_id: principal-decision-ee7eceb1-4faa-42b9-b022-aac14204b6f7
decision_expires_at_utc: '2026-09-27T16:00:00Z'
---

# North-star Claims stdio loader recovery bootstrap waiver

## Purpose

This at-most-once waiver breaks a governance deadlock without bypassing Claims
Authority. The canonical root stdio loader imports the descriptor-bound
`claims_authority.py` as a top-level module, so its package-relative import
fails and the root falsely reports `unactivated` while the exact broker and
monotonic witness are `shadow-active`, epoch 1, sequence 2.

The principal explicitly authorized the repository repair. This waiver grants
no Claims verb, authority-store write, lifecycle operation, legacy publication,
instruction capability, or historical receipt mutation.

## Principal decision

- principal: `principal:xiamingxing`
- decision id:
  `principal-decision-ee7eceb1-4faa-42b9-b022-aac14204b6f7`
- decision time: `2026-09-23T12:10:42Z`
- expiry: `2026-09-27T16:00:00Z`
- authorization artifact:
  `/Users/xiamingxing/.local/share/zhixing-dashboard/claims-observation/claims-stdio-loader-recovery-principal-authorization-20260923T121042Z.json`
- authorization artifact SHA-256:
  `383050c42f5b653ce97e510babe7a5b9e7381ea1fa5bdd741273a0025cf6e773`
- bootstrap run id:
  `bootstrap-20260923T121042Z-north-star-claims-stdio-loader-recovery`
- governed workflow run id:
  `20260923T123727Z-bet-execution-4ab11bc6`
- recomputed WorkPacket digest:
  `sha256:897366cc547d272de457c1978859e0568cdd06d9bddfb4403a159f3212aed707`
- affected-graph receipt digest:
  `79c09ea53a3836a15e8f2b71d10a664c2af9fa88d8b1d3b4a108f4dcd7b463e7`
- effect process identity:
  `sha256:15464b73139a3ade1b9b76a3675dd617a6834938a8c6a03f174aba4a36aaf5bc`

The authorization permits one ordinary non-force branch push, one pull-request
creation or update, and one ordinary merge only after required checks pass and
both remote OID reads match. It forbids force, `--no-verify`, automatic retry
after unknown outcome, and all unlisted paths.

## Frozen bindings before first edit

- repository: `starlink-awaken/omostation`
- remote ref: `refs/heads/main`
- expected remote OID:
  `c7e1fdf09cb1edcd7e8bd26f3b100c76139b3628`
- both pre-edit remote reads:
  `c7e1fdf09cb1edcd7e8bd26f3b100c76139b3628`
- managed clone:
  `/Users/xiamingxing/agents/governance-agent/attempts/north-star-cp-repair-20260923e/ws`
- branch: `agent/governance-agent--north-star-cp-repair-20260923e`
- clone identity SHA-256:
  `710813557e17d7a57d359b82b8e39ea6c23f4b6f12850108c317229f7f0ef183`
- provenance SHA-256:
  `9d0c802651c88e1ab9f0f59a9b3b57483d5e7f3c1f545238f63b74fdd2c7b1f8`
- manifest SHA-256:
  `78a3d4c5c70e3bcc77b95f8a232c202a311c0ac09a08cd0ba485815335d851da`
- readiness SHA-256:
  `e8b2e3a2647bb7f2afd952a2ea818bb66f269adf9692bb75213b08cf27451daa`
- readiness receipt digest:
  `f9119e3c75f75d596b0c5bf649009479fb0be8d968a4f42af49f5d23ee7b7de3`

Claims binding before first edit:

- activation: `shadow-active`
- authority epoch: 1
- sequence: 2
- descriptor:
  `sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd`
- last receipt:
  `sha256:a660e34c55467e631f38d97e17b4d2377281fc5fe73a94b6f33548dbabe1eab7`
- effective authority: v1
- instruction capable: false
- store SHA-256:
  `ee3d9b9d6c53cc9b6407442128875989f5374856963d397e10d8cc4041ea16dd`
- high-water SHA-256:
  `c1973a6893583b65171136169468a7d10fb4afaa73d11e1d4b8d28181c29bcfb`
- activation-witness SHA-256:
  `06104cc6153cf4b759a34f5b69909db2e9e799b6f4e71b489f17b2bd37942357`

## Exact repository scope

Only these paths may differ from the frozen base:

1. `bin/agent-workflow.py`
2. `tests/test_agent_workflow.py`
3. `docs/superpowers/specs/2026-09-23-north-star-recovery-and-first-decision-episode-design.md`
4. `docs/plans/3y-bet-ledger.yaml`
5. this waiver

The retained #4249 retro is not rewritten. Its own text records that a complete
`EpisodeClosed` sample and four consecutive qualifying weeks do not exist, so
its merged `done`/`PROVEN` projection cannot satisfy the accepted Spec. The
Ledger is restored to non-terminal state while the historical retro remains
available as evidence of the contradictory closeout.

## Bootstrap sequence

1. Patch the exact-path loader and its tests.
2. Amend the accepted Spec and Ledger to cover this repair and restore honest
   non-terminal completion axes.
3. Run the focused and complete workflow test file.
4. Prove canonical stdio status equals direct broker status and prove the
   authority store, high-water, and witness hashes are unchanged.
5. Use the repaired canonical entrypoint to start and claim a normal governed
   run before any Git external effect.
6. Recompute and record the canonical WorkPacket; no previous packet is reused.

## Stop and rollback

Stop before the next effect on any remote drift, identity/hash drift, overlapping
claim, out-of-scope diff, failed/unknown check, stdio/direct mismatch, authority
file mutation, or Claims verb invocation. Repository rollback is an ordinary
non-force PR revert. Authority state and historical receipts are never rolled
back or rewritten.

## Bootstrap verification boundary

The first run-bound verify attempt was deterministically rejected before any
mutation verb with `AUTHORITY_ACTIVATION_WITNESS_INVALID`. The witness and its
embedded digest were valid and all three bound authority-file hashes were
unchanged. The rejection is the bootstrap cycle this repair addresses:
`projects/omo` intentionally calls the OS-account integration-root
`/Users/xiamingxing/Workspace/bin/agent-workflow.py`; that still-unmerged entry
reports `unactivated`, while the independent witness correctly reports
`shadow-active`.

The delegated principal decision therefore permits only non-run-bound,
read-only local verification and ordinary required CI for this bootstrap. It
does not permit retrying the rejected verify, bypassing Claims, changing clone
identity, or invoking a mutation verb. Run-bound verification remains blocked
until the repaired entrypoint is merged and installed at the integration root.
