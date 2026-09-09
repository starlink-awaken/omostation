---
schema_version: specification/v1
spec_version: 1.1.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-09
last-reviewed: 2026-09-09
title: A2 Resident Status Purity Truth Recovery
bet_id: BET-Y1Q4-T10-144
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: true
---

# A2 Resident Status Purity Truth Recovery

## 1. Status and authority

This document is the accepted contract for `BET-Y1Q4-T10-144`. Version 1.0.0
authorized only the child RED-to-GREEN implementation in §10; that immutable
stage closed after child PR #152 merged. Under the Principal's time-bounded
delegated authority, version 1.1.0 authorizes only the fresh WP-A2-ROOT gitlink
integration in §10. The four child source/test paths are revoked for new runs,
not appended to the root scope. Version 1.1.0 does not authorize a host canary,
recovery command, service/database/process mutation, completion transition or
value claim.

The approved Documents proposal input is:

- document:
  `2026-09-09-A2-Resident-Status-Purity恢复BET提案-v1.md`
- SHA-256:
  `acefb7211a66b7cbbe7506c70c27e74108fcd833e55922802d7e439e48123205`
- approval scope: all architecture decisions and authorization boundaries in
  that proposal. The original bootstrap transaction was limited to a
  draft/unbound Spec and waiver. The later temporary delegation recorded in the
  binding waiver authorizes this independently reviewed acceptance and the
  bounded child implementation.

## 2. Verified baseline

The design baseline is root main
`e1d36dc8f36b2acdf1a8beea4c289a16d9aae045`, whose `projects/omo` gitlink is
`db7217913dc95f727f26d66b9f7df5675404077b`. The OMO child gitlink is reachable
and its relevant tree matches the proposal's inspected child baseline.

The 1.1.0 binding-replacement baseline is root main
`0941c21d5eca3580af928d6a930afded8645f676`, whose root gitlink still points to
`db7217913dc95f727f26d66b9f7df5675404077b`. Authoritative OMO child main is
`edf2301e9344cbfbeb90599f405acb8cc29d9301`: it contains the prerequisite RLM
compatibility recovery `e2a75531b5f1926d56b3badd9c43b86c22ba864c` and merged
A2 child PR #152. The reviewed four-path content aggregate is
`012a978e3a4716ea3d85fb9f05517ac15a2ee147d7bb905e1327f599db94f42b`.

The current execution chain is:

```text
resident status
  -> status.snapshot()
     -> status._ledger_snapshot()
        -> dynamic import omo.resident.ledger_check.check_and_recover
           -> lock_age_seconds()                 read-only observation
           -> wal_checkpoint(TRUNCATE)            SQLite mutation
           -> maybe_kill_zombie_holders()
              -> CPU sampling and time.sleep()
              -> os.kill(pid, SIGTERM)            process mutation
        -> status._probe_ledger_once()            read-only chain probe
        -> retry loop and time.sleep() on busy
```

This makes the nominal status query conditionally capable of database and
process mutation. The risk is present even if an ordinary unlocked invocation
happens not to exercise the side-effect branch.

Current tests prove that `_probe_ledger_once()` uses `mode=ro`, that explicit
recovery has a kill circuit breaker, and that internal probes can run
concurrently. They do not prove that the complete status snapshot is pure.
`test_resident_status.py` currently patches the real dynamic symbol
`omo.resident.ledger_check.check_and_recover` and explicitly expects retry and
sleep behavior, so current-tree drift is directly test-visible.

## 3. Historical truth boundary

The following accepted specifications remain authoritative source inputs:

| Source | SHA-256 | Continuing contract |
|---|---|---|
| `2026-08-29-resident-ledger-read-status-design.md` | `cba73e50cad31af43d221b06613f2f436db54368ec7e63dcd2739bcf290de748` | Status never checkpoints, writes, signals or changes launchd state. |
| `2026-09-06-resident-readonly-zero-lock-wal-robustness.md` | `0085ad0bdfaca904efb3a54ea00f96ec2ee123742ebe1d9b920922721f7c46c9` | Status is a true read-only observation and remains bounded under concurrent WAL writes. |

