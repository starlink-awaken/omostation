---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-09
last-reviewed: 2026-09-09
title: Claims Authority Bridge WP1 R0 Shadow
bet_id: BET-Y1Q4-T10-145
implementation_authorized: false
value_indicator_policy: false
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-09
---

# Claims Authority Bridge WP1 R0 Shadow

## 1. One-sentence architecture

WP1 extends the existing OMO workflow lifecycle with one canonical, account-resolved
R0 claims broker that records v2 shadow decisions and drainable legacy fences while
the current v1 gate remains the only effective publication authority and the existing
`clone-lifecycle integrate` path remains the only Git effect owner.

This is the first child of parent `BET-Y1Q4-T10-143`. The parent
contract is
`docs/superpowers/specs/2026-09-09-claims-authority-bridge-design.md` version 1.0.0,
SHA-256 `a419e2fb3cd67026edebd39b25a1e1b77e6c92978ce1cf1be6b8e4be19cf8c58`.
Accepted version 1.0.0 allocates `BET-Y1Q4-T10-145` and creates a plan-only
WorkPacket. It does not authorize implementation, initialize a production store,
change Git publication behavior or materialize WP2.

## 2. Problem and current-state audit

The managed-clone execution tree and the current claims authority disagree. A valid
workflow run and exact path claim are stored inside its managed clone, while
`agent-clone.py::trusted_claims_authority()` accepts only the OS-account integration
Workspace. As a result, a valid successor clone is rejected as
`claims_authority_mismatch`, and delivery repeatedly needs an exact Human degraded
exception.

The issue is not a missing Git transport. It is an authority-placement and fencing
gap between claim validation and the single push effect.

| Component | Status | Current behavior | WP1 action |
|---|---|---|---|
| OMO run/claim lifecycle | [EXISTS] | `lifecycle.py` owns run, claim, heartbeat and close | [EXTEND] emit a shadow envelope after the v1 decision |
| WorkPacket scope check | [EXISTS] | `_validate_work_packet_claim()` checks exact write surfaces | [EXTEND] bind its inputs and result into the v2 receipt |
| Local YAML locks | [EXISTS] | clone-local, TTL-bound and non-canonical | [EXISTS] remain the v1 decision source during WP1 |
| Fixed claims authority | [EXISTS] | `trusted_claims_authority()` only accepts the integration Workspace | [EXISTS] unchanged as effective allow/deny during shadow |
| Changeset double-read | [EXISTS] | best effort, explicitly not atomic with push | [EXTEND] produce a comparable shadow observation, never an admission |
| Git/PR effect owner | [PARTIAL] | `clone-lifecycle.py::cmd_integrate()` is canonical, but legacy scripts still push/create PRs directly | [EXTEND] converge every tracked root/child publication entry through `cmd_integrate`; push argv is unchanged |
| Cross-clone coordination store | [EXISTS] | WAL/CAS/backup patterns, but environment-selectable and declared non-authoritative | [REFERENCE] reuse patterns only, never promote its DB |
| Canonical claims store | [BUILD] | absent | dedicated R0 store, receipt chain and external high-water |
| Claims broker CLI | [BUILD] | absent | one-request canonical stdio entry rooted in integration main |
| v2 shadow comparison | [BUILD] | absent | record v1/v2 pair and typed differences |
| Legacy publication fence | [BUILD] | absent | mandatory one-shot effect fence after v1 allow; cannot grant scope |
| Observer API | [BUILD] | absent | redacted `claims-authority status --json`, never instruction-capable |

`bin/gac/coordination_store.py` is an implementation reference, not a write surface
and not authority. Workflow Mesh events and Dashboard views are projections, not
authority.

## 3. Alternatives considered

### A. One WP1 child with versioned non-union binding replacements — selected

One child BET owns the whole R0 shadow milestone, but its sole accepted binding is
replaced between plan, child core, root adapter, root pointer and observation stages.
At every instant the Ledger-derived WorkPacket exposes exactly one partition; old
write surfaces are removed, never unioned. This matches the accepted parent, makes a
cross-stage claim structurally impossible, keeps WP2 absent and permits one 24-hour
graduation decision.

### B. Three sibling BETs for child, adapter and shadow window — rejected

This creates more coordination objects but does not create three independent outcomes.
It also weakens the parent contract, which defines one WP1 child as the materialization
gate for WP2.

### C. Trust the managed clone or copy its YAML into Workspace — rejected

This is self-authorization. It preserves the exact defect and gives copied projections
authority they do not possess.

## 4. Boundary and layer model

