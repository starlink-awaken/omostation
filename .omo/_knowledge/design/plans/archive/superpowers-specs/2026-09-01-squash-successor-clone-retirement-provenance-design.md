---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-01
last-reviewed: 2026-09-03
bet_id: BET-Y1Q4-T1-02
risk_level: L2
human_gate: true
value_indicator_policy: false
type: ssot
last_updated: 2026-09-03
---

# Squash-Successor Clone Retirement Provenance Design

## 1. Executive decision

Introduce a dedicated, fail-closed retirement mode for a ready,
provenance-bound independent clone whose delivery branch:

1. started at a valid frozen root;
2. advanced through one or more authoritative main successors before the
   delivery commit;
3. was merged by a one-parent squash commit; and
4. can no longer pass ordinary retirement because the ordinary guard correctly
   treats every commit in `frozen_root..HEAD` as delivery-authored.

This mode is separate from ordinary retirement and
`--platform-rebased-pr`. It does not infer authority, rewrite provenance,
relax the default guard, or permit manual deletion. It accepts only an explicit
PR, annotated source tag, delivery base, external evidence path, and clone
destination.

The implementation is intentionally narrow:

- modify `bin/gac/clone-lifecycle.py`;
- add focused coverage in `tests/test_clone_lifecycle.py`;
- reuse `bin/gac/agent-clone.py retirement-provenance` unchanged to verify
  author and committer identity over the explicit
  `delivery_base..source_head` range.

No new daemon, registry, dispatcher, database, runtime ledger, or truth plane is
introduced.

## 2. Direct incident evidence

The motivating retained clone has immutable evidence:

- identity frozen root:
  `1436639a4d3acc4076108f66486f0f0a18c6ac3f`;
- admitted main successors before delivery:
  `377e561259cd8bdf62c5c39ff6523969f9fcb38d` and
  `2f4eb7a5d8b909cfda8999da87092d4c88f967bf`;
- source/delivery HEAD and remote annotated tag target:
  `565f6a28faaf88cbebcad7afeb87a1ad864ff79c`;
- merged PR: `starlink-awaken/omostation#2881`;
- PR base / one-parent squash merge:
  `c963a18c27dd53b59478f49757061ef98c583557` /
  `8ac2135387705b3baac8c7d6f29c5d7f9cce83d3`;
- source delivery base, derived as the exact merge-base of source HEAD and PR
  base:
  `2f4eb7a5d8b909cfda8999da87092d4c88f967bf`;
- source delta and squash delta contain the same three paths and identical
  resulting blobs; their stable patch identity is
  `4f22bdb4`.

Ordinary retirement fails because it verifies author/committer identity across
the complete `frozen_root..HEAD` range, which includes the two legitimate
main commits. Platform-rebased retirement is inapplicable because the PR base
is not an ancestor of the local source HEAD. Provenance rebinding correctly
fails after delivery commits exist, and `abort-unready` correctly rejects a
ready clone.

The retained clone remains clean, provenance/readiness-bound, and free of
workflow runs and locks. It is evidence, not disposable debris, until this
contract is implemented and verified.

## 3. Goals

1. Retire the exact squash-successor topology through the canonical lifecycle
   entrypoint without attributing imported main commits to the delivery agent.
2. Preserve ordinary and platform-rebased retirement semantics byte-for-byte
   outside the new mode.
3. Bind retirement to immutable GitHub PR, annotated tag, delivery range,
   squash tree, current main, repository, actor, attempt, and external receipt
   evidence.
4. Persist an immutable, digest-chained proof/delete-intent/settlement receipt
   set outside the clone so both authorization and completed deletion survive
   process crashes.
5. During a live transaction, restore the clone on every detected proof,
   receipt, origin, PR, tag, main, inode, or quarantine race before FD-bound
   deletion. After a process crash, preserve any unrecorded quarantine for
   explicit recovery; after deletion, recover only the durable settlement.