`BET-Y1Q3-T10-48` and `BET-Y1Q4-T10-126` remain `done`. This recovery must not
rewrite, reopen or delete their completion/value evidence. The fact that the
current tree violates part of their accepted contract is new recovery work,
not authority to rewrite history.

## 4. Decision: strict Command-Query Separation

Adopt strict Command-Query Separation for the resident ledger surface:

```text
Query lane
  resident status -> check_lock_state_only + _probe_ledger_once
  effect class     -> read-only observation

Command lane
  resident-recover / daemon / heartbeat
    -> recover_ledger_with_wal_checkpoint
    -> check_and_recover
  effect class     -> explicit governed mutation
```

Status may report a degraded condition. Status may never attempt to repair the
condition it reports.

## 5. Invariants

| ID | Invariant |
|---|---|
| A2-I-01 | `resident status` is a Query and has zero database, process, service or host mutation paths. |
| A2-I-02 | A busy, locked, stale, I/O-error or unknown observation fails truthfully; it never triggers recovery. |
| A2-I-03 | The complete status ledger path performs no sleep or retry. |
| A2-I-04 | All SQLite connections opened by the Query lane use a URI containing `mode=ro` with `uri=True`. |
| A2-I-05 | Checkpoint, holder discovery, CPU sampling, signal delivery and ordinary write-capable SQLite connections are unreachable from status. |
| A2-I-06 | Explicit recovery remains available only through a visibly named Command boundary. |
| A2-I-07 | Daemon and heartbeat recovery behavior is preserved; A2 does not weaken or redesign it. |
| A2-I-08 | Missing ledger remains a non-fatal cold-start observation. |
| A2-I-09 | A test green is hermetic engineering evidence, not host operational or personal-value evidence. |
| A2-I-10 | Child code lands first; root integration changes only the `projects/omo` gitlink afterward. |

## 6. Query contract

### 6.1 `check_lock_state_only`

The OMO child must add or restore this pure helper in `ledger_check.py`:

```python
check_lock_state_only(ledger: Path) -> dict[str, Any]
```

Its normalized result must carry at least:

```text
ok: boolean
state: missing | unlocked | locked | busy | io_error | unknown
lock_age_seconds: integer | null
observation_mode: read_only
recovery_performed: false
detail: string
```

The helper contract is:

1. If the ledger does not exist, return `state=missing` without opening SQLite.
2. For an existing ledger, use only `file:<ledger>?mode=ro`, `uri=True`, and a
   bounded connection timeout.
3. It may inspect read-only lock state and immutable filesystem metadata needed
   to classify the observation.
4. It must not call `wal_checkpoint`, `find_sqlite_holders`, `_cpu_pct`,
   `maybe_kill_zombie_holders`, `os.kill`, `time.sleep`, or any recovery alias.
5. It must not open a path-style/non-URI SQLite connection or execute a
   mutating PRAGMA.
6. Expected contention and I/O outcomes return typed results; they are not
   converted into an untyped exception or an implied successful recovery.
7. The result must always state `observation_mode=read_only` and
   `recovery_performed=false`.

The implementation may reuse the existing sidecar-age calculation only if it
does not broaden the Query lane into process discovery or mutation.

### 6.2 `_ledger_snapshot`

`status._ledger_snapshot()` must implement the following bounded flow:

1. A missing ledger returns the existing cold-start non-fatal result and does
   not open SQLite.
2. An existing ledger invokes `check_lock_state_only(LEDGER)` exactly once.
3. It invokes `_probe_ledger_once()` exactly once.
4. If either observation is non-OK, it immediately returns truthful degraded
   output with the first attributable reason.
5. It performs no retry and no sleep.
6. It does not import, resolve or call `check_and_recover` or
   `recover_ledger_with_wal_checkpoint`.

`_probe_ledger_once()` remains a read-only hash-chain observation. A later
optimization may bound the number of rows it reads, but that is outside this
recovery unless a real acceptance test proves it is required for termination.

### 6.3 Output compatibility

The outer `resident.status` JSON envelope and existing component names remain
compatible. `components.ledger.lock_monitor` may retain compatibility fields,
but it must not imply a mutation was attempted:

