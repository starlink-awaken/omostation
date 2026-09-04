---
schema_version: specification/v1
spec_version: 1.2.0
title: Family dashboard runtime-state and HITL writes Phase B
bet_id: BET-Y1Q3-T10-122
status: accepted
lifecycle: contract
owner: family-hub
created: 2026-08-30
last_updated: 2026-09-02
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Family dashboard runtime-state and HITL writes Phase B

## Context

T10-111 Phase A established `projects/family-hub/apps/dashboard` as the
canonical Git-owned dashboard source. Root main now points to the child
provenance correction, but operational ownership is still incomplete:

- `/Users/xiamingxing/Workspace/runtime/family-hub/dashboard` is absent;
- the legacy Documents app still contains six private manifests, seventeen
  generated JSON products, three legacy AI-summary cache files, `.next`, and
  `node_modules`;
- the six manifests occupy about 61 KiB and the generated state about 1.07 MiB;
- `.next` and `node_modules` together occupy about 842 MiB and are reproducible;
- no SQLite file exists in the legacy app;
- a fresh consumer audit finds 35 family-dashboard references, all historical
  `content-reference` rows inside Documents or `.next`; there are no active
  family-dashboard executors and no Documents writer;
- the imported dashboard already requires `FAMILY_DOCUMENTS_ROOT` and
  `FAMILY_DASHBOARD_STATE_ROOT`, writes generated/cache/task data only below the
  state root, and unconditionally disables direct Documents writes.

The authoritative architecture remains ADR-0441: Documents is the content
plane, Workspace owns execution/runtime/state, Cockpit is the human approval
surface, Agora is the BOS routing fabric, and OMO is the mutation authority.

## Goal

Complete Phase B without performing Phase C:

1. materialize the real dashboard runtime state beneath the Workspace runtime
   plane from read-only family Documents;
2. replace direct Documents mutations with proposal-only dashboard APIs;
3. make a Cockpit human approval execute exactly one CAS-bound family-hub
   transaction through the existing Agora BOS resolver;
4. produce durable OMO and runtime receipts with rollback evidence; and
5. prove the path on real read data and a separately confirmed reversible
   Documents canary.

## Non-goals

- No Cockpit domain-app contract cutover or removal of the legacy
  `family-dashboard-app` contract.
- No persistent production port, LaunchAgent, cron, Service Gateway lifecycle,
  or always-on dashboard process.
- No deletion, move, quarantine, or rewrite of the legacy app, its `app-data`,
  manifests, `.next`, `node_modules`, or credentials.
- No copying of `.next`, `node_modules`, browser auth, `.env.local`, provider
  credentials, raw Documents content, or legacy AI cache into active state.
- No restoration of the legacy git-backup route or any `git add/commit` behavior.
- No second proposal registry, dispatcher, approval queue, content database, or
  human entry point.
- No claim of Phase C completion, production availability, principal-bound
  value, old-app retirement, or Documents-wide physical purity.

## Alternatives

### A. Existing Cockpit HITL + Agora BOS + family-hub transaction owner — selected

Reuse `.omo/state/proposals`, Cockpit `/api/v1/proposals`, and
`resolve_bos_uri`. Add a canonical OMO proposal writer/receipt broker, one
declarative Agora internal route, and one family-hub transaction owner.

This preserves ownership: OMO records authority, Cockpit captures the human
decision, Agora routes, and family-hub understands the content operation.

### B. Extend generic `apply_truth_mutation` to write Documents — rejected

The current generic OMO apply path loads Workspace YAML and applies top-level
`set` fields. Teaching it arbitrary text semantics would couple the governance
kernel to a private content format and enlarge a high-risk primitive.

### C. Re-enable direct Next.js writes behind an environment flag — rejected

An environment flag is not approval. It would restore the legacy overwrite,
background auto-tag, swallowed-error, and parent-git backup risks while
bypassing Cockpit and OMO.

## Architecture

```text
Documents family content (read-only for build)
              |
              v
family-hub runtime planner -> staging A + staging B -> fresh-build parity
              |                         |                    |
              |                         v                    v
              |                 legacy-delta receipt -> atomic promote A
              |                                              |
              +----------------> Workspace/runtime/family-hub/dashboard

Dashboard write request
  -> Cockpit proposal ingress
  -> OMO .omo/state/proposals (ref + digests, no body)
  -> Human approves in Cockpit
  -> Agora bos://governance/hitl/execute/family_dashboard_document_write
  -> family-hub CAS transaction owner
  -> Documents atomic mutation or rollback
  -> Workspace runtime receipt + OMO HITL receipt
```