6. Make the destructive operation idempotent only when the exact external
   receipt chain proves either completed deletion or a recoverable
   canonical-tool quarantine.

## 4. Non-goals

- Do not change the default `guard` or ordinary `retire` author range.
- Do not change `--platform-rebased-pr` or its wrapper-chain semantics.
- Do not edit or regenerate existing clone identity, provenance, readiness,
  baseline, or changeset receipts.
- Do not infer a delivery base from mutable state without an explicit
  `--delivery-base` argument.
- Do not accept lightweight tags, local-only tags, or ambiguous remote refs.
- Do not delete a dirty clone, a clone with live/stale locks, an active run, an
  unmerged PR, a non-main PR, or a clone with unproven submodule state.
- Do not write to `runtime/`, `.omo/state/`, user configuration, or a new
  central retirement ledger.
- Do not mark any BET done or claim personal value from this governance
  repair.
- Do not delete the retained motivating clone during Spec bootstrap, binding,
  planning, implementation, or PR review.

## 5. Rejected alternatives

### 5.1 Default-guard delivery-base inference

Rejected. It would weaken the frozen-root invariant for every ordinary clone
and make an inferred merge-base an implicit authority boundary.

### 5.2 Provenance rebinding after delivery

Rejected. Late binding would rewrite historical authority after commits exist
and is correctly blocked by the current tool.

### 5.3 Manual quarantine or recursive deletion

Rejected. It would destroy the only remaining evidence and bypass the canonical
clone lifecycle, PR, receipt, and race checks.

### 5.4 Reusing `--platform-rebased-pr`

Rejected. Platform update-branch/rebase proves a platform-generated head whose
base is in its source ancestry. A one-parent squash result is a different
topology and requires a distinct merge-tree proof.

## 6. CLI contract

The new mode is selected only when all four new arguments are present:

```bash
python3 bin/gac/clone-lifecycle.py retire \
  --destination /Users/xiamingxing/agents/blueprint-governance-skill-maintenance/attempts/architecture-perception-command-20260901-01/ws \
  --squash-merged-pr 2881 \
  --source-tag delivery/architecture-perception-command-contract-20260901-v1 \
  --delivery-base 2f4eb7a5d8b909cfda8999da87092d4c88f967bf \
  --evidence /Users/xiamingxing/agents/blueprint-governance-skill-maintenance/attempts/architecture-perception-command-20260901-01/squash-retirement-proof.json
```

Contract rules:

1. `--squash-merged-pr`, `--source-tag`, `--delivery-base`, and
   `--evidence` are required together.
2. The new mode is mutually exclusive with `--platform-rebased-pr`.
3. `--delivery-base` must be an exact 40-hex commit, not a branch or mutable
   ref.
4. `--source-tag` is a tag name below `refs/tags/`; the live remote must
   expose exactly one annotated tag object and one peeled commit.
5. `--evidence` is the proof-receipt path. It must resolve outside the clone,
   must not be a symlink, and must be created or matched by the exclusive
   receipt writer. The delete-intent and settlement paths are derived exactly
   as `<evidence>.delete-intent` and `<evidence>.settled`.
   Throughout this Spec, `<evidence>` is a defined metavariable equal to the
   exact `--evidence` argument, not an unresolved path placeholder.
6. Missing or mixed arguments return policy failure before any evidence or
   quarantine write.
7. Existing ordinary and platform-rebased parser behavior remains unchanged.

## 7. Component responsibilities

### 7.1 `clone-lifecycle.py`

Owns:

- strict GitHub PR projection;
- tag and current-main authority reads;
- delivery-base and squash topology proof;
- patch-to-merge-tree reproduction;
- invocation of the existing author-range verifier;
- external proof construction and exclusive persistence;
- repeated proof reads;
- quarantine restoration and FD-bound deletion;
- idempotent already-absent handling with matching evidence.

### 7.2 `agent-clone.py`

Remains unchanged. Its existing `retirement-provenance` command is invoked
with:

- `platform_base = delivery_base`;
- `platform_head = source_head`.

For this topology those arguments describe the exact delivery-authored range,
so the existing frozen-root ancestry, repository receipt, live author, author,
and committer checks remain authoritative. The platform argument names are an
internal compatibility detail; they are not exposed as the new lifecycle CLI.

### 7.3 `tests/test_clone_lifecycle.py`

Owns the real behavior contract and all positive/negative/race fixtures. Tests
must exercise the existing code paths, not only compare text or mock a final
boolean.

## 8. Proof protocol

The lifecycle must complete these predicates in order before quarantine.

### P1 — clone identity and local state

- destination is the exact independent-clone `ws` directory;
- `.git` is clone-local, not a linked worktree;
- identity schema is v2 and binds the actor, agent, delivery attempt, canonical
  root, working branch, frozen root, and provenance/readiness digests;
- root and initialized submodules are clean;
- active runs, live locks, stale locks, and unreadable workflow state are all
  empty.

### P2 — repository and origin

- the verified provenance receipt resolves one canonical GitHub repository;
- fetch and push origin each expose exactly one URL;
- both URLs resolve to the receipt repository;
- no URL rewrite changes the declared authority.

### P3 — exact merged PR

The GitHub projection has an exact scalar schema containing:

- number, URL, state;
- base ref name and OID;
- head ref name and OID;
- head repository and owner;
- merge commit OID and merged timestamp.

Require:

- state `MERGED`;
- base ref `main`;
- repository, owner, branch, and PR number equal the clone/CLI identities;
- head OID equals local source HEAD;
- every required OID is 40-hex;
- no missing or extra projection field.

### P4 — exact annotated source tag

- local tag ref is a Git tag object, not a lightweight commit ref;
- the tag object peels to local source HEAD;
- the remote returns one exact tag object plus its one peeled commit;
- remote tag object and peeled target equal the local values;
- no other ref is accepted as attribution.

### P5 — explicit delivery base

- `merge-base(source_head, pr_base)` returns one exact commit;
- the result equals `--delivery-base`;
- frozen root is an ancestor of delivery base;
- delivery base is an ancestor of PR base;
- `delivery_base..source_head` is non-empty.

### P6 — delivery-only author and committer identity

Invoke the unchanged `agent-clone.py retirement-provenance` verifier over
`delivery_base..source_head`. Imported commits before delivery base are not
attributed to the delivery agent. Every commit inside the explicit range must
match the clone-bound author and committer digest.

### P7 — one-parent squash topology

- merge commit object is locally present;
- merge commit has exactly one parent;
- that parent equals the queried PR base OID;
- merge commit differs from source HEAD while representing the accepted
  result.

### P8 — patch-to-tree equivalence

- create a binary full-index patch for
  `delivery_base..source_head`;
- enumerate a non-empty ordered changed-path set;
- seed a temporary index from the PR base tree;
- apply the source patch to that index;
- write the reproduced tree;
- require reproduced tree equal the squash merge tree;
- record changed-path count and SHA-256 digest.

No working tree, branch, index, or repository file is modified by this proof.

### P9 — current remote main

- resolve `refs/heads/main` directly from the canonical origin;
- reject URL rewrite, missing, or ambiguous authority;
- require the squash merge commit to be an ancestor of the first main read;
- repeat the read before quarantine and require exact equality;
- a concurrent main advance is a retryable fail-closed race, not an implicit
  successor admission.

### P10 — surviving source branch

The remote source branch may be:

- absent after GitHub branch auto-deletion; or
- present exactly at source HEAD.

Any other surviving OID is a contradiction and blocks retirement.

### P11 — external receipt chain

Construct one canonical
`clone-squash-successor-retirement-proof/v1` payload containing:

- canonical repository, PR identity, branch, actor, attempt, destination;
- frozen root, delivery base, source HEAD;
- tag name, tag object, peeled tag target;
- PR base, squash commit, squash parent and tree;
- current main OID;
- changed-path count and digest;
- provenance/readiness receipt digests;
- clone state digest;
- `status: verified_for_retirement`;
- receipt digest over every other field.