```text
locked: boolean | null
checkpoint: null
recovery: null
detail: truthful observation detail
state: normalized observation state
observation_mode: read_only
recovery_performed: false
```

The top-level health remains `degraded` when the ledger observation is not OK.
No state may be labelled `recovered` because status itself repaired it.

## 7. Command contract

The OMO child must expose the explicit mutation name:

```python
recover_ledger_with_wal_checkpoint = check_and_recover
```

This alias makes the effect boundary visible without changing the current
recovery algorithm. It may be called only from an explicit recovery command or
the existing daemon/heartbeat mutation journeys.

A2 must not change:

- WAL checkpoint semantics;
- stale-lock threshold;
- checkpoint failure counter or budget;
- holder discovery;
- CPU sampling or zombie classification;
- kill threshold or signal;
- daemon tick scheduling;
- heartbeat publication behavior.

If those paths require repair, they need a separate accepted Spec and
WorkPacket.

## 8. Failure semantics

| Observation | Query result | Permitted action |
|---|---|---|
| Ledger missing | non-fatal cold start | report only |
| Ledger unlocked and chain valid | healthy ledger component | report only |
| Lock observed within or beyond the old recovery threshold | locked/degraded | report only |
| SQLite reports locked or busy | busy/degraded | report once; no retry |
| Read-only connection I/O error | io_error/degraded | report only |
| Broken event hash chain | degraded with sequence/detail | report only |
| Lock age cannot be established | unknown/degraded unless unlocked is directly proven | report only |
| Unexpected exception | bounded degraded response or existing CLI non-zero contract | no mutation and no silent success |

## 9. A3 dependency amendment

A2 must not depend on `BET-Y1Q4-T10-142` becoming `done`. The Principal has
explicitly required that T10-142 remain `candidate/evaluating`, with operational
and value status `NOT_PROVEN`.

A2 instead consumes the following non-BET engineering prerequisites:

| Receipt | Exact value |
|---|---|
| A3 binding merge | `6876869233ef595877406510cccbdeacb757f478` |
| A3 implementation merge | `5fb98bd3f4a342b77c5a0560eaf13bc02ed5d893` |
| A3 accepted Spec SHA-256 | `e097950a5979c2a7b05edb75d8e432171a4050e8cf6a259f3053a308d9d639a1` |
| A3 merged test blob | `9e4774f590c3b1e5007508ca46534ad17c27e735` |
| A3 canonical focused result | `6/6` |

These receipts prove a managed-Python engineering prerequisite only. They do
not prove A3 operational/value completion and do not alter the Ledger.

## 10. Accepted binding and sequential WorkPackets

The original accepted-binding transaction reread the execution-time remote
Ledger, open PRs and remote branches. `BET-Y1Q4-T10-144` was absent and
collision-free after Claims Bridge parent `BET-Y1Q4-T10-143` merged. Version
1.0.0 bound the child stage only.

The version 1.1.0 binding-replacement transaction is limited to:

```text
docs/superpowers/specs/2026-09-09-a2-resident-status-purity-truth-recovery-design.md
docs/plans/3y-bet-ledger.yaml
.omo/_truth/governance-evidence/waiver-2026-09-10-a2-root-binding-amendment.md
```

The Ledger compiler generates one WorkPacket per BET and copies the BET's
complete `write_surfaces` list into that packet. It has no stage-aware path
fence. Therefore child and root paths must never be exposed as a union. The
sequential binding state is:

1. version 1.0.0 exposed only the four WP-A2-CHILD paths below;
2. its final child run is closed and PR #152 is merged as authoritative child
   main `edf2301e9344cbfbeb90599f405acb8cc29d9301` with required and post-merge
   child CI green;
3. version 1.1.0 replaces all four child paths with the single `projects/omo`
   gitlink path; it does not append or union the scopes;
4. the root run must be fresh and bind the newly generated immutable
   WorkPacket hash. Closed 1.0.0 child runs retain their original hash and
   evidence;
5. the root pointer may target `edf2301e9344cbfbeb90599f405acb8cc29d9301`
   or a directly re-proven authoritative child-main descendant containing the
   reviewed four objects;
6. the host canary remains a third, post-root operational transaction and is
   not authorized by version 1.1.0.