```text
L4 Human / accepted parent contract
      |
      v
L3 clone-lifecycle integrate ------------------------+
      | effective v1 decision                         |
      |                                               | sole Git/PR effect
      +--> [WP1 shadow seam] --> canonical stdio ---->| (argv unchanged)
                                 broker                |
                                      |                |
L2 OMO lifecycle + claims_authority.py                |
      | v1 decision pair | v2 shadow receipt          |
      v                                               |
L1 account-resolved R0 store + high-water + backups  |
      |                                               |
L0 canonical JSON schemas + digests + typed errors   |
                                                      |
X1: fail closed for v2 evidence; never alter v1       |
X2: sequence, lease, expiry, freshness, 24h window    |
X3: value_indicator_policy=false                      |
X4: receipt chain, exact identity and decision parity +
```

| Layer | Question | WP1 responsibility |
|---|---|---|
| L0 contract | What is a valid authority object? | canonical JSON, schemas, digests and typed errors |
| L1 storage | Where is shadow authority state? | one account-resolved store, high-water and three backups |
| L2 kernel | Who evaluates claims? | OMO broker independently rereads identity, WorkPacket and paths |
| L3 delivery | Where is the effect? | unchanged `clone-lifecycle integrate`; shadow cannot push |
| L4 authority | Who may graduate? | accepted parent plus explicit Human/delegated graduation decision |

No new project, daemon, LaunchAgent, service account, network port, MCP server or
Dashboard command is introduced.

## 5. Authority and trust model

### 5.1 Canonical resolution

Production resolution derives the account home with `pwd.getpwuid(os.getuid())`, then
binds the integration root to the canonical Workspace identity from committed policy.
It must not accept `$HOME`, cwd, a clone-local policy, `--claims-root`, `--store`,
`--db`, `WORKSPACE_ROOT` or `OMO_COORDINATION_DB` as a production authority selector.

The R0 authority identity is `omo-claims-authority-r0`. Its dedicated store, high-water
and backup directories follow parent Spec §8.1. Existing ancestors are verified, never
chmodded. Symlink, owner or unsafe-mode drift returns `AUTHORITY_STORE_UNSAFE`.

### 5.2 Cooperative limit

Every production WP1 receipt is labeled `R0_COOPERATIVE`. Same-UID malicious writes
remain out of scope. No object may claim `ADVERSARIAL_ENFORCED`; R1 remains a separate
future Spec and operation-specific host decision.

### 5.3 Projection boundary

Clone-local run and claim files may contain a receipt reference, digest, broker
sequence and observation timestamp. They cannot authorize an effect. Deleting or
editing a projection cannot create, close, renew or settle a canonical claim.

## 6. Components and responsibilities

### 6.1 Child broker module

`projects/omo/src/omo/workflow/claims_authority.py` owns:

- canonical object encoding and SHA-256 digest;
- descriptor and request schema validation;
- account-safe store resolution;
- SQLite schema, serial migrations and query-only test injection;
- receipt sequence, previous digest and idempotency rows;
- claim/lease CAS and shadow decision recording;
- legacy-fence shadow state and settlement evidence;
- high-water verification, crash-tail reconciliation and backup manifests;
- redacted status response and stable typed errors.

It never runs Git, `gh`, workflow closeout, service control or host recovery.

### 6.2 Lifecycle hook

`projects/omo/src/omo/workflow/lifecycle.py` constructs a
`ClaimMutationEnvelope` only after the existing v1 claim result is known. The hook:

1. independently rereads accepted Spec/WorkPacket, identity and affected graph;
2. calls the canonical integration-root broker;
3. records a v1/v2 comparison pair;
4. emits `shadow_observed`, `shadow_difference` or `shadow_unprovable`;
5. returns the original v1 result unchanged.

Broker absence, timeout, malformed stdout or mismatch cannot change the stored v1
claim verdict. Separately, a v1-allowed publication still stops before Git when it
cannot obtain and enter the mandatory LegacyPublishFence.

### 6.3 Root CLI adapter

`bin/agent-workflow.py` recognizes `claims-authority` with standard-library argument
parsing before repository imports. Mutation verbs accept exactly one canonical JSON
request on stdin. `status --json` is the only bodyless read-only form. Stdout contains
one JSON object; diagnostics go to stderr.

### 6.4 Changeset and publication observer

`agent-clone.py` computes the existing v1 verdict and a v2 shadow observation over the
same immutable identity, WorkPacket, affected graph and exact paths. The changeset
keeps existing `claim_verification.enabled`, `all_covered` and `violations` semantics
unchanged, and adds a sibling `claims_authority_shadow` object. Shadow fields never
stand in for `all_covered=true`.

`clone-lifecycle.py` adds one shadow seam between final verification and the existing
push. The code is inert until an exact descriptor activation receipt exists. Before
activation, Waves B1, B2, B3, B4 and C must report
`shadow_unprovable:not_activated` and retain the
pre-WP1 legacy effect behavior so the bridge can bootstrap without fencing its own
delivery.

