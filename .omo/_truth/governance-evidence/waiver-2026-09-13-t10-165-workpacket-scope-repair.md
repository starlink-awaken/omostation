---
id: waiver-2026-09-13-t10-165-workpacket-scope-repair
scope: BET-Y1Q4-T10-165 final child integration and truth recovery
created: 2026-09-13
owner: governance-team
status: active
---

# T10-165 WorkPacket scope and premature-closeout recovery

## Authority

Under the user's standing delegation to repair execution-mechanism blockers and
post-merge truth regressions, unbound run
`20260913T125654Z-project-doc-change-50103674` authorizes exactly:

- `projects/omo`
- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_knowledge/retros/BET-Y1Q4-T10-165.md`
- this waiver.

It does not authorize another BET, accepted-spec change, value proof, external
writer admission, runtime mutation, or modification of any other gitlink.

## Why unbound

The original T10-165 WorkPacket omitted the root `projects/omo` gitlink path.
PR #3753 then marked the BET done before child PR #172 was integrated and while
its own retro said Claim, Verification, and ASD work remained pending. A bound
rerun against the incomplete WorkPacket could not claim the required root
integration path. `AGCP_REQUIREMENT_ITERATION_GATE=0` was used once only for
this unbound start; claims, verification, Git, CI, merge, and closeout use the
default gates.

## Recovery evidence

- Child PR #170 restored RoleRegistry and Capsule semantics.
- Child PR #172 completed Capsule→Mesh handoff, task_gateway claim binding, and
  Role-level verification; lint, test, and test-cov all passed.
- Child merge commit: `5fe0f477efa71d734b765ea2c28e55d1b1cdaa84`.
- Post-merge focused replay passed 180/180 tests.
- This PR advances root `projects/omo` from
  `4ab66bdd3870806f303d6b16c2c399308f6ecc62` to `5fe0f477efa71d734b765ea2c28e55d1b1cdaa84`,
  supplies the missing completion matrix, and corrects the retro. Value remains
  `NOT_PROVEN`; the overall state is delivery_accepted only.