Persist it before quarantine with:

- parent-chain `O_NOFOLLOW` validation;
- leaf `O_CREAT | O_EXCL | O_NOFOLLOW`;
- file and parent-directory `fsync`;
- exact-match idempotency when the file already exists.

The proof is authorization to retire the exact state. It is not personal value
evidence and does not claim deletion before deletion occurs.

After quarantine rename and complete post-quarantine revalidation, but before
FD-bound deletion, create
`clone-squash-successor-retirement-delete-intent/v1` at
`<evidence>.delete-intent`. It contains:

- proof receipt digest;
- destination, repository, actor, attempt, PR, merge, and source HEAD;
- exact quarantine and payload paths;
- payload device/inode identity captured from the opened quarantine payload;
- `status: delete_authorized`;
- its own receipt digest.

The delete-intent uses the same no-follow, `O_EXCL`, file-`fsync`, and
parent-`fsync` rules. If it cannot be written or exactly matched, the
quarantined clone is restored and deletion does not begin.

After FD-bound payload deletion and quarantine-directory removal, create
`clone-squash-successor-retirement-settlement/v1` at
`<evidence>.settled`. It contains:

- proof and delete-intent receipt digests;
- destination, repository, actor, attempt, PR, merge, and source HEAD;
- `status: retired`;
- settlement timestamp;
- its own receipt digest.

Settlement failure is not reported as retirement success. It returns a typed
`settlement_pending` result whose exact proof and delete-intent remain
available for bounded replay.

The settlement uses the same parent-chain `O_NOFOLLOW`, leaf
`O_CREAT | O_EXCL | O_NOFOLLOW`, file-`fsync`, parent-directory-`fsync`,
and exact-match replay rules as the proof and delete-intent. An existing
identical settlement is idempotent; a missing, partial, or mismatched
settlement is never overwritten or treated as success.

## 9. Revalidation and deletion

After the external proof is durable:

1. re-run the PR, tag, origin, source branch, main, HEAD, clean-state, run, and
   lock reads;
2. re-read the external proof through the safe external reader and require
   byte-semantic equality;
3. quarantine-rename only the verified destination inode;
4. from the quarantined payload, re-prove HEAD, clean state, run/lock absence,
   repository origin, PR, tag, current main, and external proof;
5. write and re-read the exact delete-intent bound to the opened quarantine
   payload;
6. only then perform the existing FD-bound, symlink-safe recursive deletion;
7. remove the now-empty quarantine directory and write the exact settlement
   receipt.

Any mismatch before irreversible deletion restores the original clone path.
No path-based fallback deletion is permitted.

If the destination is already absent, success is allowed only when the external
receipt state satisfies one of these cases:

- **Settled replay:** proof, delete-intent, and settlement all have valid
  schemas/digests, form one exact digest chain, match the supplied PR, tag,
  delivery base, and destination, bind non-empty repository/actor/attempt
  values, still resolve exact PR/tag/main authority, and have no recorded or
  unexpected quarantine directory.
- **Crash after delete, before settlement:** proof and delete-intent form an
  exact chain, settlement is absent, destination and both recorded/unexpected
  quarantine paths are absent, and live PR/tag/main authority still matches.
  The tool writes the settlement and then returns success.
- **Crash after quarantine, before delete:** proof and delete-intent form an
  exact chain and the one recorded quarantine payload still matches its bound
  device/inode, HEAD, clean state, repository, PR, tag, and main. The tool
  resumes the existing FD-bound deletion, removes that quarantine, writes the
  settlement, and returns success.

Because the clone is absent, repository authority for replay is read only from
the digest-valid proof and must pass URL-rewrite rejection before network use.
Proof without delete-intent cannot establish that the canonical tool acquired
quarantine ownership; it is rejected as `retirement_unsettled`. An
unrecorded, mismatched, or additional quarantine is preserved and rejected.
Absent destination without an exact settled or recoverable receipt chain is
policy failure.