After Waves A, B1, B2, B3, B4 and C are on authoritative main, a separately authorized
host transaction may activate the exact descriptor in `shadow-active` mode. From that
atomic activation point onward, after v1 allows an already-supported legacy
Workspace/worktree publication, the canonical broker must issue a
`LegacyPublishFence`, and `cmd_integrate()` must enter
that exact fence into durable `publishing` before Git. The fence cannot grant a path,
repair a failed claim or make a managed clone publishable. Missing, expired, replayed
or unavailable fencing blocks the Git effect even though the underlying v1 semantic
allow/deny result remains unchanged. This is the drainable effect interlock required by
the parent contract, not v2 claim enforcement.

WP1 does not consume a v2 PublishIntent, change the canonical push argv, add automatic
retry or create a second push path. Settlement records the exact remote observation
for the same legacy fence. An unknown effect result freezes that fence and requires
operator resolution; it never mints a replacement.

The current `--force-with-lease` new-branch command and exact PR lookup/create logic
remain byte-for-byte behaviorally equivalent. WP2, not WP1, owns cooperative
enforcement and the ordinary non-force operational canary.

### 6.5 Publication effect convergence

The current root tree contains additional effect entries. WP1 must remove their Git
ownership rather than merely document them:

| Existing entry | WP1 disposition |
|---|---|
| `bin/gac/gac-worktree.sh submit` | build a verified legacy changeset, request/enter one fence, then delegate push and exact PR lookup/create to `clone-lifecycle integrate --apply` |
| `bin/gac/git-retry.sh push` | reject the `push` verb with `PUBLICATION_OWNER_REQUIRED`; retain fetch/pull network retry only |
| `bin/gac/gitlink-drift-protect.py --fix` | stop before Git and emit a remediation proposal requiring a managed delivery transaction |
| `bin/sync-submodules.sh` | become read-only detection; an unpushed child commit is a failure, never auto-pushed to main |
| `bin/ssot/sync-submodules-push.sh` | preserve the compatibility path but make it verification-only; pre-push never launches a nested child push |
| `scripts/wait-and-bump-cockpit.sh` | preserve `--validate` as a read-only historical check; all modes either report already integrated or stop with `PUBLICATION_OWNER_REQUIRED` before commit/push |
| `bin/gac/gh-api-push.sh` | hard-reject before any Git Data API POST/PATCH; its registry and Agent Brief point to canonical integrate |
| `bin/gac/git-shim` and `bin/gac/swarm-git` | reject every `push` with `PUBLICATION_OWNER_REQUIRED`; no exact-argv exception remains in wrappers |
| `clone-lifecycle.py` | resolve the real Git executable outside the shim path, bind its identity in the descriptor and invoke it directly only inside the fenced effect block |
| submodule autobump/freshness GitHub workflows | become detection/report-artifact workflows with read-only repository permissions; no push or PR creation |
| `omo-autopilot.yml` | upload a proposed patch/report artifact instead of using `peter-evans/create-pull-request` |

The wrappers remain command guards, not effect owners. The canonical integrate path
uses a descriptor-bound real Git executable rather than a caller-selected environment
override. Root scripts may invoke Git for read-only inspection, fetch or local commit
operations, but no tracked root automation other than `clone-lifecycle.py` may execute
a remote Git ref write or create a PR. The inventory gate permits local commit/index
operations and covers literal Git commands,
wrapper reachability, GitHub Git Data API write endpoints and third-party PR-creation
actions; it is not a string-only grep.
Child repositories publish through their own managed clone-lifecycle transaction; a
root pre-push hook never publishes a child commit on their behalf.

### 6.6 Registry

`.omo/_truth/registry/swarm-coordination.yaml` may declare only:

- `authority_id`;
- requested mode `shadow`;
- critical dependency path names;
- receipt/status freshness thresholds;
- v1 compatibility `legacy-effective-shadow`.

It must not embed the descriptor digest, an allow flag, a caller-selected path or a
cutover request.

Merged policy is only requested configuration. The broker activation CAS, which binds
the exact root commit, policy blob, child gitlink, critical closure and managed-Python
receipt, is the sole transition from `unactivated` to `shadow-active`. A missing or
failed activation receipt leaves the system unactivated and cannot partially require a
fence.

## 7. Data and state contracts

The child module implements the parent v2 object set without changing parent schemas:

- `claims-authority-descriptor/v2`;
- `claim-mutation-envelope/v2`;
- `claims-authority-receipt/v2`;
- `claims-legacy-publish-fence/v2`;
- `claims-publication-settlement/v2`;
- `claims-authority-projection/v2`;
- `claims-authority-status/v2`.

WP1 may represent PublishIntent fixtures for RED/race tests, but it never issues a
publishable production v2 intent.

```text
v1 claim result ------+
                      +--> comparison pair --> explained | unexplained
v2 shadow result -----+                           |
                                                  +--> graduation counter

shadow receipt: proposed -> active -> closed | expired | taken_over
legacy fence:  issued -> publishing -> settled | unknown
activation:    unactivated -> shadow-active
```