`BET-Y1Q4-T10-144` has no Ledger dependency on T10-142 or T10-143. A3 is
consumed only through the exact engineering receipts in §9. Claims Bridge R0
enforcement affects the normal managed-clone publication route, not the A2
engineering dependency graph.

### WP-A2-CHILD — OMO CQS implementation

```text
projects/omo/src/omo/resident/status.py
projects/omo/src/omo/resident/ledger_check.py
projects/omo/tests/unit/test_resident_status.py
projects/omo/tests/unit/test_ledger_check.py
```

The child repository owned RED-to-GREEN implementation and its own PR. This
historical stage was authorized only by version 1.0.0 and is now delivered and
closed. Its paths are not authorized for a new 1.1.0 run.

### WP-A2-ROOT — authoritative child integration

```text
projects/omo
```

This is the only implementation stage authorized by version 1.1.0. The active
binding replaces the child write set with exactly `projects/omo`; a fresh root
run may advance only that mode-160000 gitlink to the already merged,
authoritative child-main commit or a verified child-main successor containing
it. The root PR must not carry source code, tests, Ledger/Spec changes, host
evidence or unrelated gitlinks.

## 11. RED-to-GREEN matrix

| ID | Current/RED proof | Required GREEN proof |
|---|---|---|
| A2-RG-01 | With an existing test ledger, patch the real runtime symbol `omo.resident.ledger_check.check_and_recover`; current `_ledger_snapshot()` invokes the sentinel. | The same sentinel is invoked zero times by `_ledger_snapshot()` and `snapshot()`. |
| A2-RG-02 | Existing busy fixtures prove up to three probes and patched sleep. | Busy performs one lock observation, one chain probe, zero sleep and returns degraded. |
| A2-RG-03 | A stale lock can reach `wal_checkpoint(TRUNCATE)`. | Fail-fast checkpoint sentinel remains untouched by every status scenario. |
| A2-RG-04 | Repeated checkpoint failure can reach holder discovery, CPU sampling and `os.kill`. | Fail-fast holder/CPU/kill sentinels remain untouched by status. |
| A2-RG-05 | A non-URI SQLite connection is available in the recovery module. | A tracking connector proves every Query-lane connection contains `mode=ro` and `uri=True`. |
| A2-RG-06 | `check_lock_state_only` is absent. | It returns deterministic typed results for missing, unlocked, locked, busy, I/O error and unknown. |
| A2-RG-07 | Existing tests cover concurrent internal probes, not complete snapshots. | 100 concurrent complete snapshots are JSON-serializable, terminate within the declared budget and make zero side-effect calls. |
| A2-RG-08 | Explicit recovery behavior exists under `check_and_recover`. | The explicit alias exists and existing checkpoint/circuit-breaker tests remain green. |
| A2-RG-09 | Daemon and heartbeat dynamically import `check_and_recover`. | Their explicit mutation journeys retain focused regression coverage and behavior. |

The RED test must patch
`omo.resident.ledger_check.check_and_recover`. Patching a nonexistent
`status.check_and_recover` attribute is invalid evidence.

## 12. Acceptance criteria

### 12.1 Hermetic engineering

1. The RED matrix fails for the current side-effecting status path before the
   implementation change and passes afterward.
2. Missing, unlocked, locked, busy, I/O-error, broken-chain and unknown cases
   all return truthful bounded results with zero side effects.
3. Recovery, checkpoint, holder discovery, CPU sampling, kill, sleep and
   write-capable SQLite connection invocation counts are all zero for the full
   status surface.
4. One hundred concurrent complete snapshots are JSON-serializable, terminate
   within the declared test budget, and cause no side effect.
5. Explicit recovery tests, daemon/heartbeat focused tests, OMO focused/full
   tests and lint all pass.

### 12.2 Child delivery

1. The child diff is limited to the four WP-A2-CHILD paths.
2. The accepted Spec digest and WorkPacket source digest match the binding.
3. Child required checks pass.
4. The merged child commit is reachable from authoritative child main.
5. Post-merge child objects match the reviewed source and tests.

### 12.3 Root integration

1. The root diff changes only `projects/omo` as a mode-160000 gitlink.
2. The gitlink points to the accepted child merge or a child-main successor
   containing it.
