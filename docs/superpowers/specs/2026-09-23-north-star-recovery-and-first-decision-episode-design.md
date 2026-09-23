---
schema_version: specification/v1
spec_version: 1.3.0
title: North-star recovery and first real Decision Episode proof
bet_id: BET-Y2Q2-T4-01
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-23'
last-reviewed: '2026-09-23'
implementation_authorized: false
value_indicator_policy: true
risk_level: L3
human_gate: true
type: ssot
---

# BET-Y2Q2-T4-01: North-star recovery and first real Decision Episode proof

## Decision and north star

The principal accepts this specification as the minimum governed container for
the active Goal whose only north star is:

> 织星是夏明星一个人的业务操作系统：把外部信号转化为他愿意署名的真实结果，并准确记住每次人工修订。

The three-year strategy remains the primary line. The digital-twin blueprint is
its subordinate target architecture. Mesh remains the only active SFOP `S`
dispatcher and OMO remains the only governance write control plane. This Spec
does not create a second ledger, dispatcher, operating system, ontology, or
top-level project.

## Current factual baseline

- `BET-Y2Q2-T5-03`, `BET-Y1Q4-T10-155`, and `BET-Y1Q4-T10-156` are already
  delivery-accepted and must not be rebuilt.
- Claims Authority is `shadow-active`, authority epoch 1, effective v1, with
  instruction capability disabled.
- The authoritative store tip is sequence 2, receipt
  `sha256:a660e34c55467e631f38d97e17b4d2377281fc5fe73a94b6f33548dbabe1eab7`.
- Lifecycle Operation A is historical and non-repeatable. Operation B is
  protocol-blocked; Operation C has not started.
- The conflicting approval records for the old lifecycle draft are preserved
  as non-authoritative evidence and are not consumable.
- The authoritative OMO causal Event Ledger observes zero Personal Episodes and
  no qualifying week. Parallel JSONL contains 30 v2 rows, but those rows are not
  ledger-bound and therefore do not prove personal value. Engineering or
  governance work is not a substitute for personal business value.
- The 30 v2 rows are a single batch, not 30 observed business episodes. They
  were appended from `2026-09-23T06:22:10Z` through
  `2026-09-23T06:26:42Z`, use consecutive run ids
  `val-win-20260923-01` through `val-win-20260923-30`, and all declare
  `accepted`, `review_duration_seconds=45`, and
  `estimated_time_saved_seconds=240`. Their source scene outcomes explicitly
  say `value-window human adjudication batch`. The authoritative scene
  execution database contains zero matching runs, and the Event Ledger
  contains zero matching correlation ids or payload references. These rows and
  their adjacent v1 mirrors are preserved as historical advisory records but
  count as zero real-value samples.
- The value-window SSH signature is cryptographically valid only for the six
  canonical attestation fields. The 30-sample count, baseline, acceptance
  percentage, revision burden, and window are outside the signed bytes. Its
  `episode_id` and `signal_event_id` do not exist in the Event Ledger. The
  attestation is therefore a valid human signature over an unbound statement,
  not proof of the claimed value window.
- Merge `c7e1fdf09cb1edcd7e8bd26f3b100c76139b3628` preserved a closeout retro
  whose own text says there is no complete `EpisodeClosed` sample and no
  four-consecutive-week proof. That merge remains historical evidence, but its
  `done`/`PROVEN` projection is non-authoritative for this Spec's completion
  contract and must be corrected rather than deleted.

## Authorized one-time stdio recovery bootstrap

The principal granted operation
`north-star-claims-stdio-loader-recovery-bootstrap-v1` at most once under
decision
`principal-decision-ee7eceb1-4faa-42b9-b022-aac14204b6f7`, expiring
`2026-09-27T16:00:00Z`. It is a repository repair, not a Claims lifecycle
operation.

The bootstrap is bound to `origin/main`
`c7e1fdf09cb1edcd7e8bd26f3b100c76139b3628`, managed clone attempt
`north-star-cp-repair-20260923e`, authority epoch 1, store sequence 2, and last
receipt `sha256:a660e34c55467e631f38d97e17b4d2377281fc5fe73a94b6f33548dbabe1eab7`.
Only these repository paths may change:

- `bin/agent-workflow.py`
- `tests/test_agent_workflow.py`
- this Spec
- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_truth/governance-evidence/waiver-2026-09-23-north-star-claims-stdio-loader-recovery.md`

The loader must execute the exact descriptor-bound broker in a private package
namespace rooted at the pinned `projects/omo/src/omo`, preserve package-relative
imports without consulting caller `sys.path` or the public `omo` module cache,
verify loaded file paths, and purge partial private modules on failure. Missing
or malformed code remains typed and fail-closed.

Required proof is:

1. focused loader tests cover real relative imports, poisoned module caches,
   missing code, malformed code, and partial-module cleanup;
2. the complete `tests/test_agent_workflow.py` file passes;
3. canonical stdio status byte-semantically equals direct broker status on the
   bound production store;
4. store, high-water, activation-witness, and historical receipt hashes remain
   unchanged;
5. no Claims Authority verb is invoked.

The only authorized external effects are one ordinary non-force branch push,
one pull-request creation or update, and one ordinary merge after required
checks pass and both remote OID reads match. Force, `--no-verify`, unknown
outcome retry, legacy publication, instruction enablement, and historical
receipt mutation remain forbidden.

## Delegated ledger-bound value projection repair

Under the principal's bounded delegation for ordinary blocking and screening
decisions through `2026-09-28T00:00:00+08:00`, delegated decision
`delegated-decision-e53dc119-fe70-44e3-a440-a5ab092d347b` authorizes operation
`north-star-ledger-bound-value-projection-repair-v1` at most once. The decision
was recorded at `2026-09-23T13:45:56Z` and expires at
`2026-09-27T16:00:00Z`. This is a fail-closed projection repair and does not
grant any Claims Authority operation or any external business action.

The repair may modify only:

- this Spec;
- `docs/plans/3y-bet-ledger.yaml`;
- `bin/panorama/panel-collect.py`;
- `bin/panorama/panorama-collect.py`;
- `tests/unit/test_panel_collect.py`;
- `tests/unit/test_panorama_objective_coverage.py`.

Post-acceptance audit proved that this six-path operation is insufficient. The
current `PersonalEpisodeService.observe_principal` can return `passed` for a
chain that lacks per-Episode role-context assignment, responsibility linkage,
pre-mandate human adjudication, distinct outcome observation, adjudication
recording, memory candidacy, and closure. Projecting that result would merely
replace one false-positive source with another. Operation
`north-star-ledger-bound-value-projection-repair-v1` is therefore superseded
before execution and must never be consumed, retried, or reinterpreted as
implementation authority.

The authoritative personal-value verdict must come from the read-only
`bin/bc-os/north_star_meter_v2.py` projection over the OMO causal Event Ledger,
including chain integrity and `PersonalEpisodeService` qualification. Existing
JSONL, revision-baseline, and signed-attestation inputs remain advisory display
data only and cannot independently flip `panel_value.state`, `BUSINESS_VALUE`,
or `value_proof` to proven. Missing code, ledger, principal binding, integrity,
or observer output fails closed to `not_proven` or `unprovable` with a typed
reason.

Required tests cover:

1. thirty legacy JSONL rows plus a valid legacy attestation remain
   `not_proven` when the ledger observation is not ready;
2. only a chain-verified ledger observation with personal-value status
   `passed` can project `proven`;
3. unavailable or malformed ledger observation fails closed;
4. objective coverage refuses an unbound caller-supplied `panel_value.state`;
5. existing advisory metrics and lowercase deployment-safe state semantics are
   preserved.

The only external repository effects are one ordinary non-force branch push,
one pull-request creation or update, and one ordinary merge after required
checks are green and two remote-main OID reads match. The operation stops on
scope drift, unexpected file changes, unknown remote outcome, ledger mutation,
Claims mutation, or concurrent writer conflict. It never uses force,
`--no-verify`, or automatic retry.

## Delegated fail-closed design correction

Under the same bounded delegation, delegated decision
`delegated-decision-5d0751c9-f824-4902-8b0c-cbaa646ed7ef`, recorded at
`2026-09-23T15:57:48Z` and expiring at `2026-09-27T16:00:00Z`, authorizes
operation `north-star-ledger-truth-contract-v2` at most once. This is a
repository-only design correction. It may modify only this Spec and
`docs/plans/3y-bet-ledger.yaml`, with one ordinary non-force branch push, one
pull-request creation or update, and one ordinary merge after required checks
are green and two remote-main OID reads match.

This design operation does not authorize runtime writes, Event Ledger writes,
Claims verbs, external business actions, child-repository publication, or the
implementation surfaces below. It stops on any unexpected changed path,
remote drift, unknown remote outcome, active overlapping lease, or failed
required check and is never automatically retried.

The successor implementation must be split into independently fenced,
child-first transactions. Each transaction needs a fresh base OID, exact path
claims, patch digest, process identity, tests, rollback, one-shot repository
effects, and a root gitlink update only after the child commit is reachable:

1. **OMO truth writer and observer**
   - `projects/omo/src/omo/personal_episode.py`
   - `projects/omo/src/omo/personal_episode_helpers.py`
   - `projects/omo/src/omo/omo_adjudication.py`
   - `projects/omo/tests/test_personal_episode.py`
   - `projects/omo/tests/test_omo_adjudication.py`
2. **Cockpit command delegation**
   - `projects/cockpit/src/cockpit/web/api_decision_inbox.py`
   - `projects/cockpit/src/cockpit/web/api_workflow_mesh_operations.py`
   - `projects/cockpit/src/cockpit/tests/test_api_decision_inbox.py`
   - `projects/cockpit/src/cockpit/tests/test_api_workflow_mesh_operations.py`
3. **Root meter, legacy demotion, and honest projection**
   - `bin/bc-os/north_star_meter_v2.py`
   - `bin/ssot/scene-outcome-recorder.py`
   - `bin/ssot/value-recorder.py`
   - `bin/panorama/panel-collect.py`
   - `bin/panorama/panorama-collect.py`
   - `tests/test_north_star_meter_v2.py`
   - `tests/test_scene_outcome_value_v2_bridge.py`
   - `tests/unit/test_panel_collect.py`
   - `tests/unit/test_panorama_objective_coverage.py`
   - the two child gitlinks, this Spec, and the BET ledger

The listed paths are a proposed implementation envelope, not authorization to
edit them under the design operation.

### Canonical Episode truth contract

The OMO Event Ledger is the only value-truth writer. A qualifying Episode must
contain one causally ordered, principal-bound chain with stable ids and no
cross-principal or cross-Episode joins:

`SignalObserved → RoleContextAssigned → ResponsibilityLinked → DecisionProposed → HumanAdjudication → MandateGranted → ActionSucceeded → EvidenceRecorded → OutcomeObserved → AdjudicationRecorded → MemoryCandidateProposed → EpisodeClosed`.

The existing event names may be versioned, but their semantics and ordering
are mandatory. Existing `Episode.Decision.v1`, `Evidence.LocalDraft.v1`, and
`Outcome.Human.v1` rows do not become qualifying merely because equivalent
fields occur in their envelopes. `EpisodeClosed` must name the exact terminal
outcome, adjudication, evidence, mandate, and memory-candidate event ids and
must be idempotent. Reject, defer, and ignore may close an Episode for honest
denominator accounting but never count as an accepted delegated result.

Human adjudication that authorizes a mandate is distinct from the later human
adjudication of the observed outcome. Both must be explicit Event Ledger
events. An action without a prior valid, revocable mandate is non-qualifying.
An edit without the original candidate digest, revised digest, and concrete
changed-field receipt is non-qualifying. Missing burden fields or
`review_duration_seconds >= estimated_time_saved_seconds` is non-qualifying.

### Observer and meter contract

`PersonalEpisodeService.observe_principal` must validate the complete chain,
event ordering, producer/principal/episode identity, causation links,
idempotency, mandate state at action time, revision receipt, closure bindings,
and Ledger hash integrity before incrementing any qualifying counter. It must
return typed gap codes for every missing or conflicting leg. Thirty incomplete
chains and four synthetic timestamps remain `not_ready`.

`north_star_meter_v2.py` remains read-only. It may project `proven` only when
the observer reports a complete-chain schema version, all counted Episode ids
are closed and provenance-complete, at least 30 qualifying real Episodes exist,
and four consecutive natural weeks each contain at least three
principal-accepted outcomes. Caller-supplied booleans, legacy JSONL,
attestations, scene-card existence, run-id strings, or engineering receipts can
never elevate the verdict.

### Legacy convergence contract

`.omo/_delivery/outcomes/adjudications.jsonl`,
`.omo/_delivery/ingress/value-evidence.jsonl`, scene outcomes, and MOS
`decision_outcome` are legacy/advisory surfaces. During migration they remain
append-only historical evidence, but they are not co-equal truth writers. New
canonical adjudications and decision outcomes originate in the Event Ledger;
JSONL and MOS become rebuildable projections with source event ids and
projection checkpoints. Projection failure may degrade display or learning but
must not roll back, duplicate, or hide the canonical event.

### Required negative proofs

The implementation is incomplete unless tests prove all of these fail closed:

- the existing 30-row batch plus its valid SSH signature counts as zero;
- thirty partial chains that satisfy the old observer remain `not_ready`;
- missing, reordered, duplicated, cross-principal, cross-Episode, or
  mismatched-causation legs never qualify;
- mandate-after-action, revoked mandate, unbound authority receipt, replay
  conflict, missing revision diff, missing burden, and burden greater than or
  equal to savings never qualify;
- JSONL, MOS, panel inputs, or an attestation cannot flip value independently;
- observer and meter are read-only and byte-preserve the source Ledger;
- an interrupted projection is rebuildable from Ledger without a second truth
  write or altered historical receipt.

## Concurrent-writer operating contract

Concurrent activity in the canonical Workspace is expected during this BET and
is handled without taking over another writer:

1. `/Users/xiamingxing/Workspace` is a read-only runtime-fact source for this
   writer. No edit, reset, clean, checkout, rebase, commit, or stash is allowed
   there.
2. All repository changes use one isolated managed worktree and one writer.
3. Every commit, push, pull-request update, and merge is fenced by two reads of
   the remote `refs/heads/main` OID.
4. If the remote OID changes, the writer stops the pending external effect,
   verifies the isolated worktree is clean or has a fully enumerated expected
   diff, and replays only that expected diff on the new base. No blind rebase,
   cherry-pick, force push, or automatic retry is allowed.
5. Canonical dirty files and other writers' processes remain untouched. A
   branch-occupancy or path conflict is evidence to reroute or serialize the
   local transaction, not authority to kill or seize the other writer.
6. The principal delegated decisions about ordinary blocking and screening
   conditions through `2026-09-28T00:00:00+08:00`. This delegation does not
   supply the operation-specific fields required for any Claims lifecycle
   operation and does not authorize Restricted-data egress.
7. Run status and write ownership are separate facts. An expired lease removes
   write authority but does not erase, close, or rewrite the old run. A
   successor may proceed only after proving the old effect process is absent,
   binding a new base OID and process identity, and acquiring non-overlapping
   exact paths. An overlapping path remains blocked until the old lease is
   expired and the successor explicitly records the predecessor run id.
8. A stale run is never closed through an API that would invoke forbidden
   Claims verbs. It remains preserved as stale/orphaned evidence until an
   applicable reconciliation operation exists.

## Phase 0: factual and authorization integrity

Required result:

- preserve the sequence 1 and sequence 2 receipt chain byte-for-byte;
- classify the conflicting approval records as non-authoritative evidence;
- prove all effects that occurred and prove zero legacy publication effect;
- mark the abandoned run/lock as stale legacy without inventing success;
- recompute the bound WorkPacket with the canonical ECOS compiler;
- maintain a successor authorization draft bound to authority epoch 1,
  sequence 2, the current receipt digest, current `origin/main`, and the real
  protocol capability.

No new Claims operation is authorized by this Spec.

## Phase 1: one control plane and honest projections

Required result:

- A1 through A9, SFOP, the workflow observer, managed code-root health, and the
  single-control-plane projection are recomputed from one fresh `origin/main`;
- A4 reads scheduler registry and installed runtime facts from the intended
  roots, rather than from a stale canonical checkout;
- A9 consumes a complete ASD five-panel snapshot and a fresh cockpit source
  projection; partial evidence never becomes PASS;
- Mesh is the only `S` holder, OMO is the only governance writer, resident is a
  projection, north-star components only meter outcomes, and MOS only governs
  memory;
- active and stale locks are attributed to a live process or explicitly
  preserved as legacy.

Read-only external checks may be re-run only as a new deliberate observation;
no unknown external-effect outcome may be automatically retried.

## Phase 2: strategy-to-runtime convergence

The following chain must map one-to-one across strategy, architecture, runtime,
and the BET ledger:

`Vision → Role responsibility → Decision Episode → Mandate → Action → Evidence → Outcome → Human adjudication → Memory/Evolution`.

MOF may act only as a Control Compiler. Every promoted model needs a named
consumer, compiled artifact, test, accountable owner, M0 use evidence, and an
exit or rollback path. Dynamic counts and health facts remain projections and
must not be copied into strategy documents.

## Phase 3: first real Golden Scenario

The first Golden Scenario begins with a real personal work signal, not a
governance task or engineering pull request:

`SignalObserved → RoleContextAssigned → ResponsibilityLinked → DecisionProposed → HumanAdjudication → MandateGranted → Action/Evidence → OutcomeObserved → AdjudicationRecorded → MemoryCandidate → EpisodeClosed`.

Acceptance requires all of the following:

- Cockpit is the only human entry point.
- Every external action is covered by a valid, revocable Mandate.
- Accept, edit, reject, and ignore decisions retain the original signal,
  concrete human revision diff, outcome, cost, and time burden.
- `decision_outcome` is the common fact for evaluation, delegation, memory, and
  evolution.
- At least 30 qualifying v2 real records exist.
- Four consecutive weeks each contain at least three principal-accepted,
  verifiable delegated results.
- Human approval and correction time is less than system time saved; otherwise
  the scenario is degraded or stopped.

No fixture, backfill, gate result, test, code volume, commit, or agent count can
qualify as value evidence.

## Phase 4: controlled evolution

Only after the Golden Scenario establishes a real outcome baseline may Policy,
Skill, Prompt, Model Route, Journey, Connector, or Agent Cell changes become
evolution candidates. Every candidate requires historical Episode replay,
sandbox, shadow, limited canary, human adjudication, and rollback. Family,
organization, physical multi-host, and generic-agent-platform expansion remain
out of scope.

## Claims boundary

This Spec does not authorize `observe-claim`, `begin-claim-mutation`,
`settle-claim-mutation`, legacy fence issuance, publication, instruction
capability, or promotion above shadow. Each future Claims operation requires a
fresh successor draft plus the principal's exact operation list,
`principal_decision_id`, `decision_timestamp_utc`,
`decision_expires_at_utc`, and verbatim authorization text.

The blocked v1-allow versus managed-clone-v2 fence design may change only
through an accepted Spec addendum with success, failure, unknown-outcome,
replay, and rollback tests plus a newly compiled WorkPacket.

## Completion evidence

The BET remains non-terminal until every axis is independently proven:

- Engineering: target tests, integration gates, failure/recovery paths,
  required checks, and a reachable merged commit.
- Operational: fresh replay, live canary, cleanup, receipts, and reconstructible
  projections from authoritative sources.
- Value: 30 qualifying real records, four consecutive qualifying weeks, signed
  principal adjudications, revision diffs, rejection evidence, and time-burden
  evidence.

If any axis is missing, it must remain `NOT_PROVEN`, `PARTIAL`, `BLOCKED`, or
`UNPROVABLE`; delivery status cannot substitute for value.

The #4249 closeout cannot terminate this BET because its own retained evidence
marks the mandatory complete Episode and four-week criteria false. Until those
criteria are genuinely observed, the Ledger status remains non-terminal and
the value axis remains `NOT_PROVEN`.

## Rollback and stop conditions

Repository changes are reverted by ordinary non-force PR rollback. Runtime
projections are regenerated from their sources. Historical Claims receipts and
human records are never rewritten.

Stop the pending effect on any unauthorized external action, receipt/hash
anomaly, unknown remote outcome, unexplained origin drift, Restricted-data
egress, unbound Claims request, missing real-value provenance, or human burden
greater than benefit. Preserve evidence and continue only through an applicable
principal decision or already-delegated bounded concurrency policy.