The v2 claim verdict is evidence-only during WP1. A LegacyPublishFence is different:
it is a mandatory one-shot safety interlock for an effect already allowed by v1. It
cannot grant scope or reverse a v1 denial, but missing/invalid fencing must block Git so
that every legacy effect is visible and drainable. Neither object is a v2 admission.

Every mutation uses `BEGIN IMMEDIATE`, WAL, `synchronous=FULL`, foreign keys and a
5-second busy timeout. Receipt, sequence, previous digest, idempotency row and state
transition commit atomically. High-water reconciliation is limited to the exact
one-tail case defined by the parent. Corruption never auto-restores.

WP1 inherits the parent time contract without weakening it:

- an active claim lease lasts 15 minutes;
- heartbeat interval is at most 5 minutes and every renewal increments lease epoch;
- a PublishIntent exists only in fixtures during WP1 and expires after 300 seconds;
- broker time more than 30 seconds behind persisted `last_broker_time` returns
  `AUTHORITY_CLOCK_ROLLBACK` and issues nothing;
- observer output is fresh for at most 120 seconds;
- entering `publishing` freezes the bound claim: close, takeover, expiry, heartbeat and
  a second intent/fence are rejected until settlement or separately authorized
  resolution proves the effect process ended and the exact remote OID.

Before any future cutover, legacy-fence issuance for an epoch must be CAS-closed and
all `issued`, `publishing`, `unknown` and `operator_required` states drained. A v1
snapshot taken before epoch closure cannot execute Git after closure.

## 8. Shadow comparison policy

Each observation records the same immutable input identity and two results:

```json
{
  "effective_v1": {"decision": "allow|deny", "code": "..."},
  "shadow_v2": {"decision": "would_allow|would_deny|unprovable", "code": "..."},
  "classification": "equivalent|expected_managed_clone_difference|unexplained",
  "effective_claim_authority": "v1",
  "publication_effect_fence": "legacy-v2-required-after-v1-allow",
  "instruction_capable": false
}
```

The only expected difference is a valid managed clone denied solely by the fixed v1
authority root while v2 independently validates it. Any other difference, missing
input or v2 false-allow is `UNPROVABLE` and resets the continuous graduation window.

## 9. Exact delivery partitions and binding versions

No accepted WorkPacket may expose the paths below together. The child keeps one BET ID
and one accepted Spec binding, but every stage uses a fresh Spec version and a complete
replacement of `scope.write_surfaces`. A replacement removes the prior partition;
union, append-only accumulation or reuse of an earlier WorkPacket hash is a hard
`WORK_PACKET_SCOPE_MISMATCH`.

| Accepted version | Only permitted write surface | Purpose |
|---|---|---|
| 1.0.0 | `docs/superpowers/plans/2026-09-10-claims-authority-bridge-wp1-shadow.md` | writing-plans only; implementation remains unauthorized |
| 1.1.0 | Wave A three child paths | child broker/lifecycle implementation |
| 1.2.0 | Wave B1 six root paths | lazy shadow adapter, fence integration and registry |
| 1.3.0 | Wave B2 nine effect-convergence paths | eliminate every alternate tracked push/PR owner |
| 1.4.0 | Wave B3 nine bypass/shim paths | close Git Data API and wrapper publication bypasses |
| 1.5.0 | Wave B4 five GitHub automation paths | make cloud automation proposal-only |
| 1.6.0 | Wave C `projects/omo` only | root gitlink closeout |
| 1.7.0 | Wave D two evidence paths | activation, 24-hour observation, graduation report and retro |

Each replacement is its own accepted-binding transaction from then-latest main, with
an exact Spec digest, WorkPacket hash, independent review and required checks. A run
bound to version N must be closed and its locks released before version N+1 is created.
The binding history is preserved, while `accepted_specifications` contains one current
binding only.

### Wave A — child broker and lifecycle

```text
projects/omo/src/omo/workflow/claims_authority.py
projects/omo/src/omo/workflow/lifecycle.py
projects/omo/tests/test_workflow_claims_authority_bridge.py
```

Wave A is a child-repository PR. It must merge and pass child post-merge CI before any
version 1.2.0 is created. Version 1.1.0 contains none of the plan, root, pointer or
evidence paths.

### Wave B1 — root shadow adapter and canonical fence owner

```text
bin/agent-workflow.py
bin/gac/agent-clone.py
bin/gac/clone-lifecycle.py
tests/test_agent_workflow.py
tests/test_clone_lifecycle.py
.omo/_truth/registry/swarm-coordination.yaml
```

Wave B1 is a root PR based on a root whose `projects/omo` pointer still lacks the new
child interface. It must lazily report `shadow_unprovable` and preserve all legacy
claim semantics. It must not change the canonical Git push argv. Version 1.2.0 contains
none of the child, plan, alternate-entry, pointer or evidence paths.

