---
schema_version: governance-waiver-evidence/v1
status: active
owner: human-principal
lifecycle: history
created: 2026-09-10
last-reviewed: 2026-09-09
value_indicator_policy: false
title: T10-127 pruner marker and successor consistency recovery waiver
type: doc
---

# T10-127 Pruner Marker and Successor Consistency Recovery Waiver

## Principal delegation

Verbatim temporary authority:

> 我要去休息了，针对上述这种精细化的授权，我估计暂时不能给你处理，直到明天上午10点之前，所有相关授权，你来自主处理，做好备案即可。

The delegation is interpreted under Asia/Shanghai and expires at
`2026-09-10T10:00:00+08:00`. It authorizes this reversible, repository-only
baseline recovery and its exact evidence record. It does not authorize force,
history rewrite, deletion of a live worktree, modification of host crontab or
LaunchAgent state, secret access, another BET transition or completion/value
claims.

## Trigger and diagnosis

Bound A2 child run `20260909T153147Z-bet-execution-5aa4f3a4` passed its own
focused/unit/Ruff verification but the required workflow check
`pyright-sweep-check` failed because
`tests/test_gac_worktree_lifecycle.py` read the nonexistent
`bin/gac/gac-worktree-cleanup.sh`.

Git history proves commit `0e6d649d53ea4b2e13ffd109783a76f5a0f99598`
(`BET-Y1Q4-T10-127`) intentionally archived that shell entry and introduced
`bin/gac/prune-zombie-worktrees.py`, while live tests and canonical references
were not fully migrated. This is a post-convergence baseline defect, not an A2
product failure. The A2 run was closed `blocked`, all six locks were released,
and its exact four-path staged child work was retained without commit or push.

Read-only analysis also proved a real safety regression in the successor:

1. `gac-worktree.sh claim` creates `.ws-<session>.claiming` before the worktree
   is registered;
2. the successor pruner did not inspect that marker and classified a
   pre-registration directory as `no-gitfile`;
3. in enforce mode it ignored `git worktree remove` failure, released the D2
   branch claim and incremented the removed count anyway.

This can create duplicate occupancy while the original initialization still
proceeds. Repairing only the test string would preserve the unsafe behavior and
is therefore rejected.

## Exact delegated recovery decision

Under the temporary delegation, one unbound governance recovery is authorized:

- restore the claim-in-progress marker as the first pruner fence;
- add one shared atomic `.ws-<session>.lifecycle-lock` to
  `gac-worktree.sh claim` and the successor pruner: claim holds it from before
  D2 branch occupancy through worktree/PASW initialization, while the pruner
  holds it from candidate adjudication through remove, branch handling and
  claim release;
- never release a claim, delete a branch or count removal unless worktree
  removal succeeds and the target is absent;
- migrate both lifecycle tests from the deleted shell to behavioral successor
  tests;
- replace the dead workflow route in canonical `_root.yaml`, then regenerate
  the read-only compatibility projection with its canonical writer;
- align the retired D5 registry to the successor and seven-day TTL;
- remove the uninstalled old six-hour PASW LaunchAgent template rather than
  redirecting it into a second destructive scheduler;
- remove the false active-master convergence-manifest record;
- outside that shared claim-side lock, correct only the stale compatibility
  comment in `gac-worktree.sh`.

No Ledger/BET, submodule, branch protection, CI workflow, host scheduler or
runtime service is modified.

This one recovery is an atomic cross-lane transaction: executable successor,
behavioral tests, canonical/derived governance routing, retired scheduler
template, convergence data and the authorization evidence must agree in the
same final tree. The official process-local interface
`AGENT_WORKFLOW_ALLOWED_LANES=governance_code,governance_state,docs_data,code`
is therefore authorized only for this transaction's local validation and Git
hooks. Advisory mode, `--no-verify`, a persistent environment setting or any
additional lane is not authorized. The `last-reviewed` value uses the current
UTC calendar date because document governance evaluates future dates in UTC;
the evidence filename and `created` field retain the Asia/Shanghai date.

## Exact scope

1. `bin/gac/prune-zombie-worktrees.py`
2. `bin/gac/gac-worktree.sh`
3. `tests/test_gac_worktree_lifecycle.py`
4. `tests/test_gac_worktree_lifecycle_integration.py`
5. `.omo/_truth/registry/agent-workflows/_root.yaml`
6. `.omo/_truth/registry/agent-workflows.yaml` (generated only by
   `agent-workflow.py projection-sync`)
7. `.omo/_truth/registry/swarm-coordination.yaml`
8. `.omo/_config/pasw-cleanup-launchd.plist` (tracked template deletion only)
9. `docs/operations/bin-scripts-convergence-manifest.json`
10. this waiver

Historical ADRs, accepted Specs, retros, patterns,
`bin/_archive/gac-worktree-cleanup.sh` and archive reports remain unchanged.