There is one execution path. The Dashboard process never opens a Documents
file for writing.

## Runtime-state contract

The canonical production root is supplied explicitly and resolves to:

```text
runtime/family-hub/dashboard/
  manifests/                 # six private YAML manifests, mode 0600
  generated/                 # rebuilt JSON products
  cache/                     # starts empty; new cache only
  proposals/<id>/payload     # mode 0600, body never enters .omo
  mutations/<id>/
    original                 # rollback bytes when a source existed
    prepared.json
    apply.json
    verify.json
    rollback.json            # only on rollback
  migration/
    plan.json
    receipt.json
    parity.json
```

When an interrupted or externally damaged target contains only an unbound,
partial runtime (that is, it has no `migration/plan.json`), the only additional
runtime surface is a sibling quarantine directory with the exact generated
name `runtime/family-hub/.dashboard.recovery-<source-fingerprint-prefix>-<partial-inventory-prefix>/`.
It is not an active runtime root, is never read by Dashboard, and remains
private-mode until a separately authorized cleanup action. No wildcarded
parent-directory write is permitted.

The active root must be outside Git and Documents, must not be a symlink, and
must not already contain unknown state. Every directory and file is created
with private modes. Receipts contain only relative paths, modes, byte counts,
digests, statuses, and error classes; they contain no body fragments.

### Migration transaction

1. **Plan:** inventory exactly six `data-manifest/*.yaml` files, the legacy
   generated JSON set, and the regular builder input closure beneath
   `_knowledge`, `_archive`, and `_control`; reject non-regular nodes,
   collisions, unreadable files, path escapes, insufficient disk, or source
   drift. The public plan stores only counts, relative-path digests, aggregate
   digests, sizes, and modes; it never stores document bodies or absolute
   private paths.
2. **Stage:** create two new sibling staging roots. Copy only the six manifests
   into each root; do not copy legacy generated data or cache into active state.
3. **Build:** run the pinned family-hub builders independently against staging A
   and staging B with the real family Documents root mounted read-only. Compute
   the private input-closure digest before build A, between the builds, and
   after build B; any change blocks promotion.
4. **Fresh-build parity:** require the two isolated builds to produce the same
   exact product set and equal normalized JSON digests after removing only the
   declared volatile fields. Missing, extra, malformed, nondeterministic, or
   schema-invalid products block promotion.
5. **Legacy delta:** compare staging A with legacy `app-data` and write an
   explicit per-product `equal` or `different` observation plus aggregate
   digests. A value difference does not block promotion because legacy
   `app-data` is a preserved derived snapshot, not content truth. A missing or
   malformed legacy product, product-set mismatch, or unreadable baseline still
   blocks. No waiver or hidden allowlist is introduced.
6. **Promote:** after input stability, fresh-build parity, required-product
   parsing, path verification, and legacy-delta recording pass, remove staging B
   and atomically rename staging A to the absent canonical root.
7. **Verify:** replay representative read journeys against the canonical state,
   prove the transaction-bound input digest and source fingerprints were
   unchanged, and write the final receipt.
8. **Rollback:** before Phase C, rollback removes only failed/new staging and
   target roots; it never edits the preserved legacy source.

### Partial runtime recovery amendment (2026-09-02)

Recovery is a narrow continuation of the migration transaction, not a second
builder, truth plane, or cleanup mechanism. It is available only when a target
is non-empty yet unbound: `migration/plan.json` must be absent. A target that
contains a bound plan is an existing canonical or otherwise governed state and
is rejected without movement.

1. **Preflight:** recompute the privacy-safe source plan and require its exact
   reviewed fingerprint. Reject source drift, a symlink, an empty target,
   unsafe nodes, an existing recovery sibling, or any target containing a bound
   plan.
2. **Inventory:** enumerate only regular partial-target files, recording their
   relative path, mode, byte count, and SHA-256 in a pathless aggregate digest.
   No body or absolute private path enters recovery evidence.
3. **Isolate atomically:** rename the entire partial target to the one exact
   sibling quarantine path derived from the approved source fingerprint and
   partial inventory digest. There is no delete, merge, or overwrite operation.