### Wave B2 — publication effect-owner convergence

```text
bin/gac/gac-worktree.sh
bin/gac/git-retry.sh
bin/gac/gitlink-drift-protect.py
bin/sync-submodules.sh
bin/ssot/sync-submodules-push.sh
scripts/wait-and-bump-cockpit.sh
tests/test_gac_worktree_claim_pasw.py
tests/unit/gac/test_submodule_pointer_transaction.py
tests/test_git_publication_effect_owner.py
```

Wave B2 routes `gac-worktree submit` through the canonical integrate owner, makes both
submodule sync scripts detection-only, rejects generic push through `git-retry.sh`,
removes auto-push from drift protection and converts the completed one-off Cockpit
script to read-only validation. The dedicated test proves these compatibility entries
cannot reach a fake Git/GitHub writer. Version 1.3.0 contains no child, B1, plan,
pointer or evidence path.

### Wave B3 — API and Git-wrapper bypass closure

```text
bin/gac/gh-api-push.sh
bin/_registry/scripts/governance/gh-api-push.yaml
bin/gac/git-shim
bin/gac/swarm-git
docs/plans/AGENT-BRIEF.md
tests/integration/test-git-shim.sh
tests/unit/gac/test_immutable_writer_git_policy.py
tests/test_swarm_discipline.py
tests/test_git_publication_effect_owner.py
```

Wave B3 makes the Git Data API helper fail before every write endpoint, marks its
registry entry non-publishing, updates the active Agent Brief, and makes both wrappers
reject all push verbs. `clone-lifecycle.py` already belongs to B1 and must use the
descriptor-bound real Git executable inside its fenced effect block. Fake-executable
tests prove the wrappers and API helper have zero ref/blob/tree/commit/PR effects.
Version 1.4.0 contains no A/B1/B2, pointer or evidence path.

### Wave B4 — cloud publication removal

```text
.github/workflows/submodule-autobump.yml
.github/workflows/reusable-submodule-bump-pr.yml
.github/workflows/submodule-freshness-gatekeeper.yml
.github/workflows/omo-autopilot.yml
tests/test_github_publication_effect_owner.py
```

Wave B4 replaces automatic branch/commit/push/PR creation with read-only detection and
uploaded proposal artifacts. It removes write repository permissions where no other
step needs them. The workflows may report a proposed patch or stale gitlink but cannot
write a ref. Version 1.5.0 contains no local adapter, child, pointer or evidence path.

### Wave C — root pointer

```text
projects/omo
```

Wave C is a separate root pointer PR after Waves A and B1–B4. It runs recursive
checkout, require-main reachability and cross-layer integration before merge. Version 1.6.0
contains no source, test, registry, plan or evidence path.

### Wave D — observation and graduation evidence

```text
.omo/_truth/governance-evidence/claims-authority-bridge-wp1-shadow-graduation.json
.omo/_knowledge/retros/BET-Y1Q4-T10-145.md
```

The ID above is collision-checked and allocated by the accepted 1.0.0 binding. It
remains candidate/evaluating. Wave D may write `done` evidence only after the complete
24-hour window and all criteria in §12. Before that it records a non-terminal shadow
report and leaves the child candidate/evaluating. Version 1.7.0 contains no
implementation or gitlink path.

The initial 1.0.0 accepted binding is plan-only. Writing-plans uses a fresh bound run,
claims only the plan, verifies and closes before the 1.1.0 Wave A amendment. It cannot
create code, a store, a receipt or an implementation claim.

### 9.1 Binding replacement transaction

Every 1.0.0–1.7.0 replacement is outside the current implementation WorkPacket and is
performed as a separate Human- or time-bounded-delegated bootstrap transaction. It may
claim exactly:

```text
docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md
docs/plans/3y-bet-ledger.yaml
.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v100-binding.md
```

The code block is the exact initial 1.0.0 transaction. Every later replacement must
name a new exact version-specific waiver path in its own authorization; wildcard or
template claims are invalid. The transaction must start from then-latest main, record the exact authorization,
modify only the T10-145 entry and current Spec binding, pass required checks, merge and
close before the newly bound implementation run starts. If a bypass is required for
the self-binding start, it is process-local to that start only and is recorded in the
waiver. It never applies to claim, verify, Git, CI or closeout. The prior run must be
closed and all its locks zero before the next binding transaction starts.

## 10. Error handling matrix