## Clone and workflow identity

- Actor: `codex-agent-os-recovery`
- Attempt: `t10-127-pruner-marker-recovery-20260910-01`
- Frozen root: `dd0d39fcebcf452773d8b1ba4a474a2ac3110de3`
- Managed full clone:
  `/Users/xiamingxing/agents/codex-agent-os-recovery/attempts/t10-127-pruner-marker-recovery-20260910-01/ws`
- Branch:
  `agent/codex-agent-os-recovery--t10-127-pruner-marker-recovery-20260910-01`
- Manifest digest:
  `2644e5d807e57fc68c934957fc1c702f0d2bae2a516383bd82d62329fa8bac31`
- Provenance status/digest:
  `ready / c2eae2d5cb633e448f8bcb2c97389cf56fa6359af52f03b103cb261d0a040375`
- Readiness status/digest:
  `ready / 67115e65c021661a0c44dec18a0eaf7824021f2aa9347b0fb08e4aece4c14e80`
- Workflow run:
  `20260909T161024Z-governance-state-mutation-f395460e`
- Affected graph:
  `3b89346a9814fb35338006a288dc53171fe0948b802f2fcb7838bd44bb5118d7`
- Generated projection source digest:
  `sha256:e7cba5657f21ce28e7ab9346b8ebfaf9002bb03a47bc98c882e5f5e277e2d405`

The canonical projection writer also removed one stale duplicate
`scene-lifecycle` block from the compatibility projection. The canonical split
source `.omo/_truth/registry/agent-workflows/workflows/scene-lifecycle.yaml`
remains present and registered; no executable workflow was deleted.

`AGCP_REQUIREMENT_ITERATION_GATE=0` was supplied only to this single unbound
start process. All claims, RED/GREEN work, verification, compliance, Git, CI
and closeout use default policy.

## TDD evidence

Before production changes, migrated behavioral tests returned `4 failed,
3 passed` for the exact expected reasons:

- marker-protected directory was classified `no-gitfile`;
- `main` had no injectable argv boundary;
- enforce-mode removal failure released/claimed success.

After the first minimal pruner change, the same suite returned `7 passed`.
Independent review then found a second scan-to-delete TOCTOU: marker,
registration or dirty state could change after the initial scan. New race tests
returned `2 failed, 7 passed` before the fix. The pruner performs two
fail-closed pre-effect rereads around the potentially slow protection check,
validating marker absence, path/registration state, cleanliness and branch
identity. Marker, registration and dirty races, plus failed removal with a
non-HEAD branch, invoke no remove/branch-delete/claim-release effect.

A subsequent review identified the remaining final race between the last
reread and deletion, plus a fail-open registration helper that collapsed a
failed `git worktree list` into an empty set. Atomic lifecycle-lock and
unprovable-registry tests first returned `3 failed, 10 passed`. The shell claim
path and Python pruner now contend on the same atomic
`.ws-<session>.lifecycle-lock` directory. The pruner holds that lock from final
candidate adjudication through removal, branch handling and claim release; a
concurrent claim stops before `git worktree add`. Worktree registration is read
with porcelain output and preserves timeout, command failure, empty output and
invalid-path states as unprovable/fail-closed. The same suite then returned
`13 passed`; two direct reader-contract tests were added, and the expanded
sweep/lifecycle/integration suite returned `23 passed`.

Post-GREEN verification also passed Ruff, `bash -n`, workflow projection check
at digest
`sha256:e7cba5657f21ce28e7ab9346b8ebfaf9002bb03a47bc98c882e5f5e277e2d405`,
script-registry validation (`641` registered), the exact eight-check workflow
verification, and the staged local GaC gate (`61` checks executed, all green;
six known-unavailable checks skipped by the non-strict contract). The four
lanes were admitted only through the explicitly recorded process-local lane
set above.

## Host and derived-artifact boundary

Read-only host observation found no loaded
`com.omostation.pasw-cleanup` service. The live crontab invokes
`make worktree-hygiene` daily, not the T10-127 weekly successor command. This
means there is no currently executing dead command, but T10-127 operational
cron evidence is not proven. Any host-scheduler repair is a separate explicit
operation and is not performed here.

Two dated `docs/generated/bin-tool-registry*.json` snapshots also contain the
dead path. Their current canonical producer/schema or retirement route was not
proven, so this recovery does not hand-edit or delete them. They remain
explicit derived-snapshot debt, not evidence that the dead entry is live.

## Stop conditions

Stop without publication if any change exceeds the ten paths, any behavioral
RED cannot be reproduced, any test still resolves the deleted shell as live,
projection sync is not deterministic, a live host scheduler would be mutated,
another writer overlaps the scope, a default gate fails for this change, or a
claim/completion/value statement would be inferred without direct evidence.