4. **Rebuild and compare:** call the ordinary absent-target migration path,
   then require the newly built `generated/tasks.json` digest to equal the
   preserved partial task digest. A mismatch is a recovery failure rather than
   a migration waiver.
5. **Commit or restore:** after full normal verification, write a private
   `migration/recovery.json` that names only fingerprints, inventory/task
   digests, and status. On any build, parity, comparison, or receipt failure,
   remove only the newly created target and atomically restore the quarantine
   directory to its original target name.

Recovery never writes Documents, never runs the real write canary, never
changes proposal/HITL semantics, and never authorizes removal of the preserved
partial sibling. It proves recoverability and runtime continuity only; Phase B
remains non-terminal until the separately gated canary and final evidence.

### Derived parity amendment (2026-09-01)

The first real materialization proved that the original legacy-equality gate
confused a derived snapshot with its source of truth. All builders completed,
but current Documents truth legitimately produced newer search, task, timeline,
and domain projections than the preserved legacy `app-data`. Rewriting that
snapshot would violate the Phase B non-goal, while silently accepting arbitrary
differences would destroy the parity guarantee.

The selected correction is therefore **deterministic double-build parity with
an explicit legacy-delta receipt**:

- Documents remains the immutable content authority during the transaction;
- family-hub remains the single builder/runtime owner;
- equality between two fresh isolated builds is the blocking reproducibility
  proof;
- legacy comparison remains visible evidence, but not a false truth plane; and
- no second dispatcher, content store, approval path, or waiver mechanism is
  added.

Rejected alternatives are: rewriting legacy `app-data` inside Documents to
manufacture equality, retaining a permanently impossible legacy-equality gate,
or adding a human waiver that bypasses arbitrary parity differences.

Legacy AI summaries are naming-incompatible with the new hashed cache and may
contain private excerpts. They remain in the legacy app for Phase C retirement
and are not activated or copied in Phase B.

## HITL mutation contract

### Proposal ingress

OMO owns a `record_hitl_proposal` broker for the existing X4 proposal queue.
Cockpit exposes the authenticated create endpoint; Dashboard proposal routes
call Cockpit and never write `.omo` or Documents directly.

The proposal contains:

- stable proposal id and `type: family_dashboard_document_write`;
- `operation`: `replace_text`, `vaccine_update`, or `milestone_achieve`;
- target relative to `FAMILY_DOCUMENTS_ROOT`, never an absolute path;
- expected source existence, SHA-256, mode, and byte count;
- private runtime payload ref and payload SHA-256;
- human-readable change summary with no source/body fragment;
- operation level `L3`, `approval_required: true`, and `auto_apply: disabled`;
- verification and rollback contracts; and
- request trace/idempotency keys.

Proposal generation is not approval. Repeated ingress with the same id and
canonical digest is idempotent; a different digest is rejected.

### Approval and execution

Cockpit approval is the only human action. Approval immediately invokes the
existing BOS plugin hook with server-owned approver identity and timestamp.
The registered route is an `internal` Agora service targeting family-hub and
has cache TTL zero; no mutation result may be replayed from cache.

The family-hub owner then:

1. validates proposal schema, operation, relative target, allowlist, payload
   containment, payload mode, payload digest, and approval metadata;
2. canonicalizes the Documents root and rejects traversal or every symlink
   component;
3. independently re-reads source metadata and requires exact CAS equality;
4. writes original bytes and a `prepared` receipt under Workspace runtime;
5. writes the proposed bytes using same-directory temporary file, `fsync`,
   preserved mode, and atomic `replace`;
6. re-reads the target and requires the proposed digest;
7. writes `apply` and `verify` receipts; and
8. returns only the receipt ref/digest to Cockpit/OMO.

Any failure after mutation restores the original bytes (or removes a newly
created canary), verifies the rollback digest, and writes `rollback.json`.
Unknown final state is a hard failure and leaves the proposal visible.

OMO archives a durable approval/execution receipt before removing a successful
queue item. Reject keeps a durable rejected receipt. The OMO receipt binds the
proposal digest, approver, approval time, BOS URI, runtime receipt ref/digest,
and terminal status; it never copies the payload or Documents body.

## Operation policy