| Code | Scenario | WP1 result | Retry |
|---|---|---|---|
| `AUTHORITY_UNAVAILABLE` | broker unavailable/timeout | before activation: observation `unprovable`, legacy bootstrap unchanged; after activation: any unfenced Git effect stops | no automatic retry in effect path |
| `AUTHORITY_DESCRIPTOR_MISMATCH` | critical path/runtime drift | v2 `unprovable`; no receipt | no |
| `AUTHORITY_STORE_UNSAFE` | symlink/owner/mode violation | fail closed for v2 | no |
| `AUTHORITY_STORE_CORRUPT` | integrity or chain failure | preserve store; v2 unavailable | operator-only recovery |
| `AUTHORITY_HIGHWATER_ROLLBACK` | DB behind high-water | v2 unavailable | no |
| `AUTHORITY_HIGHWATER_GAP` | DB ahead by more than one | v2 unavailable | no |
| `AUTHORITY_CLOCK_ROLLBACK` | broker clock >30s behind high-water time | issue nothing; preserve evidence | no |
| `REQUEST_SCHEMA_INVALID` | malformed request | typed denial | no |
| `REQUEST_ID_REUSE_MISMATCH` | same ID, different payload | typed denial | no |
| `IDENTITY_MISMATCH` | actor/attempt/repo/branch/HEAD mismatch | would-deny | no |
| `WORK_PACKET_UNBOUND` | unbound/stale packet | would-deny | new accepted transaction only |
| `CLAIM_SCOPE_VIOLATION` | path outside WorkPacket | would-deny | no |
| `AFFECTED_GRAPH_MISMATCH` | graph/path digest disagreement | would-deny | rebuild exact receipt |
| `CLAIM_VERSION_STALE` | claim/lease changed | would-deny | fresh lifecycle transaction |
| `CLAIM_LEASE_EXPIRED` | claim lease exceeded 15m | would-deny; no fence | fresh run only |
| `LEGACY_FENCE_ISSUANCE_CLOSED` | legacy epoch is draining | zero Git effect | no |
| `LEGACY_FENCE_REPLAY` | reused legacy fence | zero Git effect | no |
| `LEGACY_DRAIN_INCOMPLETE` | unresolved legacy effect exists | no graduation/cutover | settle same fence |
| `PUBLISH_INTENT_EXPIRED` | 300s fixture intent expired | RED fixture | no refresh |
| `PUBLISH_INTENT_REPLAY` | second consume/enter-publishing | RED fixture | no |
| `REMOTE_OID_DRIFT` | expected remote ref changed | record difference and stop before Git | new immutable successor only |
| `V1_AUTHORITY_FORBIDDEN` | v1 tries to authorize managed clone | deny; no fence | no |
| `PROJECTION_STALE` | clone projection older than 120s | rebuild projection | query only |

Raw payloads, usernames, account home, hostnames, absolute paths and remote URLs are
never returned by the observer API.

## 11. Required RED/GREEN matrix

Every row of parent Spec §11 is inherited and must map one-to-one to a named WP1 test;
the table below is the traceable WP1 closure, not a reduced sample. Removing or
combining a parent row without preserving its independent negative mutation is a
binding failure.

| Attack | Expected result |
|---|---|
| clone-local or arbitrary external root presented as authority | RED |
| hand-created, copied or modified run/receipt presented as authority | RED |
| environment/cwd/CLI attempts to redirect production store | RED |
| store, high-water, backup or clone path symlink escape | RED |
| wrong owner or unsafe mode | RED |
| actor, attempt, repository, branch or HEAD mismatch | RED |
| identity, manifest or readiness digest drift | RED |
| unbound/stale WorkPacket or scope overflow | RED |
| affected graph/path mismatch | RED |
| claim version/lease race, expiry, takeover or replay | RED |
| broker clock rolls back more than 30 seconds | RED; issue nothing |
| token/fence is consumed twice or refreshed after expiry | RED |
| claim is close/takeover/expired/heartbeat-renewed or receives a second intent while `publishing` | RED; keep frozen |
| legacy epoch closes after a v1 snapshot but before Git | RED before effect |
| cutover/graduation while any `issued/publishing/unknown/operator_required` fence exists | RED |
| request ID reused with different payload | RED |
| expected remote OID changes between verification and effect | RED before Git |
| descriptor closure or managed-Python receipt drift | RED |
| policy blob attempts to embed the descriptor digest that includes itself | RED self-reference |
| two authority reads disagree | RED; no receipt/fence/effect |
| store sequence rollback, high-water gap or broken receipt chain | RED |
| test authority receipt reaches production verifier | RED |
| R0 receipt labeled adversarial | RED |
| projection attempts to overwrite authority | RED |
| projection disagrees with authority | rebuild projection; authority unchanged |
| v1 receipt authorizes a managed clone during WP1 | RED |
| v1 receipt authorizes any publication after a future cutover | RED fixture |
| v1 run/claim record is copied or promoted into v2 | RED |
| v2 shadow result changes effective v1 allow/deny | RED |
| shadow hook changes push argv, adds a push or creates a PR | RED |
| B1/B2/B3/B4/C delivery is fenced before exact shadow activation | RED bootstrap deadlock |
| broker/fence failure is followed by a legacy Git effect | RED; zero push/PR effect |
| any tracked script, GitHub workflow, Git Data API helper or wrapper outside `clone-lifecycle.py` reaches a Git/PR write | RED |
| valid legacy claim + exact HEAD + fresh fence | GREEN: consume once, enter `publishing`, execute canonical argv once, reread remote and settle same fence |
| repeated settlement with the same canonical payload | GREEN: return the same receipt idempotently |
| valid managed clone | v1 fixed-root deny + v2 expected shadow difference; no publication |