## 10. Error semantics and rollback

- **Proof failure before evidence:** no persistent write; clone remains.
- **Evidence collision/tamper:** fail; clone remains; do not overwrite.
- **Race after evidence but before quarantine:** fail; clone remains; the
  prepared proof can be reused only if the complete state is unchanged.
- **Delete-intent failure:** restore the original clone path and fail.
- **Race after quarantine but before delete-intent:** restore the original
  clone path and fail.
- **Crash after delete-intent:** replay only the exact recorded quarantine
  disposition described in Section 9.
- **Settlement failure after deletion:** return `settlement_pending`; do not
  claim retirement success until bounded replay writes the settlement.
- **Successful deletion:** source commit remains recoverable from the annotated
  tag, merged PR, squash commit, main ancestry, and external receipt chain.
- **Implementation regression before use:** revert the implementation PR.
- **Post-merge gate failure:** do not invoke retirement; revert through a new
  PR if the failure is caused by the new files.

The mechanism does not promise byte-for-byte local cache recovery after
successful deletion. The retained source/tag/PR/main/evidence chain is the
recovery boundary.

## 11. Test contract

### 11.1 Mandatory RED

Before implementation, add a focused fixture matching the motivating topology:

- frozen root;
- two legitimate foreign-author main successors;
- one clone-authored delivery commit and annotated remote tag;
- newer PR base;
- one-parent squash merge whose tree equals the patch applied to that base;
- current main containing the squash merge;
- clean, ready v2 clone with no run/lock.

The test must first fail because the parser/new mode does not exist or ordinary
retirement returns `clone_provenance_mismatch`. An import/setup error is not
accepted RED.

### 11.2 Mandatory GREEN

The exact fixture retires only with all new arguments and a durable matching
external proof. The clone is absent, the evidence remains, and ordinary and
platform-rebased fixtures remain green.

### 11.3 Negative coverage

At minimum cover:

1. partial/mixed new CLI arguments;
2. new mode combined with `--platform-rebased-pr`;
3. v1 or unbound identity;
4. wrong repository, owner, branch, PR number, state, or base name;
5. missing/extra GitHub schema field;
6. wrong source head, delivery base, frozen ancestry, or foreign delivery
   author/committer;
7. lightweight, local-only, ambiguous, moved, or wrongly peeled tag;
8. missing merge/base/head objects;
9. multi-parent or wrong-parent merge commit;
10. patch apply failure, empty delta, changed-path drift, or tree mismatch;
11. merge not reachable from current main;
12. current-main double-read race;
13. surviving remote branch at a contradictory OID;
14. fetch/push origin mismatch or origin race;
15. evidence collision, digest alteration, symlink, parent swap, or path inside
    the clone;
16. missing, altered, crossed, or mismatched proof/delete-intent/settlement
    chain;
17. PR/tag/evidence/main drift before quarantine;
18. the same drifts after quarantine, with original path restored;
19. proof-only absent destination, unrecorded quarantine, multiple
    quarantines, or quarantine inode/HEAD drift;
20. exact replay for crash-after-quarantine and crash-after-delete-before-
    settlement;
21. settlement write failure reported as pending rather than success;
22. dirty root/submodule, active run, live/stale lock, or unreadable state;
23. preservation of every existing ordinary/platform retirement test.

### 11.4 Verification commands

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml \
  python -m pytest -q -p no:cacheprovider tests/test_clone_lifecycle.py

uv run ruff check \
  bin/gac/clone-lifecycle.py tests/test_clone_lifecycle.py

PYTHONDONTWRITEBYTECODE=1 python3 -c \
  'import ast, pathlib; ast.parse(pathlib.Path("bin/gac/clone-lifecycle.py").read_text())'