| Surface | Phase B behavior |
|---|---|
| Generic file save | Validate CSRF/path/body size, stage private payload, create proposal, return HTTP 202 |
| Vaccine update | Render proposed whole-file bytes from an exact source hash, then create proposal |
| Milestone achievement | Render proposed whole-file bytes from an exact source hash, then create proposal |
| Task completion | Continue writing only `state/generated/tasks.json`; no Documents mutation |
| AI summary/embedding cache | Continue writing only state cache |
| Backup | Produce Workspace snapshot/receipt; never run Git against Documents |

The proposal API never reports `saved` before the OMO terminal receipt exists.

## Error handling

- Missing roots, unknown manifests, malformed JSON/YAML, parity drift, cache
  copy, source mutation, or target collision stops runtime promotion.
- Cockpit/OMO/Agora unavailable returns proposal-unavailable and performs no
  side effect.
- Missing or caller-supplied approval identity, stale source hash, payload
  drift, unsafe target, duplicate conflict, receipt collision, or BOS caching
  stops mutation before write.
- A partial mutation must prove rollback; inability to prove either applied or
  restored state is an incident, not a successful response.

## Testing strategy

### family-hub

- RED/GREEN tests for runtime plan/apply/verify/rollback, private modes,
  determinism, source drift, collisions, symlinks, insufficient state, parity,
  and no source mutation.
- RED/GREEN tests for all three proposal operations, payload redaction,
  idempotency, CAS, atomic apply, rollback, and no direct Next.js writes.
- Existing dashboard unit, lint, build, E2E, root Vite, Python, and FastMCP
  suites remain green.

### OMO

- Proposal ingress is exclusive/idempotent, rejects secrets and malformed
  envelopes, and has one registered writer.
- Approve/reject/execute produce immutable terminal receipts and preserve queue
  items on execution failure.

### Cockpit and Agora

- Cockpit create/approve routes use server-owned identity and never accept a
  client-selected approver.
- BOS registry validation proves the exact URI, internal function binding, and
  cache TTL zero.
- Resolver tests execute the family-hub function with a sanitized proposal and
  never call `tools/call` or a shell string.

### Real evidence

- Two read-only real-data builds against the current family Documents root,
  with stable input-closure digests and equal normalized fresh products.
- A privacy-safe legacy-delta receipt records every preserved `app-data`
  comparison without copying or rewriting the legacy products.
- Consumer audit remains `forbidden_executors=0`, and source tree fingerprints
  remain unchanged.
- A real write canary is a separately confirmed danger-gate operation. It
  creates a dedicated non-private canary document through the approved path and
  then uses the same transaction rollback to restore absence. No existing
  household document is selected for the canary.

## Delivery sequence

1. Merge family-hub runtime/mutation owner and tests.
2. Merge OMO broker/receipt support.
3. Merge Agora declarative BOS route and cache policy.
4. Merge Cockpit proposal ingress/approval binding.
5. Merge Dashboard proposal routes after all downstream authorities exist.
6. Update root gitlinks child-first, run synthetic and real read-only evidence.
7. Obtain explicit canary confirmation, execute and roll back the real canary.
8. Finalize report/retro/completion evidence while keeping the migration family
   non-terminal for Phase C.

## Acceptance

Phase B is complete only when all of the following are proven:

1. canonical Workspace runtime state exists with six private manifests,
   rebuilt generated products, empty/new cache, stable input-closure evidence,
   equal normalized double-build parity, an explicit legacy-delta receipt,
   immutable migration receipt, and unchanged Documents source;
2. Dashboard write routes return proposals and contain no direct Documents
   writer or environment bypass;
3. Cockpit approval invokes the exact uncached BOS route and the family-hub
   owner produces CAS/apply/verify or proved rollback receipts;
4. one separately approved real canary completes and rolls back without
   touching existing household documents;
5. all child and root PRs merge, root gitlinks equal authoritative child mains,
   required CI passes, and fresh-main replay succeeds; and
6. `family-dashboard-app` remains pending/in-progress for Phase C, with live
   entry cutover, old-app retirement, value, and Documents-wide physical purity
   still `NOT_PROVEN`.

## Phase C admission boundary

Phase C may start only after this Phase B receipt set is complete. It owns the
unique Cockpit domain-app contract, persistent service/port, operational
observation window, final consumer cutover, recoverable old-app/cache
quarantine, migration-family terminal state, and any principal-bound value
claim.