Tests must demonstrate RED before implementation where a current behavior is wrong.
No production store, Git remote or host service is used by unit tests; test authority is
`test:<uuid>` and `publishable=false`.

## 12. Acceptance and graduation

| ID | Assertion | Evidence |
|---|---|---|
| CAB-WP1-AC-01 | Canonical broker/store resolution cannot be redirected by caller env, cwd, clone or CLI path | negative test report |
| CAB-WP1-AC-02 | Receipt chain, idempotency, CAS, high-water, crash-tail and three-backup rotation pass | test/replay report |
| CAB-WP1-AC-03 | v2 shadow never grants or denies a claim; every v1-allowed Git effect requires one consumable legacy fence and keeps canonical push argv | root regression tests |
| CAB-WP1-AC-04 | Full §11 RED matrix passes; zero v2 false-allow | immutable test report |
| CAB-WP1-AC-05 | Child, B1 adapter, B2/B3 local convergence, B4 cloud convergence and root pointer PRs merge in order with exact-SHA and required CI | delivery receipts |
| CAB-WP1-AC-06 | Same immutable fixtures produce recorded v1/v2 comparison pairs with typed classifications | comparison report |
| CAB-WP1-AC-07 | Shadow status is redacted, `instruction_capable=false`, and stale after 120 seconds | observer contract tests |
| CAB-WP1-AC-08 | At least three independent lifecycles cover managed clone, legacy regression and expiry/replay | lifecycle receipts |
| CAB-WP1-AC-09 | A continuous 24-hour window has zero unexplained differences and zero false-allows | graduation report |
| CAB-WP1-AC-10 | R0 is labeled cooperative; operational/value remain `NOT_PROVEN` until direct evidence | schema/Ledger check |
| CAB-WP1-AC-11 | WP2 has no Ledger ID, binding, run or write surface before WP1 is done | portfolio gate |
| CAB-WP1-AC-12 | Tracked repository publication inventory finds exactly one push/PR effect owner; wrappers, API helpers, cloud workflows and submodule pre-push perform no alternate publication | source scan and negative tests |
| CAB-WP1-AC-13 | Before descriptor activation, bridge delivery preserves legacy bootstrap effects; after exact `shadow-active`, every v1-allowed effect requires a fence | pre/post activation test pair |

The 24-hour clock starts only after Waves A, B1, B2, B3, B4 and C are on authoritative main, production
shadow activation has an exact descriptor receipt, the observer reads are repeatable
and all RED tests are green. Any unexplained difference, false-allow, sequence gap,
identity drift or observer blindness resets the window.

## 13. Daily implementation sequence

| ID | Timebox | Prerequisite | Work | Acceptance | Output | Main risk |
|---|---|---|---|---|---|---|
| D0 | 0.5 day | accepted 1.0.0 plan-only binding | write implementation plan and frozen fixture matrix; close plan run | plan review clear; only plan path changed | exact plan | scope union |
| D1 | 0.5 day | D0 closed | replace binding with 1.1.0 Wave A only | current WorkPacket has exactly three child paths | binding receipt | stale plan surface |
| D2 | 1 day | 1.1.0 | RED tests plus canonical schemas/store core | RED proves current absence; store unit tests green | child commit | accidental second authority |
| D3 | 1 day | D2 | lifecycle shadow hook, receipts/high-water/backup | v1 result byte-equivalent; child CI green | child PR | shadow affecting gate |
| D4 | 0.5 day | child main | replace binding with 1.2.0 Wave B1 only | current WorkPacket has exactly six B1 paths | binding receipt | child/root union |
| D5 | 1 day | 1.2.0 | root CLI, comparison adapter and mandatory legacy fence owner | v1 claim regressions green; canonical push argv unchanged | root adapter PR | lazy-interface mismatch |
| D6 | 0.5 day | D5 | replace binding with 1.3.0 Wave B2 only | current WorkPacket has exactly nine B2 paths | binding receipt | alternate effect missed |
| D7 | 1 day | 1.3.0 | route/disable legacy script publication paths | fake effect tests see zero nested/alternate publication | B2 PR | legacy entry regression |
| D8 | 0.5 day | D7 | replace binding with 1.4.0 Wave B3 only | current WorkPacket has exactly nine B3 paths | binding receipt | API/shim bypass missed |
| D9 | 1 day | 1.4.0 | close Git Data API and wrapper bypasses | API/wrapper fake executables see zero writes | B3 PR | canonical Git identity drift |
| D10 | 0.5 day | D9 | replace binding with 1.5.0 Wave B4 only | current WorkPacket has exactly five B4 paths | binding receipt | cloud publisher missed |
| D11 | 1 day | 1.5.0 | make GitHub automation proposal-only | workflow test finds no ref/commit/push/PR write | B4 PR | lost proposal artifact |
| D12 | 0.5 day | D11 | replace binding with 1.6.0 then update root pointer | 16/16 reachability plus required CI | root pointer PR | unreachable gitlink |
| D13 | 0.5 day | A/B1–B4/C main | replace binding with 1.7.0; separately authorize production shadow activation | descriptor/store safety PASS | activation receipt | host path/permission drift |
| D14 | 24h minimum | D13 | three lifecycle classes and continuous observation | zero unexplained/false-allow | graduation report | blind observer |
| D15 | 0.5 day | D14 | independent audit and honest closeout | candidate completes only if all AC pass | retro/receipts | premature done |