python3 bin/gac/clone-lifecycle.py retire --help
python3 bin/gac/gac-validate.py --gate
git diff --check
```

The focused suite must run with explicit PyYAML; a missing dependency is an
environment failure, not a product verdict.

## 12. Delivery and rollout

### Phase 0 — draft Spec

This document and its explicit workflow-start waiver only. No binding, code,
test, receipt, clone, runtime, or ledger mutation.

### Phase 1 — accepted binding

Only after a new, separate, operation-specific principal authorization for
accepted binding:

- change this Spec to `status: accepted`, version `1.0.0`;
- bind a new candidate `BET-Y1Q4-T1-02`;
- depend on `BET-Y1Q3-T1-11`;
- keep engineering `NOT_STARTED`, operational/value `NOT_PROVEN`, overall
  `evaluating`, and `value_indicator_policy=false`;
- declare only the accepted Spec, plan, ledger, waiver, two implementation
  files, and retro as repository `write_surfaces`;
- record the exact external proof path separately as the future Phase 4
  operation surface. It is outside the repository and therefore is not a
  workflow claim surface.

### Phase 2 — writing-plans

Produce a complete TDD implementation plan after the accepted binding PR is
merged. No code implementation occurs during binding.

### Phase 3 — implementation

- start a fresh BET-bound workflow in a fresh independent clone;
- claim every exact repository `write_surface`;
- complete real RED before production edits;
- implement only the accepted contract;
- run focused/full verification and independent Orca review;
- commit, annotated tag, unique PR, required checks, squash merge, and exact-SHA
  post-merge Governance Check.

### Phase 4 — operational canary and cleanup

Only after implementation post-merge success and a separate,
operation-specific principal authorization:

- invoke the new mode against the retained motivating clone with the exact PR,
  tag, delivery base, destination, and external evidence path;
- verify the clone is absent, the proof/delete-intent/settlement chain remains
  valid, no quarantine remains, and no unrelated clone/branch/tag was modified;
- preserve the external receipt chain as the cleanup receipt;
- do not promote personal value or any unrelated BET.

## 13. Acceptance criteria

The design is implemented only when direct evidence proves:

1. ordinary and platform-rebased retirement behavior is unchanged;
2. the motivating topology fails ordinary retirement and passes only the
   explicit new mode;
3. author attribution excludes imported main commits but includes every
   delivery commit;
4. exact annotated tag, PR, squash parent/tree, current main, repository,
   branch, actor, and attempt are bound;
5. external proof is durable before quarantine, delete-intent is durable after
   quarantine ownership, and settlement is durable after deletion;
6. all required negative/race tests restore or preserve the clone;
7. required PR contexts and exact-SHA post-merge Governance Check succeed;
8. the retained motivating clone is retired only through the canonical tool;
9. the exact external proof/delete-intent/settlement chain remains after
   deletion;
10. no runtime registry, receipt rebinding, manual deletion, BET completion, or
    personal-value claim occurs.

## 14. Value and completion boundary

This is governance infrastructure. During draft, binding, implementation, and
cleanup:

- value remains `NOT_PROVEN`;
- no personal value indicator is written;
- implementation success does not imply operational cleanup success;
- operational cleanup success does not mark T1-11, T1-12, or the future BET
  done;
- any later completion transition requires its own completion matrix, retro,
  and principal acceptance.

## 15. Accepted review record

The principal reviewed the draft at SHA-256
`222106b0f3f0f24c35901b44f1cab3004e257c9f9a3cbbf655daf2b528c44f5a`
and, on 2026-09-03, approved recommended authorization package Sections 1
through 4. That review accepted:

- the dedicated CLI mode;
- the exact proof predicates;
- unchanged `agent-clone.py` and existing retirement modes;
- the external evidence model;
- the negative/race test boundary;
- the `BET-Y1Q4-T1-02` binding and value isolation.

This accepted transition authorizes only the Spec, candidate binding, and
waiver described in Phase 1. It does not itself authorize an implementation
plan, code, test, runtime operation, receipt write, or clone deletion.