3. Full recursive checkout, reachability, root GaC and required PR contexts
   pass against the final tree.
4. Post-merge root main is reread and the gitlink is verified again.

### 12.4 Host operational canary

Only after child and root integration are merged, run a read-only production
canary:

- 100/100 `resident status` invocations return parseable output and terminate
  within the declared budget;
- resident/daemon PID and launch identity are unchanged before and after;
- no recovery, checkpoint, signal or restart event is observed;
- background daemon WAL writes are allowed, so raw database-byte equality is
  not used as a false purity test;
- absent services or insufficient logs produce `UNPROVABLE`, not a fixture-based
  operational PASS.

This canary does not authorize `resident-recover`, `kill`, `restart`,
`launchctl`, database repair or host configuration change.

## 13. Evidence and value boundary

Evidence must remain layered:

```text
test/lint green
  != child merge/reachability
  != root final-tree integration
  != host operational proof
  != personal value proof
```

This design and its future implementation use
`value_indicator_policy=false`. Engineering evidence must never be counted as a
personal value indicator. No status may advance to `done`, and no operational
or value state may advance from `NOT_PROVEN`, without its own direct evidence
and authorized Ledger transition.

## 14. Rollback

- Before child merge: close the run, release locks and retain the rejected
  artifact as evidence; do not publish partial work.
- After child merge but before root integration: revert the child through an
  ordinary reviewed child PR; root remains unchanged.
- After root integration: revert root gitlink through a separate root PR, then
  revert child code if required.
- Output additions must be backward compatible; rollback must preserve old
  consumer-readable keys.
- No rollback step may delete WAL files, repair SQLite, kill a process or
  mutate service configuration.

## 15. Stop conditions

Stop and require a successor decision if:

- T10-142 must be falsely marked done to continue;
- the active 1.1.0 root WorkPacket needs any path outside `projects/omo`;
- status still sleeps, retries, checkpoints, discovers holders, samples CPU or
  signals a process;
- a RED test patches the wrong symbol or covers only `_probe_ledger_once`;
- checkpoint, kill thresholds, daemon scheduling or heartbeat semantics must
  change;
- child code and root gitlink would enter one repository commit/PR;
- a WorkPacket or Ledger revision exposes the four child paths and
  `projects/omo` together;
- a root run reuses the child run or starts before the child run is closed and
  child-main reachability is proven;
- the root gitlink is not an authoritative child-main descendant;
- a host canary would require recovery or runtime mutation;
- any accepted Spec, WorkPacket, required context or digest check fails.

## 16. Ordered rollout

1. Preserve the accepted 1.0.0 child binding and its closed immutable runs.
2. Preserve child PR #152 merge/reachability, exact objects and CI as the
   engineering prerequisite; do not copy them into completion/value evidence.
3. Merge this accepted 1.1.0 root-only binding replacement through normal
   required gates.
4. Start a fresh 1.1.0 root run and execute only the `projects/omo` pointer
   change.
5. After root merge, obtain a separate operation-specific authorization and
   run the read-only 100/100 operational canary.
6. Update only the evidence layer actually proven in a later transaction;
   never infer value or done.

## 17. Decision log

| Decision | Ruling | Reason |
|---|---|---|
| Status behavior | Pure Query | Observation must not repair or signal what it observes. |
| Busy handling | One observation, then degraded | Retrying a monitor amplifies contention and violates bounded purity. |
| Recovery availability | Preserve explicit Command alias | Purity must not remove legitimate, explicitly invoked recovery. |
| Historical BET truth | Preserve | Current-tree recovery does not rewrite prior evidence. |
| A3 prerequisite | Exact engineering receipts | T10-142 completion/value is neither true nor required. |
| Delivery topology | Child first, root last | Source authority and root integration authority are separate. |
| Mechanical scope | Version 1.1.0 replaces the delivered child scope with the sole root gitlink scope | The current compiler has no stage fence; a union would authorize child/root writes together. |
| Host proof | Post-merge read-only 100/100 | Hermetic tests cannot prove production execution identity. |
| Value | Excluded / NOT_PROVEN | Infrastructure purity is not a personal decision outcome. |