Only one writer works in a repository at a time. A read-only reviewer may operate in
parallel. Child-first/root-last is mandatory.

## 14. Self-red-team

| Question/attack | Resolution |
|---|---|
| Is this patch-on-patch complexity? | It replaces degraded exceptions with one broker and one existing effect path; no new project/service. |
| Cold start with no DB/high-water? | Initialize only when both are absent; asymmetric presence is `UNPROVABLE`. |
| Broker is down? | Before activation it is shadow-unprovable and bootstrap remains possible; after activation v1 still supplies semantics but no unfenced Git effect runs. |
| Same-UID attacker forges R0? | Explicitly out of scope and never labeled adversarial. |
| Schema evolves? | `PRAGMA user_version`, forward-only serial migration and pre-migration backup. |
| Agent-specific coupling? | Envelope binds neutral actor/attempt/repository identities, not Codex/Claude/Orca. |
| Economic burden? | One process per request and lazy daily backup; no daemon or recurring compute. |
| Test authority escapes? | `test:*`, `publishable=false`, production verifier hard-rejects it. |
| Anti-entropy mechanism decays? | Descriptor closure, high-water and 120-second freshness make drift visible and fail closed for v2. |
| Dashboard becomes authority? | Only redacted status, always `instruction_capable=false`. |

## 15. Rollback

Before WP2, rollback is an explicit repository rollback to the pre-WP1 v1 behavior.
There is no automatic runtime fallback around the mandatory legacy fence, and rollback
does not rewrite receipts or make a degraded exception permanent.

1. Stop new shadow observations and fence issuance; block publication while any fence
   is issued, publishing, unknown or operator-required.
2. Settle or separately resolve every in-flight legacy fence; never mint a replacement.
3. Preserve store, high-water, backups, comparisons and unexplained differences.
4. Revert child, B1 adapter, B2/B3 local convergence, B4 cloud convergence and root
   pointer in separate repository-ordered PRs.
5. Only the merged rollback may restore the exact pre-WP1 v1 effect routes.
6. Do not auto-restore corruption, copy projections into authority, change live
   permissions or reclassify an unknown result.
7. Do not materialize WP2 unless WP1 later re-runs and graduates from a fresh 24-hour
   window.

## 16. Anti-metrics and non-goals

The following do not prove WP1 success:

- number of schemas, receipt fields, tests or lines of code;
- a green clone-local projection;
- a copied v1 workflow file;
- a degraded direct push;
- Dashboard rendering a shadow receipt;
- one positive fixture without the complete RED matrix;
- less than 24 hours of observation;
- a shadow `would_allow` called `admitted`;
- CI or engineering proof counted as personal value.

WP1 does not enforce v2 claim admission or issue a publishable v2 intent. It enforces
only the parent-required LegacyPublishFence around an effect already allowed by v1.
It does not change the canonical Git push command, add multi-tenant RBAC/HA/R1
security, modify branch protection, install host services, operate the Dashboard,
complete the parent BET or create WP2.

## 17. Acceptance record and transition gate

Version 1.0.0 acceptance requires and records:

1. two independent read-only reviews must find no scope, authority, storage or effect
   ownership contradiction;
2. candidate ID `BET-Y1Q4-T10-145` must remain collision-free at binding time;
3. accepted version 1.0.0 must have a plan-only WorkPacket and parent relation to
   `BET-Y1Q4-T10-143`;
4. version 1.0.0 keeps `implementation_authorized=false`; it authorizes only the
   writing-plans artifact;
5. `implementation_authorized` may become true only in the 1.1.0 Wave A replacement
   under direct or time-bounded delegated Human authority;
6. every later binding must replace, not append, `write_surfaces`, keep one current
   `accepted_specifications` entry and reject an earlier WorkPacket hash;
7. writing-plans starts only after the 1.0.0 binding merges and its exact Spec digest
   is verified.
