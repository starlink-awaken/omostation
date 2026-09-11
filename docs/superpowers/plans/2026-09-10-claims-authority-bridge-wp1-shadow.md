---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-11
last_updated: 2026-09-11
type: doc
---

# Claims Authority Bridge WP1 R0 Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver WP1 as a cooperative R0 shadow authority that records independently verified v1/v2 claim comparisons, fences every legacy publication after exact activation, converges all tracked publication effects onto `clone-lifecycle integrate`, and graduates only after a clean 24-hour evidence window without ever making v2 an effective claim authority.

**Architecture:** One child module owns canonical schemas, account-resolved SQLite state, receipts, comparisons, legacy fences and redacted status. Root adapters call that module through a one-request stdio command while v1 remains the only effective claim decision. Seven sequential accepted-binding versions expose exactly one delivery partition at a time; child work merges first, root adapters and effect convergence follow, the root gitlink moves last, and a separately authorized host activation starts the shadow window.

**Tech Stack:** Python 3.13+ standard library (`sqlite3`, `json`, `hashlib`, `pwd`, `pathlib`, `dataclasses`), Bash, PyYAML only in existing root tooling, pytest, GitHub Actions YAML, Agent Workflow/WorkPacket v2, managed independent clones, GitHub required contexts.

## Global Constraints

- Canonical Spec: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`, accepted version `1.1.2`, SHA-256 `bc1de057c28ce91aec5120396bcdedebb3b93b1289fcdc8c81387554efd47192`.
- Parent/child: `BET-Y1Q4-T10-145` is a child of zero-write parent `BET-Y1Q4-T10-143`; `depends_on=[]` is intentional because parent coordination is not a completed execution predecessor.
- Current WorkPacket `sha256:73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613` authorizes only the three Wave A child paths listed by Tasks 2–4. Versions 1.0.0, 1.1.0 and 1.1.1 are immutable history, not current execution authority.
- Each later version `1.2.0` through `1.7.0` is a complete replacement, never a union. The prior run must be closed, its locks must be zero, and the new Spec digest and WorkPacket hash must be verified before any new path is claimed.
- WP1 is shadow-only: `effective_claim_authority=v1`; v2 may return `would_allow`, `would_deny` or `unprovable` but may never grant, deny or publish.
- v2 never authorizes a valid managed clone during WP1. The managed-clone shadow
  lifecycle remains unpublished and the only expected difference is v1 fixed-root
  deny plus v2 `would_allow`. A WP1 implementation commit rejected solely by the
  existing v1 fixed-root gap may be delivered only through a separately recorded,
  exact-commit Human/time-bounded-delegated degraded publication; that exception is
  never a v2 receipt, never graduation evidence and never a reusable precedent.
- `clone-lifecycle.py::cmd_integrate()` is the only remote Git/ref and PR effect owner. The broker never runs Git or `gh`.
- Before exact descriptor activation, only pristine total absence or a verified canonical `unactivated` witness returns `shadow_unprovable:not_activated` and preserves bootstrap behavior. If the canonical stdio broker is unavailable while the account-resolved witness is `prepared`, `shadow-active`, invalid, rolled back, unsafe or missing after store/high-water initialization, reject before any v1 write. After activation, every v1-allowed publication must possess one fresh, consumable legacy fence before Git.
- No daemon, UDS, LaunchAgent, network port, MCP server, Dashboard authority, service account, Keychain material, multi-tenant RBAC, HA or R1 security is introduced.
- Production store paths derive from `pwd.getpwuid(os.getuid()).pw_dir`; `$HOME`, cwd, CLI/env store overrides and clone-local policy never choose authority.
- Production paths and ancestors must not be symlinks, must be owned by the current UID, and must not be group/world writable. Dedicated directories use `0700`; files use `0600`; shared ancestors are never chmodded.
- Before creating a production store, reuse the canonical SQLite WAL-safety predicate. An unsafe SQLite runtime fails closed with `AUTHORITY_STORE_UNSAFE` before DDL, witness or high-water mutation; it never downgrades to `journal_mode=DELETE`. Every admitted mutation then verifies actual WAL mode and uses `BEGIN IMMEDIATE`, `synchronous=FULL`, foreign keys and a 5-second busy timeout. Corruption never auto-restores; only the exact one-tail crash case may reconcile.
- Broker-owned claim lease is 15 minutes; heartbeat is at most 5 minutes and
  increments the broker-owned lease epoch without adding fields to v1; broker clock
  rollback beyond 30 seconds fails closed; observer freshness is 120 seconds.
- An unresolved run-scoped claim-mutation batch (`reserved`, `unknown` or
  operator-required) blocks fence entry, graduation and rollback restoration until
  that same batch and all of its members are settled with canonical evidence.
- Test authority IDs use `test:UUIDV4` and `publishable=false`. Production verification rejects every `test:*` receipt.
- No automatic push retry, replacement token/fence, force push, `--no-verify`, projection-to-authority write, historical receipt promotion, completion inflation or value claim.
- `value_indicator_policy=false`; engineering/CI/shadow evidence never counts as personal value. Operational/value remain `NOT_PROVEN` through WP1.
- WP2 must have no Ledger ID, Spec, binding, run or write surface before WP1 is honestly done.
- The accepted Ledger appetite is `12 days` of elapsed delivery time, including the mandatory 24-hour observation. It is a circuit-breaker budget, not completion, graduation, operational or value evidence.

## Frozen Command and Data Contracts

The following names are fixed by this plan so separate workers do not invent incompatible APIs.

### Child Python API

`projects/omo/src/omo/workflow/claims_authority.py` exposes only these public symbols:

```python
class AuthorityError(RuntimeError):
    code: str

@dataclass(frozen=True)
class AuthorityPaths:
    account_home: Path
    integration_root: Path
    authority_dir: Path
    store: Path
    high_water: Path
    backups: Path
    activation_witness: Path

@dataclass(frozen=True)
class V1Decision:
    decision: Literal["allow", "deny"]
    code: str

@dataclass(frozen=True)
class ShadowDecision:
    decision: Literal["would_allow", "would_deny", "unprovable"]
    code: str

def canonical_json(value: Mapping[str, Any]) -> str: ...
def canonical_digest(value: Mapping[str, Any]) -> str: ...
def resolve_authority_paths() -> AuthorityPaths: ...
def dispatch_request(verb: str, request: Mapping[str, Any] | None) -> dict[str, Any]: ...
def observe_claim(request: Mapping[str, Any]) -> dict[str, Any]: ...
def begin_claim_mutation(request: Mapping[str, Any]) -> dict[str, Any]: ...
def settle_claim_mutation(request: Mapping[str, Any]) -> dict[str, Any]: ...
def mark_claim_mutation_operator_required(request: Mapping[str, Any]) -> dict[str, Any]: ...
def resolve_claim_mutation_unknown(request: Mapping[str, Any]) -> dict[str, Any]: ...
def activate_shadow(request: Mapping[str, Any]) -> dict[str, Any]: ...
def issue_legacy_fence(request: Mapping[str, Any]) -> dict[str, Any]: ...
def enter_legacy_publishing(request: Mapping[str, Any]) -> dict[str, Any]: ...
def settle_legacy_publication(request: Mapping[str, Any]) -> dict[str, Any]: ...
def mark_legacy_operator_required(request: Mapping[str, Any]) -> dict[str, Any]: ...
def resolve_legacy_unknown(request: Mapping[str, Any]) -> dict[str, Any]: ...
def authority_status() -> dict[str, Any]: ...
def evaluate_graduation(request: Mapping[str, Any]) -> dict[str, Any]: ...
def cli_main(argv: Sequence[str]) -> int: ...
```

Internal test injection is limited to `_AuthorityStore.connect_for_test(path: Path, authority_id: str)`. No production CLI flag accepts a path or connection.

### Root stdio API

The only production entry is the integration-root script:

```text
bin/agent-workflow.py claims-authority observe-claim --request-json -
bin/agent-workflow.py claims-authority begin-claim-mutation --request-json -
bin/agent-workflow.py claims-authority settle-claim-mutation --request-json -
bin/agent-workflow.py claims-authority mark-claim-mutation-operator-required --request-json -
bin/agent-workflow.py claims-authority resolve-claim-mutation-unknown --request-json -
bin/agent-workflow.py claims-authority activate-shadow --request-json -
bin/agent-workflow.py claims-authority issue-legacy-fence --request-json -
bin/agent-workflow.py claims-authority enter-legacy-publishing --request-json -
bin/agent-workflow.py claims-authority settle-legacy-publication --request-json -
bin/agent-workflow.py claims-authority mark-legacy-operator-required --request-json -
bin/agent-workflow.py claims-authority resolve-legacy-unknown --request-json -
bin/agent-workflow.py claims-authority evaluate-graduation --request-json -
bin/agent-workflow.py claims-authority status --json
```

Every mutation reads exactly one JSON object from stdin and emits exactly one canonical JSON object on stdout. Diagnostics are stderr-only. `status --json` accepts no body; all other bodyless calls fail `REQUEST_SCHEMA_INVALID`.

`begin-claim-mutation` accepts only `claim`, `heartbeat`, `close`, `takeover` or `expire` in
the envelope operation. Existing v1 claims have no version or lease-epoch field and a
single run may contain several claims, while heartbeat/close/takeover/expiry are
run-wide. The broker therefore owns all authority claim versions and lease epochs. In
one CAS, begin binds the exact v1 run/claims snapshot digest plus the complete sorted
v1 lock-set existence/content digest and creates one run-scoped
mutation batch containing every current broker claim member in stable claim-ID order.
It rejects the entire batch if any member is missing, stale, already reserved or bound
to a fence in `publishing`/`unknown`; fence entry rejects while a batch contains that
member. No v1 run/claim byte gains a version field.

The root workflow command settles the same batch with the exact resulting v1 run and
lock-set digests. This distinguishes heartbeat, which changes lock YAML but not run
YAML, and close/prune, which may delete locks. The broker atomically updates all member states and its own versions/epochs
for the operation. A crashed/unknown batch freezes every member and requires the same
separately authorized resolution discipline as an unknown fence; it is never timed
out, partially released or silently discarded.

On first observation the broker assigns each v1 claim a stable `claim_id` from the
canonical digest of authority ID, run ID, zero-based claim ordinal and exact v1 claim
digest. Re-reading the same bytes returns the same member; appending a claim creates
only the next ordinal. Reordering, removing or changing an earlier v1 claim is drift
and cannot be normalized into a new identity.

`mark-claim-mutation-operator-required` only marks an `unknown` mutation batch.
`resolve-claim-mutation-unknown` requires an operation-specific authorization digest,
proof that the v1 mutation process ended, and two equal independent reads of the
current v1 run/claims bytes, exact lock existence/content set, and broker-owned member versions/lease epochs. It may
settle the same batch as `applied` only when those reads prove the requested run-wide
transition for every member, or `rejected` only when they prove the complete
pre-mutation snapshot remains exact. Ambiguous, mixed or partial-member evidence
leaves it `unknown`; the resolver never edits v1 state, guesses an outcome or clears a
different batch.

`mark-legacy-operator-required` only sets an escalation marker on an `unknown` fence.
`resolve-legacy-unknown` requires an operation-specific authorization digest, proof
that the effect process ended, two equal reads of the exact remote ref/OID and the
original fence/request identity. It may settle that fence; it cannot create a new
fence, change a claim scope or clear any different marker.

### Mutation request bodies

Every request contains `schema`, UUIDv4 `request_id`, `authority_id`, broker-issued
time context and the complete `ClaimMutationEnvelope` identity tuple. Verb-specific
fields are fixed as follows:

| Verb | Additional required fields |
|---|---|
| `observe-claim` | v1 decision/code and exact resulting v1 run/claim plus lock-set snapshot digests; broker returns its own claim version/lease epoch |
| `begin-claim-mutation` | operation, exact v1 run/claims digest, complete sorted lock existence/content digest, and complete sorted broker member/version/lease tuple |
| `settle-claim-mutation` | mutation batch ID, exact resulting v1 run and lock-set digests, and result `applied`, `rejected` or `unknown`; broker computes new member versions/epochs |
| `mark-claim-mutation-operator-required` | unknown mutation ID, escalation reason code and mutation-process identity |
| `resolve-claim-mutation-unknown` | same batch ID, authorization digest, stopped-process proof digest, two equal complete v1 run/claims and lock-set reads plus broker member versions/epochs and final result |
| `activate-shadow` | complete descriptor object, expected authority epoch and expected `unactivated` state |
| `issue-legacy-fence` | v1 allow receipt reference, exact v1 snapshot digest, broker claim version/lease, changeset/path digests, HEAD and descriptor-bound remote-observation pair |
| `enter-legacy-publishing` | fence ID, expected `issued`, second equal v1 snapshot digest/broker version and a fresh descriptor-bound remote-observation pair |
| `settle-legacy-publication` | fence ID, outcome `success`, `rejected` or `unknown`, exact remote observations and effect-process identity |
| `mark-legacy-operator-required` | unknown fence ID, escalation reason code and effect-process identity |
| `resolve-legacy-unknown` | same fence ID, authorization digest, stopped-process proof digest, two equal remote observations and final outcome |
| `evaluate-graduation` | activation receipt, observation-window digest, lifecycle receipt IDs, RED report digest and publication-inventory digest |

Unknown fields, missing fields, caller timestamps used as authority, invalid enums and
noncanonical re-encoding return `REQUEST_SCHEMA_INVALID`. The broker independently
rereads repository, WorkPacket, identity, v1 run/claim and its own authority state. It
never runs Git or `gh`. Remote facts arrive only as two canonical observations
produced by the descriptor-bound real Git executable inside `clone-lifecycle`; the
broker validates equality, executable/descriptor binding, fence/request digest and
CAS state, but does not call this an independent remote read. Matching caller JSON
alone is not proof.

Each remote-observation pair is produced exclusively by `clone-lifecycle` using the
descriptor-bound real Git executable and the existing private-repository credential
context. Its two records bind repository identity digest, remote-ref digest, observed
OID, monotonic/broker-adjacent timestamps, Git executable/object digest, effect-process
identity and command digest; they contain no remote URL or credential. The broker
accepts the pair only when both records are canonical, equal in ref/OID/identity,
fresh, descriptor-bound and consistent with the fence's expected OID. This is
cooperative R0 evidence from the sole effect owner, not an independent broker network
read.

### Auxiliary R0 evidence, activation closure and source authority

Wave A recognizes two evidence schemas without making either one an authority object.
`claims-operator-authorization/v1` has exactly:

```text
schema, authority_id, security_level, principal_id, principal_authority_ref,
principal_receipt_digest, decision_ref, target_kind, target_id,
unknown_receipt_digest, resolver_operation, authorized_outcome,
process_identity_digest, issued_at, expires_at, digest
```

`claims-stopped-process-proof/v1` has exactly:

```text
schema, authority_id, security_level, observer_kind, observer_receipt_digest,
target_kind, target_id, unknown_receipt_digest, authorization_digest,
process_identity_digest, status, observed_at, digest
```

Both objects are canonical JSON no larger than 16 KiB. They are regular,
current-UID-owned, link-count-one, non-symlink, create-once `0600` files under
account-derived `0700` directories rooted at
`pwd.getpwuid(os.getuid()).pw_dir/agents/_shared/runtime/omo-claims-authority-r0`.
Authorization expires within 300 seconds, cannot predate `operator_required_at`, and
the stopped-process observation cannot predate authorization. Target, unknown receipt,
process identity, resolver and outcome must all match. Environment, cwd, CLI and
request JSON cannot redirect these paths. Presence and self-digest never grant a
claim, issue a fence, perform Git or resolve another target.

Version 1.1.2 binds no production principal-decision or process-observer verifier.
Therefore production `resolve-*-unknown` remains fail-closed even for structurally
valid files, and production activation rejects missing verifier digests. Only
`test:<uuid>` stores may exercise positive recovery mechanics. A future accepted
binding must name and closure-bind both exact verifier implementations before any
positive production recovery or activation can become possible.

The activation descriptor closure contains the existing descriptor fields plus
exactly:

```text
root_commit_oid, policy_blob_digest, child_gitlink_oid,
critical_dependency_entries, managed_python_receipt_digest,
managed_python_executable_digest, operator_authorization_verifier_digest,
stopped_process_verifier_digest
```

`critical_dependency_entries` is sorted by canonical path and each entry contains
only `path`, `kind` and `object_oid_or_digest`. Before activation the broker performs
two independent reads from the passwd-derived integration root and requires root,
policy, child gitlink, dependency entries, managed Python and both verifier digests to
match the request and descriptor. The Ledger, accepted Spec, Instruction Pack,
`bin/plan/bet-ledger.py` helper and the verifier entries belong to the same closure.
Policy bytes cannot embed their own descriptor digest. Any disagreement fails before
witness, SQLite or high-water mutation.

Before every production request capable of issuing a receipt/fence or changing
authority state, the broker loads the fixed integration-root
`bin/plan/bet-ledger.py`, calls `prepare_bet_execution(...,
require_startable=False)`, compares BET/packet identity, hash, unique Spec
version/digest, `implementation_authorized`, sorted write surfaces, required packets,
candidate/evaluating state and `value_indicator_policy=false`, then executes
`validate_work_packet_run()`. Clone-local bytes are evidence only. A self-consistent
clone packet that differs from the integration-root rebuild is `WORK_PACKET_UNBOUND`
and produces zero authority mutation. The only exception is an identical replay of a
previously committed request ID/body, which returns the stored response without a new
source-dependent mutation.

`begin-claim-mutation` and `enter-legacy-publishing` allocate one immutable
`settlement_request_id`. A lost settlement response may be confirmed only by replaying
the identical settlement request ID and canonical body. If the first commit happened,
the stored response is returned; if it did not, exact replay may commit once. The v1
mutation or Git effect is never repeated. If the broker remains unavailable, the
object stays `reserved` or `publishing`; callers must not fabricate `unknown` or an
operator marker. Same ID with different bytes is `REQUEST_ID_REUSE_MISMATCH`.

### Canonical response envelope

```json
{
  "ok": true,
  "schema": "claims-authority-response/v2",
  "authority_id": "omo-claims-authority-r0",
  "sequence": 1,
  "result": {},
  "error": null
}
```

Failures use `ok=false`, a redacted stable `error.code`, and no raw request, username, home path, hostname or remote URL.

### SQLite v1 schema

Wave A creates `PRAGMA user_version=1` with these tables in one serial migration:

```sql
CREATE TABLE authority_meta (
  authority_id TEXT PRIMARY KEY,
  epoch INTEGER NOT NULL,
  operating_mode TEXT NOT NULL CHECK (operating_mode IN ('shadow', 'enforce-r0', 'human-degraded-only')),
  descriptor_digest TEXT,
  last_sequence INTEGER NOT NULL DEFAULT 0,
  last_receipt_digest TEXT,
  last_broker_time TEXT NOT NULL
);
CREATE TABLE requests (
  authority_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (authority_id, request_id)
);
CREATE TABLE receipts (
  authority_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  receipt_id TEXT NOT NULL UNIQUE,
  previous_receipt_digest TEXT,
  receipt_json TEXT NOT NULL,
  receipt_digest TEXT NOT NULL UNIQUE,
  recorded_at TEXT NOT NULL,
  PRIMARY KEY (authority_id, sequence)
);
CREATE TABLE claims (
  claim_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  authority_claim_version INTEGER NOT NULL,
  authority_lease_epoch INTEGER NOT NULL,
  state TEXT NOT NULL,
  intent_or_fence_id TEXT,
  expires_at TEXT NOT NULL,
  identity_digest TEXT NOT NULL,
  v1_snapshot_digest TEXT NOT NULL
);
CREATE TABLE claim_mutation_batches (
  mutation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  operation TEXT NOT NULL CHECK (operation IN ('claim', 'heartbeat', 'close', 'takeover', 'expire')),
  settlement_request_id TEXT NOT NULL UNIQUE,
  expected_v1_run_digest TEXT NOT NULL,
  expected_v1_lockset_digest TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('reserved', 'settled', 'unknown')),
  result_v1_run_digest TEXT,
  result_v1_lockset_digest TEXT,
  outcome TEXT,
  authorization_digest TEXT,
  operator_required INTEGER NOT NULL DEFAULT 0 CHECK (operator_required IN (0, 1)),
  operator_required_at TEXT,
  mutation_process_proof_digest TEXT,
  observed_v1_state_digest TEXT,
  created_at TEXT NOT NULL,
  settled_at TEXT
);
CREATE TABLE claim_mutation_members (
  mutation_id TEXT NOT NULL REFERENCES claim_mutation_batches(mutation_id),
  claim_id TEXT NOT NULL REFERENCES claims(claim_id),
  expected_authority_claim_version INTEGER NOT NULL,
  expected_authority_lease_epoch INTEGER NOT NULL,
  PRIMARY KEY (mutation_id, claim_id)
);
CREATE TABLE legacy_fences (
  fence_id TEXT PRIMARY KEY,
  epoch INTEGER NOT NULL,
  claim_id TEXT NOT NULL REFERENCES claims(claim_id),
  request_digest TEXT NOT NULL,
  settlement_request_id TEXT UNIQUE,
  state TEXT NOT NULL,
  expected_remote_oid TEXT NOT NULL,
  remote_ref_digest TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  outcome TEXT,
  observed_remote_oid TEXT,
  settlement_digest TEXT,
  operator_required INTEGER NOT NULL DEFAULT 0 CHECK (operator_required IN (0, 1)),
  operator_required_at TEXT,
  operator_authorization_digest TEXT,
  effect_process_proof_digest TEXT
);
CREATE TABLE activation (
  authority_id TEXT PRIMARY KEY,
  operating_mode TEXT NOT NULL CHECK (operating_mode = 'shadow'),
  activation_state TEXT NOT NULL CHECK (activation_state IN ('unactivated', 'shadow-active')),
  descriptor_digest TEXT NOT NULL,
  activated_at TEXT NOT NULL,
  activation_receipt_digest TEXT NOT NULL
);
CREATE INDEX receipts_request_order ON receipts(authority_id, recorded_at);
CREATE INDEX fences_state ON legacy_fences(epoch, state);
```

## Delivery Dependency Graph

```text
plan-convergence run close + locks=0
  -> 1.1.2 binding -> Wave A child PR/main
  -> 1.2.0 binding -> Wave B1 root PR/main
  -> 1.3.0 binding -> Wave B2 root PR/main
  -> 1.4.0 binding -> Wave B3 root PR/main
  -> 1.5.0 binding -> Wave B4 root PR/main
  -> 1.6.0 binding -> Wave C root pointer PR/main
  -> 1.7.0 binding -> separately authorized host activation
  -> >=24h evidence + three lifecycles -> independent audit -> honest closeout
```

Each arrow is a hard gate. Never start or claim the next partition while the prior run is active or its PR/post-merge verification is incomplete.

## Binding QA Protocol

Every binding task below executes this protocol from the root of its fresh binding
clone. Before the commands, set `EXPECTED_SPEC_VERSION` to that task's version and
`EXPECTED_SURFACES_JSON` to a compact JSON array containing that task's exact
implementation/evidence surfaces. `BINDING_RUN_ID` is the active binding transaction.

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/plan/bet-ledger.py portfolio lint --strict
git diff --check
EXPECTED_SPEC_VERSION="$EXPECTED_SPEC_VERSION" \
EXPECTED_SURFACES_JSON="$EXPECTED_SURFACES_JSON" \
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import yaml

root = Path.cwd()
spec_path = root / "docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md"
digest = "sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest()
ledger = yaml.safe_load((root / "docs/plans/3y-bet-ledger.yaml").read_text())
bet = next(item for item in ledger["bets"] if item["id"] == "BET-Y1Q4-T10-145")
expected = json.loads(os.environ["EXPECTED_SURFACES_JSON"])
binding = bet["accepted_specifications"]
assert len(binding) == 1
assert binding[0]["spec_version"] == os.environ["EXPECTED_SPEC_VERSION"]
assert binding[0]["content_digest"] == digest
assert bet["write_surfaces"] == expected
assert bet["status"] == "candidate"
assert bet["completion_evidence"]["axes"]["operational"]["status"] == "NOT_PROVEN"
assert bet["completion_evidence"]["axes"]["value"]["status"] == "NOT_PROVEN"
assert bet["completion_evidence"]["overall_state"] == "evaluating"
assert bet["value_indicator_policy"] is False

module_path = root / "bin/plan/bet-ledger.py"
module_spec = importlib.util.spec_from_file_location("bet_ledger_contract", module_path)
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)
prepared = module.prepare_bet_execution(
    "BET-Y1Q4-T10-145", workspace=root, require_startable=False
)
assert prepared["spec_binding"] == binding[0]
assert prepared["work_packet"]["scope"]["write_surfaces"] == expected
assert prepared["work_packet_hash"].startswith("sha256:")
print(json.dumps({
    "spec_version": binding[0]["spec_version"],
    "spec_digest": digest,
    "work_packet_hash": prepared["work_packet_hash"],
    "write_surfaces": expected,
}, sort_keys=True))
PY
uv run --with pyyaml python bin/agent-workflow.py verify \
  "$BINDING_RUN_ID" --from-diff --execute
uv run --with pyyaml python bin/agent-workflow.py compliance \
  "$BINDING_RUN_ID" --json
make gac-local-gate
```

Expected: every command exits zero; the JSON prints the intended version, exact
computed digest, a fresh WorkPacket hash and exact surface array; compliance has no
finding other than the current active run. Stage/commit only the Spec, Ledger and that
version's exact waiver. Two read-only reviewers must approve the staged diff.

After the unique PR is created, run:

```bash
gh pr checks "$PR_NUMBER" --required --watch
SOURCE_SHA="$(git rev-parse HEAD)"
MERGE_SHA="$(gh pr view "$PR_NUMBER" --json mergeCommit --jq .mergeCommit.oid)"
test -n "$MERGE_SHA"
git fetch --no-tags origin main
git merge-base --is-ancestor "$MERGE_SHA" origin/main
for path in \
  docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md \
  docs/plans/3y-bet-ledger.yaml \
  "$BINDING_WAIVER"
do
  test "$(git rev-parse "$SOURCE_SHA:$path")" = "$(git rev-parse "$MERGE_SHA:$path")"
done
git show "$MERGE_SHA:docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md" \
  | shasum -a 256
```

Expected: required contexts are green, `MERGE_SHA` is the actual squash merge, every
final object equals the reviewed source object, and the printed Spec digest equals the
Ledger binding. Run post-merge GaC on an exact-merge clean clone, close the binding
run, prove live/stale locks are zero and retire the clone. If the hosting platform has
not produced a merge commit, stop before object comparison; never substitute PR head
for merged-main evidence.

## Bootstrap Publication Protocol

WP1 cannot use a v2 shadow receipt to publish its own implementation. Every plan,
binding, child, root and pointer delivery first attempts the effective v1 publication
path. If v1 permits it, use the normal managed lifecycle and all default hooks/gates.
If v1 rejects an otherwise valid managed clone solely because authority is fixed to
the integration Workspace, publication requires a still-live, operation-specific
Human or time-bounded delegated decision bound to the exact commit, tag, branch,
repository and one non-force attempt.

Record that decision outside the repository before the effect and disclose it in the
PR body. The record must state `changeset_claims_unverified`, the fixed-authority root
cause, exact commit/tag, expiry, no-retry condition and that it is not graduation or
value evidence. Default hooks, local tests, independent reviews and required PR checks
remain mandatory; force, `--no-verify`, history rewrite and a second attempt are not
authorized. An actual gate rejection or unknown remote result stops. With no live
operation-specific decision, stop and preserve the commit; do not treat this plan or
the accepted Spec as standing publication authority.

## Accelerated Iteration v1

The Human-approved accelerated model changes scheduling, not evidence quality:

- At most one Writer modifies the current WorkPacket.
- While a Writer is active, run two read-only roles in parallel: Contract Reviewer
  checks parent/child Spec, Ledger, code, interfaces, state machines, authority and
  paths; Verification Scout checks executable commands, RED/GREEN coverage, test
  paths, CI, rollback and recomputability.
- While the Writer is idle or waiting for CI, an optional read-only Next-wave Scout may
  research only the next binding/Wave's code seams, risks and order. It creates no
  Spec, BET, run, claim, commit, branch or PR.
- Reviewers never edit, start workflows, claim, fetch/push, operate PRs/services/DBs,
  mutate runtime or change user configuration. Every review binds the exact file
  SHA-256 or commit SHA; a target-byte change invalidates it.
- Each review is bounded to 20–30 minutes and returns only PASS, BLOCKED or
  UNPROVABLE, exact file/line evidence and a minimal correction. Conflicts are decided
  from the accepted Specs, current code and reproducible tests, never by majority. A
  tie-breaker is scoped only to the disputed point.
- The Writer applies the adjudicated minimum once and reruns the affected checks once;
  it does not enter an unbounded review loop. A next Writer starts only after local
  verification, independent review, required checks, exact-object post-merge proof and
  zero locks for the current version.
- Parallel research is allowed; two dependent binding/Wave implementations are not.

At each stage the orchestrator reports only: current Writer; parallel read-only tasks
and bound digest; passed/blocked items; next executable transaction; and remaining
critical-path time.

### Task 1: Confirm the current version 1.1.2 binding and converge this plan

**Status:** binding prerequisite completed; this plan-convergence transaction is in
progress. PR #3515 merged as
`da1ef9756b0c3f1bc370d808bfb461d11f3ad630`; its reviewed source and squash trees are
both `94354073b941b43e93f47d0365064725de82cce1`. The Spec, Ledger and waiver object
digests, WorkPacket, required checks, post-merge Governance Check and zero-lock
closeout were reproduced before the binding clone was retired. Versions 1.0.0,
1.1.0 and 1.1.1 are historical predecessors and are not current execution authority.

**Current binding files (read-only during plan convergence):**
- Read: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Read: `docs/plans/3y-bet-ledger.yaml`
- Read: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v112-binding.md`
- Modify: `docs/superpowers/plans/2026-09-10-claims-authority-bridge-wp1-shadow.md`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v112-plan-convergence.md`

**Interfaces:**
- Consumes: merged 1.1.2 binding and closed
  `20260910T150555Z-governance-state-mutation-3354a087`.
- Produces: one reviewed plan aligned to the existing 1.1.2 binding plus one scoped
  waiver. It does not replace or mutate the Spec, Ledger, WorkPacket, implementation
  or runtime.

- [x] **Step 1: Prove the binding run is closed and all locks are zero**

Run:

```bash
uv run --with pyyaml python bin/agent-workflow.py status --json
```

Expected and observed after #3515: no active binding run, `stale_locks=0`, `live_locks=0`.

- [x] **Step 2: Use a fresh full clone from a twice-read latest main for the binding transaction**

Historical evidence confirms `AGCP_REQUIREMENT_ITERATION_GATE=0` was used only on the
binding transaction's fresh unbound start; all claims, verification, Git, CI and
closeout used the default policy. The plan-convergence transaction repeats that rule
for its own unbound start and claims exactly the two files above. Do not repeat or
rewrite the binding transaction.

- [x] **Step 3: Confirm the complete non-union 1.1.2 replacement**

The merged binding has this exact semantic shape:

```yaml
# Spec frontmatter
spec_version: 1.1.2
status: accepted
bet_id: BET-Y1Q4-T10-145
implementation_authorized: true

# T10-145 current binding
write_surfaces:
  - projects/omo/src/omo/workflow/claims_authority.py
  - projects/omo/src/omo/workflow/lifecycle.py
  - projects/omo/tests/test_workflow_claims_authority_bridge.py
accepted_specifications:
  - spec_ref: repo://docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md
    spec_version: 1.1.2
    decision_ref: decision://accepted/BET-Y1Q4-T10-145
underlying_workflow: project-code-change
```

The required `content_digest` is
`sha256:bc1de057c28ce91aec5120396bcdedebb3b93b1289fcdc8c81387554efd47192`
and the recomputed WorkPacket is
`sha256:73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613`.
Both were computed from merged bytes and reproduced after merge. Future replacements
must repeat that calculation and fail unless the Spec and Ledger values are identical;
never hand-enter or predict a new digest. The accepted `12 days` appetite is elapsed
delivery time including the mandatory 24-hour window, never completion or value
evidence. This plan transaction must not edit those already-merged facts.

The 1.1.2 Spec replacement retains the frozen clarifications from the reviewed
1.1.1 plan and closes four additional gaps: production lifecycle calls only the
integration-root stdio broker;
claim addition/heartbeat/close/takeover/expiry use durable run-scoped mutation batches
covering every v1 claim, while versions/epochs remain broker-only and v1 bytes stay
unchanged; unknown batches/fences have separate operator markers and
authorization-bound resolution; remote double-read belongs only to descriptor-bound
`clone-lifecycle` and the broker performs no Git/`gh`; descriptor
`operating_mode=shadow` is distinct from
`activation_state=shadow-active`; degraded bootstrap publication never counts as v2
or graduation evidence; and graduation requires three distinct real workflow run IDs,
not fixtures. It also fixes the two auxiliary operator-evidence schemas, complete
activation closure, integration-root WorkPacket recomputation and idempotent
settlement confirmation. These are contract corrections, not extra Wave A write
surfaces.

- [x] **Step 4: Recompute and inspect the WorkPacket**

Run the repository `prepare_bet_execution()` helper and assert:

```python
assert packet["packet_id"] == "WP-BET-Y1Q4-T10-145"
assert packet["scope"]["write_surfaces"] == sorted([
    "projects/omo/src/omo/workflow/claims_authority.py",
    "projects/omo/src/omo/workflow/lifecycle.py",
    "projects/omo/tests/test_workflow_claims_authority_bridge.py",
])
assert packet["dependencies"]["required_packets"] == []
```

- [ ] **Step 5: Verify, review, publish and merge only the plan convergence**

Assert the plan names Spec version `1.1.2`, the exact merged Spec digest and current
WorkPacket above, and that `git diff --name-only` contains only the plan and this
transaction's waiver. Run default workflow verify/compliance, documentation checks,
full GaC and two digest-bound read-only reviews. Publish one normal non-force branch
and one unique PR. After required checks, squash merge, compare both final objects to
the reviewed source, run post-merge Governance Check, close the plan run, prove zero
locks and retire the clean clone. Only then may Task 2 start in a fresh child clone.

### Task 2: Establish the Wave A RED matrix and canonical models

**Files:**
- Create: `projects/omo/tests/test_workflow_claims_authority_bridge.py`
- Create: `projects/omo/src/omo/workflow/claims_authority.py`

**Interfaces:**
- Consumes: the public API, response envelope and schema frozen above.
- Produces: deterministic schemas, typed errors, safe path resolution, canonical encoding and RED evidence without production state.

- [ ] **Step 1: Write RED tests for canonical encoding and request identity**

Add tests with these exact assertions:

```python
def test_ac01_canonical_json_and_digest_are_stable():
    left = {"b": 2, "a": 1, "digest": "ignored"}
    right = {"a": 1, "b": 2}
    assert canonical_json(left) == '{"a":1,"b":2}'
    assert canonical_digest(left) == canonical_digest(right)
    assert canonical_digest(right).startswith("sha256:")

def test_ac02_request_id_reuse_with_different_payload_is_rejected(store):
    first = valid_observe_request(request_id="00000000-0000-4000-8000-000000000001")
    store.observe_claim(first)
    changed = {**first, "head_oid": "b" * 40}
    with pytest.raises(AuthorityError, match="REQUEST_ID_REUSE_MISMATCH"):
        store.observe_claim(changed)
```

- [ ] **Step 2: Write RED tests proving production resolution cannot be redirected**

```python
@pytest.mark.parametrize("name", ["HOME", "WORKSPACE_ROOT", "OMO_COORDINATION_DB", "CLAIMS_ROOT"])
def test_ac01_environment_cannot_redirect_production_authority(monkeypatch, name):
    monkeypatch.setenv(name, "/tmp/attacker")
    paths = resolve_authority_paths()
    account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    assert paths.integration_root == account_home / "Workspace"
    assert paths.store == account_home / "agents/_shared/runtime/omo-claims-authority-r0/store.sqlite3"

def test_ac01_symlink_or_unsafe_mode_fails_closed(tmp_path, monkeypatch):
    unsafe = tmp_path / "runtime"
    unsafe.mkdir(mode=0o777)
    monkeypatch.setattr(claims_authority.pwd, "getpwuid", fake_account_home(tmp_path))
    with pytest.raises(AuthorityError, match="AUTHORITY_STORE_UNSAFE"):
        resolve_authority_paths()
```

- [ ] **Step 3: Run the focused file and capture genuine RED**

Run:

```bash
cd projects/omo
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /opt/homebrew/bin/python3 -B -m pytest -q -p no:cacheprovider \
  tests/test_workflow_claims_authority_bridge.py
```

Expected: import failure because `omo.workflow.claims_authority` does not yet exist. Save the command, exit code and failing test names outside the repository review surface.

- [ ] **Step 4: Implement canonical models, validation and typed errors**

Implement `AuthorityError`, the frozen dataclasses, `canonical_json`, `canonical_digest`, UUIDv4 validation, 40-hex OID validation, schema allowlists, redaction and production path resolution. Digest preimages must remove only top-level `digest` and `signature` fields and use `ensure_ascii=True`, `allow_nan=False`, sorted keys and compact separators.

- [ ] **Step 5: Run the focused contract tests to GREEN**

Expected: canonical/path/schema tests pass; store and lifecycle tests may remain RED until Tasks 3–4.

- [ ] **Step 6: Establish the activation-witness RED matrix before any lifecycle mutation code**

Cover exact canonical states `absent(pristine only)`, `unactivated`, `prepared` and
`shadow-active`, plus missing-after-initialization, malformed body, unsafe
owner/mode/symlink, sequence mismatch, descriptor mismatch and rollback. Only the
first two may preserve v1 bootstrap when stdio is unavailable; every other state must
raise `AUTHORITY_ACTIVATION_WITNESS_INVALID` or `AUTHORITY_STORE_UNSAFE` before a v1
write. Prove the witness is read from the account-resolved fixed path and cannot
grant a claim, issue/settle a receipt or fence, authorize Git, or select a store.

- [ ] **Step 7: Add the auxiliary operator-evidence RED/GREEN matrix**

Add independent tests for the exact allowlisted fields of
`claims-operator-authorization/v1` and `claims-stopped-process-proof/v1`, 16 KiB
limits, 300-second authorization lifetime, account-derived fixed directories,
`0700`/`0600`, owner, regular-file, link-count-one and non-symlink requirements.
Cover expired, pre-marker, pre-authorization, redirected, copied, changed-digest,
wrong target/receipt/process/resolver/outcome and cross-target replay cases. Prove
both objects remain non-authoritative. Production resolution and activation stay RED
while either verifier is unbound; the only positive mechanics fixture uses a
`test:<uuid>` store and exact matching evidence.

- [ ] **Step 8: Add activation-closure and integration-root WorkPacket REDs**

Create one negative for every closure member: root commit, policy blob, child gitlink,
sorted critical dependency entry, managed-Python receipt/executable, operator verifier
and stopped-process verifier. Add missing-entry, wrong-kind, reordered-entry,
self-referential policy and two-read race variants; all must perform zero witness,
SQLite or high-water mutation. Separately construct a clone-local WorkPacket that is
internally valid but differs from the integration-root Ledger/Spec/Instruction rebuild
and require `WORK_PACKET_UNBOUND` with zero receipt. An identical replay of an already
committed request is the sole GREEN source-drift exception and adds no sequence or
state transition.

- [ ] **Step 9: Add settlement-confirmation RED/GREEN cases**

Test response loss after commit, response loss before commit and continued broker
unavailability as three independent cases. Only the identical
`settlement_request_id` and canonical body may be replayed. Assert the first two
return or commit the same settlement exactly once without re-running a v1 mutation or
Git effect; the third retains `reserved`/`publishing` and creates neither `unknown`
nor `operator_required`. Changed bytes under the same ID are
`REQUEST_ID_REUSE_MISMATCH`.

### Task 3: Implement the canonical SQLite store, chain and recovery rules

**Files:**
- Modify: `projects/omo/src/omo/workflow/claims_authority.py`
- Modify: `projects/omo/tests/test_workflow_claims_authority_bridge.py`

**Interfaces:**
- Consumes: canonical models from Task 2.
- Produces: atomic idempotent receipts, CAS claims/fences, high-water checks, one-tail recovery and three-backup rotation.

- [ ] **Step 0: Prove SQLite/WAL admission and activation crash ordering RED**

Reuse the existing pure SQLite-version safety predicate. An unsafe fresh runtime, an
unsafe pre-existing WAL store or failure to enter/read back `journal_mode=wal` must
raise `AUTHORITY_STORE_UNSAFE` before DDL, witness, high-water or backup mutation;
never execute `journal_mode=DELETE`. For activation, cover each crash boundary in
order: durable `prepared` witness → SQLite activation CAS/receipt → high-water update
→ atomic `shadow-active` replacement. A crash or disagreement at any boundary remains
fail-closed and only broker reconciliation of the same activation receipt may advance
the witness.

- [ ] **Step 1: Add RED tests for PRAGMAs and atomic receipt order**

```python
def test_ac02_store_pragmas_and_atomic_sequence(store):
    assert store.scalar("PRAGMA journal_mode").lower() == "wal"
    assert store.scalar("PRAGMA synchronous") == 2
    assert store.scalar("PRAGMA foreign_keys") == 1
    assert store.scalar("PRAGMA busy_timeout") == 5000
    r1 = store.observe_claim(valid_observe_request())
    r2 = store.observe_claim(valid_observe_request(request_id=uuid4_string()))
    assert r1["sequence"] == 1
    assert r2["sequence"] == 2
    assert r2["previous_receipt_digest"] == r1["receipt_digest"]
```

- [ ] **Step 2: Add RED tests for high-water and crash-tail behavior**

```python
def test_ac02_highwater_rollback_and_gap_fail_closed(store):
    receipt = store.observe_claim(valid_observe_request())
    write_test_high_water(store.test_paths.high_water, sequence=receipt["sequence"] + 2)
    with pytest.raises(AuthorityError, match="AUTHORITY_HIGHWATER_ROLLBACK"):
        store.verify_high_water()

def test_ac02_exact_one_tail_reconciles_but_two_tails_do_not(store):
    append_test_receipt_with_raw_sqlite(store.test_paths.store, count=1)
    assert store.reconcile_crash_tail()["reconciled"] is True
    append_test_receipt_with_raw_sqlite(store.test_paths.store, count=2)
    with pytest.raises(AuthorityError, match="AUTHORITY_HIGHWATER_GAP"):
        store.reconcile_crash_tail()
```

`fake_account_home`, `write_test_high_water` and
`append_test_receipt_with_raw_sqlite` are test-file fixtures that operate only under
`tmp_path`; they are not production exports or production path overrides.

- [ ] **Step 3: Add RED tests for lease/fence CAS and freeze semantics**

Assert stale broker claim versions, expired broker-owned 15-minute leases, fence
replay, second fence,
heartbeat/close/takeover/expiry while publishing, fence entry while a mutation
batch exists, crashed mutation batch, operator marker misuse and
settlement request reuse all fail with their exact typed codes. Prove
`begin-claim-mutation` and `settle-claim-mutation` reserve/settle the same run-wide
batch and exact sorted broker-member versions; a mismatched or partial result cannot
overwrite the batch.
Create one v1 run with at least two appended claims and prove heartbeat/close reserve
all members atomically, a one-member request is rejected, broker epochs advance for
every member, and the v1 YAML bytes contain no version/epoch field before or after.
Prove a heartbeat with unchanged run digest but changed lock-set digest is `applied`,
whereas unchanged run and lock sets are `rejected`; a missing/extra/changed lock makes
settlement or operator recovery ambiguous rather than guessed.
Prove an unknown mutation can be marked operator-required but cannot be released
without authorization, stopped-process proof and two equal complete v1 run/claims
plus lock-set reads and broker-member versions/epochs; ambiguous or partial reads
preserve the freeze.

Add exact settlement-request replay tests at the store boundary. A mutation batch
allocates one non-null unique `settlement_request_id`; a legacy fence allocates one
when it enters `publishing`. Reusing the same ID/body returns the committed response;
reusing the ID with changed bytes is rejected. A missing response never causes the
caller to repeat the underlying v1/Git effect or synthesize an operator marker.

- [ ] **Step 4: Implement `AuthorityStore` with one transaction boundary**

Use `BEGIN IMMEDIATE`; update `authority_meta`, claim/fence/mutation-batch member rows,
receipt row and idempotency response in the same transaction. Write high-water through
a same-directory temporary file, `fsync`, mode `0600` and `os.replace`. Never repair
more than one missing high-water tail.

- [ ] **Step 5: Implement evidence validation, activation closure and source-truth checks**

Implement the two auxiliary schema validators and fixed-path readers as internal
helpers in `claims_authority.py`; do not add a producer or path override. Bind every
field and filesystem invariant named in the frozen contract. In production, return
the typed missing/unbound-verifier error even when structural evidence is valid;
positive recovery is test-store-only.

Implement descriptor closure canonicalization and passwd-derived integration-root
double-read. Validate the exact root, policy, child gitlink, critical dependencies,
managed Python and both verifier digests before activation. For every production
request capable of issuing a receipt/fence or changing state, load the fixed root
helper, call `prepare_bet_execution(..., require_startable=False)`, compare the full
binding/state tuple and call `validate_work_packet_run()`. Check committed request
replay before this rebuild so an identical replay is read-only; no other request may
use clone-local WorkPacket authority.

- [ ] **Step 6: Implement lazy backup rotation**

Before first mutation of a UTC day or serial migration, create a SQLite backup plus
canonical manifest containing store digest, sequence, previous receipt digest,
descriptor digest and timestamp. Retain at most the newest three valid pairs. An
invalid pair is preserved and reported as incident evidence, never counted toward the
three valid pairs and never selected for automatic restore.

- [ ] **Step 7: Run store, evidence, closure and corruption negatives to GREEN**

Run the focused test file three times against fresh temporary stores. No test may touch the production authority directory.

### Task 4: Add deterministic comparison, status and the lifecycle shadow seam

**Files:**
- Modify: `projects/omo/src/omo/workflow/claims_authority.py`
- Modify: `projects/omo/src/omo/workflow/lifecycle.py`
- Modify: `projects/omo/tests/test_workflow_claims_authority_bridge.py`

**Interfaces:**
- Consumes: validated v1 result and run/claim/WorkPacket/affected-graph identities;
  production lifecycle reaches authority only through the canonical integration-root
  stdio client, while unit tests may use `_AuthorityStore.connect_for_test`.
- Produces: one shadow receipt/reference after v1 persistence plus serialized
  run-scoped mutation batches for heartbeat/close/takeover/expiry; v1 admission semantics
  remain byte-equivalent.

- [ ] **Step 1: Write RED comparison and projection tests**

```python
def test_ac03_shadow_cannot_change_effective_v1_decision(store):
    result = compare_decisions(V1Decision("deny", "claims_authority_mismatch"),
                               ShadowDecision("would_allow", "valid_managed_clone"))
    assert result["classification"] == "expected_managed_clone_difference"
    assert result["effective_claim_authority"] == "v1"
    assert result["instruction_capable"] is False

def test_ac07_status_is_redacted_and_stale_after_120_seconds(store, clock):
    status = store.authority_status(now=clock.now())
    assert status["instruction_capable"] is False
    assert not any(token in json.dumps(status) for token in (str(Path.home()), "github.com", os.getlogin()))
    clock.advance(seconds=121)
    assert store.authority_status(now=clock.now())["fresh"] is False
```

- [ ] **Step 2: Write the lifecycle byte-equivalence RED test**

Run the current `claim_run()` fixture once with the shadow adapter disabled and once with a fake successful adapter. Remove only the new sibling `claims_authority_shadow` field and assert canonical equality of every existing return/run/ledger field.

- [ ] **Step 3: Add the canonical integration-root client and post-v1 seam**

Resolve the integration root from `pwd.getpwuid(os.getuid()).pw_dir`, never from the
child checkout. Invoke the exact integration-root `bin/agent-workflow.py
claims-authority observe-claim --request-json -` through the descriptor-approved
managed Python with a bounded subprocess. The writer/child checkout is a client only:
production `lifecycle.py` must never import or call its clone-local
`claims_authority.observe_claim()` implementation.

Before every claim/lifecycle mutation, call the canonical stdio broker or, only when
that exact entry is unavailable, classify the account-resolved deny-only activation
witness. Verified pristine total absence or `unactivated` permits the existing v1
mutation; after `write_run()` and the claim ledger event, attach only a redacted
`shadow_unprovable:not_activated` sibling. A `prepared` or `shadow-active` witness,
missing witness after store/high-water initialization, malformed/unsafe body,
descriptor or sequence mismatch, or rollback rejects before any v1 write. The witness
never substitutes a positive broker response. Malformed or unexpected broker output
may be attached as `shadow_unprovable:CODE` only for a pre-activation mutation already
permitted by verified pristine/unactivated state; after preparation/activation it
fails closed before the mutation. Never roll back or rewrite a successful v1 claim.

- [ ] **Step 4: Fence every v1 claim mutation without importing another module**

Wrap the production lifecycle entrypoints for claim addition, heartbeat, close, claim
takeover and expiry/prune within `lifecycle.py`. After exact activation, each
operation must call
`begin-claim-mutation` before any local write and `settle-claim-mutation` after the
exact resulting v1 run bytes are persisted. Begin atomically covers every broker claim
member of that run; settlement updates only broker-owned versions/epochs and never
injects them into v1. The mutation batch and fence-entry CAS exclude one another. If
begin is unavailable after activation, perform no v1 mutation. If the local v1
mutation completes and the settlement response is lost, retry only the identical
settlement request ID/body; never repeat the v1 mutation. Continued broker
unavailability leaves the durable batch `reserved` and blocks further mutation. It
does not authorize fabricating `unknown`, an operator marker or a rollback claim.
Before activation, preserve byte-equivalent bootstrap behavior and record only an
unprovable shadow observation.

Hold the existing per-run `run_update_lock` across run/lock snapshot → broker begin
CAS → immediate exact snapshot revalidation → existing v1 mutation → final run/lock
snapshot → settle batch. Add that same lock boundary to direct close. Treat the local
lock as best-effort R0 exclusion: if its 30-second stale behavior admits a second
process, the durable run-wide broker CAS must reject that process before any v1 write.
Never pass `force=True` through the post-preparation/activation path; a force request
against a live lock must leave v1 bytes unchanged. A newly appended v1 claim becomes
a new broker member only at settlement; fence entry and another batch cannot
interleave. This changes no existing v1 payload/return fields and does not widen the
WorkPacket to `lifecycle_locks.py`.

If the local mutation completes but the broker durably settles the request as
`unknown`, do not retry the mutation. Only that durable unknown receipt may be marked
operator-required. A separately authorized `resolve-claim-mutation-unknown` call may
classify the already-observed v1 outcome only after a later accepted descriptor binds
both evidence verifiers and exact evidence plus two equal complete run/claims,
lock-set and broker-member version/epoch reads pass. Version 1.1.2 production remains
fail-closed; the positive path is test-store-only. Resolution never performs or
reverses the lifecycle mutation.

For stale-lock pruning, replace the `lifecycle.py` re-export with a selected-candidate
wrapper; do not call the existing `prune_stale_locks()`, because it rescans and could
delete a newly stale, unreserved lock. Under all affected run-update locks acquired in
stable run-ID order, freeze one initial `scan_locks()` candidate set, record every
candidate path/kind/content digest, begin one batch per affected run, revalidate each
exact candidate without a new discovery scan, delete only those unchanged candidates,
settle all batches, then release locks in reverse order. A new, changed or unreserved
stale lock is left untouched for the next explicit prune. Do not modify
`lifecycle_locks.py`; if exact selected deletion cannot be implemented from
`lifecycle.py`, stop and amend the accepted Spec/write surface instead of leaving a
bypass.

Add RED races proving that a process admitted after a 30-second local-lock unlink
obtains no second broker batch and performs zero v1 writes, a force request leaves a
live lock byte-identical, a candidate changed after the frozen scan survives, and the
legacy discovery-style `prune_stale_locks()` function is never called.

- [ ] **Step 5: Prove Wave A cannot publish**

Monkeypatch `subprocess.run`, Git and `gh` entrypoints to fail the test if called from `claims_authority.py`. Assert every Wave A fence fixture has `publishable=false` and no production activation row is created.

- [ ] **Step 6: Run child regressions and child CI**

Run:

```bash
cd projects/omo
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /opt/homebrew/bin/python3 -B -m pytest -q -p no:cacheprovider \
  tests/test_workflow_claims_authority_bridge.py \
  tests/test_workflow_start_preflight.py tests/test_workflow_locks.py
python3 -m compileall -q src/omo/workflow/claims_authority.py src/omo/workflow/lifecycle.py
cd ../..
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /opt/homebrew/bin/python3 -B -m pytest -q -p no:cacheprovider \
  tests/projects/omo/workflow/test_lifecycle_hash.py
git diff --check
```

- [ ] **Step 7: Publish child-first and stop**

Commit only the three Wave A paths and run the child project's required CI. If the
existing v1 authority permits the child delivery, use its normal managed lifecycle.
If it rejects solely because of the fixed authority root, require a recorded exact
commit, one-time Human/time-bounded-delegated degraded publication; disclose the gap
and exclude the publication from graduation evidence. Otherwise stop. Create one
child PR, wait for post-merge CI and prove the merge commit is reachable from
authoritative child `main`. Close the current 1.1.2 Wave A run and release every lock. Do not update
the root gitlink yet.

### Task 5: Replace the binding with version 1.2.0 for Wave B1

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v120-wave-b1-binding.md`

**Interfaces:**
- Consumes: the exact merged Wave A child commit, its post-merge CI receipt and a closed 1.1.2 Wave A run.
- Produces: one non-union 1.2.0 WorkPacket containing exactly the six Wave B1 root paths.

- [ ] **Step 1: Re-read child main and prove Wave A completion**

Read the authoritative `projects/omo` remote twice. Assert the merged child commit is
an ancestor of child main, the three child objects match the reviewed PR, child
post-merge CI succeeded, the 1.1.2 Wave A workflow is closed and every Wave A lock is zero.

- [ ] **Step 2: Start a fresh binding transaction from then-latest root main**

Use a fresh managed full clone. Any requirement-iteration bypass is allowed only on
the unbound `governance-state-mutation` start and must be quoted in the version-specific
waiver. Claim exactly the three files listed for this task.

- [ ] **Step 3: Make a complete 1.2.0 replacement**

Set the Spec version to `1.2.0`, preserve accepted/candidate/non-value semantics and
replace the current WorkPacket surfaces with exactly:

```text
bin/agent-workflow.py
bin/gac/agent-clone.py
bin/gac/clone-lifecycle.py
tests/test_agent_workflow.py
tests/test_clone_lifecycle.py
.omo/_truth/registry/swarm-coordination.yaml
```

Set `underlying_workflow: project-code-change`. Compute the final Spec digest by
command, write it into the single current accepted binding, rebuild the WorkPacket,
and prove the prior hash is rejected and none of the Wave A paths remain.

- [ ] **Step 4: Validate and merge only the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.2.0`,
the six Wave B1 paths and the Task 5 waiver, then close the binding run with locks
zero.

### Task 6: Implement Wave B1 root shadow adapter and the only fence-aware effect owner

**Files:**
- Modify: `bin/agent-workflow.py`
- Modify: `bin/gac/agent-clone.py`
- Modify: `bin/gac/clone-lifecycle.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_clone_lifecycle.py`
- Modify: `.omo/_truth/registry/swarm-coordination.yaml`

**Interfaces:**
- Consumes: the future child stdio contract, v1 workflow/claim result, immutable clone descriptor and current `cmd_integrate()` transaction.
- Produces: lazy observation, descriptor-bound calls and a mandatory one-fence wrapper around the existing Git effect after activation.

- [ ] **Step 1: Add RED tests for lazy bootstrap and v1 equivalence**

Cover missing child code, broker timeout, absent activation and malformed response.
Each case must return `shadow_unprovable:TYPED_CODE`, leave the existing v1 result
canonically equal, and perform no activation/store initialization or Git effect.

```python
def test_b1_unactivated_adapter_preserves_v1_and_does_not_publish(fake_broker, fake_git):
    fake_broker.reply(code="not_activated")
    before = legacy_integrate_fixture()
    after = run_with_shadow(before)
    assert strip_shadow_sibling(after) == before
    assert after["claims_authority_shadow"]["code"] == "not_activated"
    assert fake_git.calls == []
```

- [ ] **Step 2: Add RED tests for the descriptor-bound invocation**

The integration root, child module, Python executable and real Git executable must
come from verified descriptor closure. Caller environment, cwd, PATH and request JSON
must not redirect them. Two authority reads that disagree return
`AUTHORITY_DESCRIPTOR_MISMATCH`; no fence or Git follows.

- [ ] **Step 3: Add the root CLI subparser and bounded stdio adapter**

Before any `sys.path` mutation, `omo`/`ecos` import or other repository import, inspect
`sys.argv` using only the standard library. If and only if the first command is
`claims-authority`, resolve and verify the descriptor closure, load the broker module
from the exact committed integration-root path, dispatch one frozen verb, emit one
canonical response and exit. The ordinary workflow CLI follows its existing import
path only for non-broker commands.

Implement every frozen verb under `claims-authority`, including claim-mutation and
operator-resolution verbs. Use the repository's managed Python resolution, an
explicit timeout, one JSON stdin body and one JSON stdout body. Lazy import failure is
typed and non-blocking only before exact activation. Never parse stderr as authority
and never accept a caller-supplied store/root path.

- [ ] **Step 4: Bind agent-clone projections without making them authority**

Add only a redacted, timestamped projection containing authority ID, descriptor
digest, sequence, freshness and comparison reference. The canonical broker rereads
the clone identity independently. A stale or mismatched projection can be rebuilt but
cannot overwrite broker state or authorize publication.

- [ ] **Step 5: Add the post-activation fence state machine to `cmd_integrate()`**

Preserve the current Git argv byte-for-byte and keep all existing identity/changeset/
HEAD race checks. Immediately before the one real push:

1. verify a v1 allow result;
2. require no active run-wide mutation batch, then have `clone-lifecycle` perform the
   descriptor-bound remote double-read and request one fence bound to the
   independently reread v1 snapshot digest, broker claim version/lease, exact HEAD,
   expected remote OID and remote-observation digest;
3. immediately reread that same v1 snapshot/broker version, have the effect owner
   produce a fresh remote-observation pair, and atomically enter `publishing`; reject
   if either local or remote observation differs, and freeze
   close/takeover/expiry/heartbeat/second-fence changes;
4. execute the existing canonical push once;
5. have the descriptor-bound effect owner reread the remote ref twice and canonicalize
   the observation pair;
6. let the broker validate that pair and settle the same fence as `success`,
   `rejected` or `unknown` without running Git itself;
7. perform idempotent PR lookup-or-create only after a settled successful push.

Before activation, preserve the bootstrap path exactly and require no fence. After
activation, broker/fence failure must produce zero Git/PR effects. An `unknown`
settlement permits read-only query of that same fence/ref only; it never retries push.

- [ ] **Step 6: Add race, replay and canonical-argv RED tests**

Test expiry, replay, second fence, stale broker claim version, mutation batch versus
fence-entry races, close/takeover/expiry/heartbeat during publishing, epoch drain
between v1 snapshot and Git, remote OID drift, timeout, malformed response,
operator-required marking, authorized unknown resolution and idempotent repeated
settlement. Patch the Git executable and assert exactly one unchanged push argv in the
sole GREEN case. An authorization digest without stopped-process proof and two equal
remote reads must not resolve an unknown fence. Add the parallel negative for an
unknown claim-mutation batch: missing authorization, live process, unequal/partial v1
run reads or ambiguous broker-member versions must preserve the batch and block fence
entry.

- [ ] **Step 7: Register one broker, not another dispatcher**

Update `swarm-coordination.yaml` only with the descriptor/projection/fence contract,
R0 cooperative label, v1-effective flag and redacted observer fields. Do not register
a daemon, port, new dispatcher, instruction-capable Dashboard control or WP2.

- [ ] **Step 8: Verify, publish and close Wave B1**

Run:

```bash
uv run pytest -q tests/test_agent_workflow.py tests/test_clone_lifecycle.py
python3 -m py_compile bin/agent-workflow.py bin/gac/agent-clone.py bin/gac/clone-lifecycle.py
python3 bin/gac/harness-compliance-check.py --report
make gac-local-gate
git diff --check
```

Also execute the pre/post-activation pair with fake Git, verify a six-path-only diff,
obtain two reviews, merge one PR after required contexts, prove exact final-tree
objects, close the 1.2.0 run and release all locks.

### Task 7: Replace the binding with version 1.3.0 for Wave B2

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v130-wave-b2-binding.md`

**Interfaces:**
- Consumes: merged and post-merge-verified B1 with a closed run.
- Produces: one WorkPacket containing exactly the nine B2 effect-convergence paths.

- [ ] **Step 1: Prove B1 exactness and zero active locks**

Verify the B1 merge SHA and six final objects, required contexts, default post-merge
GaC, no stale/live B1 locks and an unchanged canonical push argv.

- [ ] **Step 2: Replace the binding, never union it**

Set version `1.3.0`; use the exact B2 nine-path list in the canonical Spec; compute and
double-check the final Spec digest; preserve candidate/evaluating and NOT_PROVEN
states. The version waiver must explicitly state that effect-owner convergence does
not authorize unrelated history rewriting. Disabling the legacy submit entrypoint's
automatic rebase is allowed only because immutable-successor delegation must stop
before publication when its base moved.

The 1.3.0 Spec replacement must also correct the 1.0.0 bootstrap assumption for
`gac-worktree submit`: a Git worktree cannot satisfy `cmd_integrate()`'s independent
managed-clone identity/common-dir invariant. The accepted 1.3.0 disposition is
therefore proposal-only: produce an immutable patch/base/source digest and a typed
`MANAGED_SUCCESSOR_REQUIRED` handoff; a separately created managed full successor
replays that patch under its own identity/claims and calls canonical integrate. Do not
weaken the independent-clone invariant or silently cast a worktree as a managed
attempt.

- [ ] **Step 3: Validate, independently review and merge the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.3.0`,
the nine Wave B2 paths and the Task 7 waiver. Require a fresh WorkPacket hash, then
close the binding run before implementation starts.

### Task 8: Converge every local tracked publication entry on `clone-lifecycle integrate`

**Files:**
- Modify: `bin/gac/gac-worktree.sh`
- Modify: `bin/gac/git-retry.sh`
- Modify: `bin/gac/gitlink-drift-protect.py`
- Modify: `bin/sync-submodules.sh`
- Modify: `bin/ssot/sync-submodules-push.sh`
- Modify: `scripts/wait-and-bump-cockpit.sh`
- Modify: `tests/test_gac_worktree_claim_pasw.py`
- Modify: `tests/unit/gac/test_submodule_pointer_transaction.py`
- Create: `tests/test_git_publication_effect_owner.py`

**Interfaces:**
- Consumes: B1 canonical integrate owner and fence contract.
- Produces: zero publication effects in every compatibility entry. Actual publication
  occurs only after a proposal is replayed in a distinct managed full successor that
  independently calls canonical integrate.

- [ ] **Step 1: Build a fake publication-effect harness and capture RED**

The fake records Git `push`, Git Data API writes, `gh pr create`, branch/ref mutation,
nested child push and `--no-verify`. Execute each of the six production entrypoints
and prove current RED calls before changing code. Each named entrypoint gets a
separate test; do not pass by source-string deletion alone.

- [ ] **Step 2: Convert `gac-worktree submit` into a managed-successor proposal**

Keep its user-facing validation and proposal preparation, but remove its direct push
and PR creation. It must not invoke `clone-lifecycle integrate` from the worktree.
Emit a deterministic patch digest, source commit, base commit, changed-path digest and
typed `MANAGED_SUCCESSOR_REQUIRED` instruction. A new managed full clone must revalidate
and replay the patch under a separate workflow transaction; this script neither
creates that clone nor publishes it. It must not rebase, merge, pull or absorb upstream
history; if the base moved, return the same typed successor instruction before any
effect.

- [ ] **Step 3: Reject generic push in `git-retry.sh`**

Return `PUBLICATION_OWNER_REQUIRED` before executing Git for the `push` verb. Preserve
read-only fetch/ls-remote and any existing bounded network handling; do not add an
automatic publication retry or fallback push.

- [ ] **Step 4: Make drift and submodule helpers detection-only**

`gitlink-drift-protect.py --fix` emits a canonical proposal containing repository,
path, current/target OID and the managed remediation entrypoint, but performs no push.
Both submodule sync scripts report missing/unreachable child commits and exit nonzero
without commit, push or `--no-verify`. Preserve worktree/index bytes on failure.

- [ ] **Step 5: Freeze the completed Cockpit helper as read-only**

Keep `--validate` for historical checks. Every mutating mode reports already integrated
or stops with `PUBLICATION_OWNER_REQUIRED` before checkout, commit, push or PR.

- [ ] **Step 6: Prove zero alternate effects and a verifiable successor proposal**

Run the new fake-effect suite against every mode and edge argv. Assert only
`gac-worktree submit` emits the complete replay proposal; none of the six files can
invoke integrate or independently reach a remote/ref/PR writer. In a separate
test-only managed-clone fixture, replay that proposal and prove canonical integrate
accepts the resulting identity/claims without relaxing its local `.git`/common-dir
checks.

- [ ] **Step 7: Verify and publish Wave B2**

Run:

```bash
uv run pytest -q tests/test_gac_worktree_claim_pasw.py \
  tests/unit/gac/test_submodule_pointer_transaction.py \
  tests/test_git_publication_effect_owner.py
bash -n bin/gac/gac-worktree.sh bin/gac/git-retry.sh \
  bin/sync-submodules.sh bin/ssot/sync-submodules-push.sh \
  scripts/wait-and-bump-cockpit.sh
make gac-local-gate
git diff --check
```

Inventory the repository for tracked push/PR writers and reconcile every hit. Merge
one nine-path PR after reviews/required checks, verify exact objects and close the
1.3.0 run with locks zero.

### Task 9: Replace the binding with version 1.4.0 for Wave B3

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v140-wave-b3-binding.md`

- [ ] **Step 1: Verify B2 post-merge and publication inventory**

Require exact B2 objects, green checks and no local entrypoint capable of independent
Git/PR effects. Stop if the inventory is incomplete or a B2 lock remains.

- [ ] **Step 2: Install the exact nine-path 1.4.0 replacement**

Use the B3 path list in the Spec, one current binding, computed Spec digest and fresh
WorkPacket hash. Remove every B2 surface. Preserve all completion/value fields.

- [ ] **Step 3: Review and merge only the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.4.0`,
the nine Wave B3 paths and the Task 9 waiver. Close its run before B3 implementation.

### Task 10: Close Git Data API and Git-wrapper publication bypasses

**Files:**
- Modify: `bin/gac/gh-api-push.sh`
- Modify: `bin/_registry/scripts/governance/gh-api-push.yaml`
- Modify: `bin/gac/git-shim`
- Modify: `bin/gac/swarm-git`
- Modify: `docs/plans/AGENT-BRIEF.md`
- Modify: `tests/integration/test-git-shim.sh`
- Modify: `tests/unit/gac/test_immutable_writer_git_policy.py`
- Modify: `tests/test_swarm_discipline.py`
- Modify: `tests/test_git_publication_effect_owner.py`

**Interfaces:**
- Consumes: B1's descriptor-bound real Git inside the canonical fenced owner.
- Produces: fail-closed wrappers/API helper and updated operator guidance.

- [ ] **Step 1: Capture RED for every write-shaped API/wrapper route**

Cover Git Data API blob/tree/commit/ref calls, ordinary push, force push,
force-with-lease, atomic create-if-absent, `--no-verify`, option permutations and both
wrappers. Fake `gh`/Git must record the current undesired effect.

- [ ] **Step 2: Make `gh-api-push.sh` reject before any write endpoint**

After non-effectful argument validation, return `PUBLICATION_OWNER_REQUIRED` before
the first POST/PATCH. Remove `force=true` execution reachability. Update its registry
entry to non-publishing/proposal-only; preserve a diagnostic/read-only description if
still useful.

- [ ] **Step 3: Make both wrappers reject every push**

Delete the atomic first-publication exception. All push forms return the same stable
typed rejection. Do not expose an exact-argv escape hatch. Canonical integrate uses
the descriptor-bound real Git binary and never loops through these wrappers.

- [ ] **Step 4: Update the active Agent Brief**

Replace any direct API/wrapper publication instruction with the managed
`clone-lifecycle integrate` route. State that proposal creation and publication are
separate and that unknown outcomes are query-only.

- [ ] **Step 5: Run bypass tests and source inventory**

```bash
bash tests/integration/test-git-shim.sh
uv run pytest -q tests/unit/gac/test_immutable_writer_git_policy.py \
  tests/test_swarm_discipline.py tests/test_git_publication_effect_owner.py
python3 bin/ssot/script-registry.py validate
make gac-local-gate
git diff --check
```

Assert fake executables observed zero ref/blob/tree/commit/push/PR writes. Merge one
B3 PR after reviews and required contexts, verify exact objects, close the 1.4.0 run
and release all locks.

### Task 11: Replace the binding with version 1.5.0 for Wave B4

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v150-wave-b4-binding.md`

- [ ] **Step 1: Verify B3 exact main state and closeout**

Prove all wrapper/API negatives on the merge tree, required checks green and zero B3
locks.

- [ ] **Step 2: Install the five-path 1.5.0 replacement**

Use exactly the four workflows and one test file listed in the Spec. Recompute the
Spec digest and WorkPacket. Remove every B3 path and keep candidate/evaluating plus
NOT_PROVEN truth unchanged.

- [ ] **Step 3: Validate and merge only the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.5.0`,
the five Wave B4 paths and the Task 11 waiver, including closeout and retirement.

### Task 12: Convert cloud publication automations to read-only proposals

**Files:**
- Modify: `.github/workflows/submodule-autobump.yml`
- Modify: `.github/workflows/reusable-submodule-bump-pr.yml`
- Modify: `.github/workflows/submodule-freshness-gatekeeper.yml`
- Modify: `.github/workflows/omo-autopilot.yml`
- Create: `tests/test_github_publication_effect_owner.py`

**Interfaces:**
- Consumes: current workflow inputs and drift/debt detection outputs.
- Produces: uploaded proposal artifacts and failing/neutral diagnostics without remote publication.

- [ ] **Step 1: Add static and simulated RED tests**

Parse all four YAML files and reject `contents: write`, write-capable checkout tokens,
`git commit`, `git push`, `gh pr create`, ref-write API calls and automatic PR actions.
Require a named proposal artifact containing base/head/ref and remediation metadata.

- [ ] **Step 2: Convert submodule workflows**

Preserve checkout, SHA resolution, reachability and drift detection. Replace bump,
branch, commit, push and PR steps with deterministic proposal generation and artifact
upload. A detected stale/unreachable gitlink remains visible and may fail the check;
it must not self-heal.

- [ ] **Step 3: Convert OMO autopilot**

Remove `peter-evans/create-pull-request` and all write permissions. Preserve read-only
debt analysis and emit a proposal artifact. Audit `omo ledger` separately: if it
mutates governed state, run it only in a throwaway staging directory or replace it
with a read-only query; never call a state mutation under a proposal-only label.

- [ ] **Step 4: Validate permissions, semantics and artifacts**

```bash
uv run pytest -q tests/test_github_publication_effect_owner.py
python3 - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path('.github/workflows').glob('*.yml')):
    yaml.safe_load(path.read_text())
print('workflow_yaml_ok')
PY
make gac-local-gate
git diff --check
```

Exercise representative fixtures and prove useful proposal content plus zero ref/PR
effect. Merge a five-path-only PR, verify the merge tree and required contexts, close
the 1.5.0 run and release all locks.

### Task 13: Replace the binding with version 1.6.0 for the root pointer

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v160-root-pointer-binding.md`

- [ ] **Step 1: Prove all four root waves are authoritative**

For B1–B4, verify merge SHA, exact reviewed objects, required contexts and post-merge
GaC. Re-run the publication inventory and require one owner. Verify the Wave A child
commit still exists on authoritative child main.

- [ ] **Step 2: Install a one-path 1.6.0 replacement**

The only write surface is `projects/omo`; set the workflow to the repository's
submodule-pointer transaction. Compute the Spec digest, build a fresh WorkPacket and
prove no implementation/evidence path remains.

- [ ] **Step 3: Validate and merge only the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.6.0`,
the sole `projects/omo` surface and the Task 13 waiver. Release its locks before the
pointer run.

### Task 14: Advance the root `projects/omo` pointer last

**Files:**
- Modify: `projects/omo`

**Interfaces:**
- Consumes: authoritative child main containing Wave A and root main containing B1–B4.
- Produces: one reachable root gitlink and a cross-layer final tree.

- [ ] **Step 1: Freeze the target child OID**

Read child main twice, require equality, prove it contains the Wave A merge and record
the exact OID. Stop if child main moves during the transaction or the commit is not
reachable without local-only objects.

- [ ] **Step 2: Update only the gitlink through the canonical transaction**

Use the repository submodule-pointer transaction. No source, Spec, Ledger, evidence
or generated file may enter the diff. Perform a full recursive checkout from a clean
clone of the candidate root tree.

- [ ] **Step 3: Run root reachability and cross-layer canaries**

```bash
BASE_SHA="<exact PR base SHA>"
git submodule update --init --recursive
uv run --with pyyaml python bin/gac/check-submodule-rewind.py \
  --range "$BASE_SHA" HEAD --no-write-debt
uv run --with pyyaml python bin/ssot/submodule-reachability-gate.py \
  --source head --require-main --json
uv run pytest -q tests/test_agent_workflow.py tests/test_clone_lifecycle.py \
  tests/test_git_publication_effect_owner.py \
  tests/test_github_publication_effect_owner.py
make gac-local-gate
git diff --check
```

Require the repository's current full require-main count rather than hard-coding a
stale count; record both count and exact target OID.

- [ ] **Step 4: Merge the one-gitlink PR and prove reachability again**

After required contexts, squash merge. Fresh-clone the exact merge SHA recursively,
prove the gitlink is on child main, rerun cross-layer canaries and post-merge GaC,
then close the 1.6.0 run and retire its clone.

### Task 15: Replace the binding with version 1.7.0 for Wave D evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_truth/governance-evidence/waiver-2026-09-10-claims-authority-bridge-wp1-v170-wave-d-binding.md`

- [ ] **Step 1: Prove repository delivery is complete but not operationally proven**

Verify A/B1–B4/C exact merge evidence, root/child reachability, one effect owner and
full RED matrix. Keep operational/value `NOT_PROVEN` and overall `evaluating`.

- [ ] **Step 2: Install the exact two-path evidence WorkPacket**

Set version `1.7.0` and replace surfaces with exactly:

```text
.omo/_truth/governance-evidence/claims-authority-bridge-wp1-shadow-graduation.json
.omo/_knowledge/retros/BET-Y1Q4-T10-145.md
```

Compute and verify the final Spec digest and WorkPacket hash. Do not pre-create
positive evidence, write `done`, add `done_at` or change completion/value truth.

- [ ] **Step 3: Validate and merge only the binding**

Execute every command and assertion in `Binding QA Protocol` with version `1.7.0`,
the exact two evidence paths and the Task 15 waiver. Close its binding run before any
host operation.

### Task 16: Activate the exact R0 descriptor under a separately recorded host decision

**Repository files:** None.

**Host surfaces:**
- Runtime store: account-resolved `agents/_shared/runtime/omo-claims-authority-r0/store.sqlite3`
- High-water: account-resolved `agents/_shared/runtime/omo-claims-authority-r0/highwater.json`
- Backups: account-resolved `agents/_shared/backups/omo-claims-authority-r0/`
- External operation record: an attempt-local, non-repository decision and receipt bundle.

**Interfaces:**
- Consumes: exact root main SHA, policy blob, child gitlink, sorted critical
  dependency entries, managed-Python receipt and executable digests, exact
  operator-authorization and stopped-process verifier digests, plus closure-bound
  Ledger, accepted Spec, Instruction Pack and `bin/plan/bet-ledger.py` helper.
- Produces: one activation CAS with descriptor `operating_mode=shadow`, independent
  `activation_state=shadow-active`, and an immutable activation receipt.

- [ ] **Step 1: Obtain or record operation-specific authority**

The repository binding does not authorize host mutation. Record the exact direct or
still-live time-bounded delegated decision, surfaces, rollback and expiry outside the
repository before invoking activation. If no valid decision exists, stop; do not
reinterpret the accepted Spec as host authority.

Version 1.1.2 intentionally binds no production evidence verifier. Before this task
can execute, a later accepted binding must name the exact principal-decision and
independent stopped-process observer verifier interfaces and closure-bind their
implementation digests. Missing, placeholder, file-presence-only or self-attested
verifier identity stops activation. This Task does not itself authorize or invent
those implementations.

- [ ] **Step 2: Preflight the production path without mutation**

Resolve account home through `pwd`, walk every existing ancestor with `lstat`, reject
symlinks/wrong owner/group-world write, and assert neither CLI nor environment can
redirect the target. Check whether DB and high-water are both absent or both form a
valid chain; asymmetric or corrupt state stops without repair.

- [ ] **Step 3: Build and double-read the descriptor**

Read root main twice and require equality. Compute canonical digests for root commit,
policy blob, child gitlink, every sorted critical dependency entry, managed-Python
receipt and executable, both accepted verifier implementations, Ledger, accepted
Spec, Instruction Pack and `bin/plan/bet-ledger.py`. Read every input again
immediately before activation and require byte equality. Each entry has only canonical
`path`, `kind` and `object_oid_or_digest`; the policy blob does not embed the
descriptor's self-digest.

- [ ] **Step 4: Execute exactly one activation CAS**

Invoke the implemented `activate-shadow` stdio verb with one canonical request. A
successful response must say `operating_mode=shadow`,
`activation_state=shadow-active`, `security_level=cooperative-r0`,
`effective_claim_authority=v1`, `instruction_capable=false`, and return a receipt
whose digest verifies against the store chain. `shadow-active` is a lifecycle state,
never a descriptor operating-mode enum. A repeated identical request is idempotent;
any different descriptor returns `AUTHORITY_DESCRIPTOR_MISMATCH`.

- [ ] **Step 5: Verify pre/post activation behavior**

Before activation receipt time, archived fixtures prove bootstrap effects were not
fenced. After that exact time, a v1-allowed fake publication without a fence produces
zero Git; a valid fresh fence permits exactly one canonical fake Git effect. Run
redacted status twice and require equal sequence/digests plus freshness.

- [ ] **Step 6: Start the observation clock only if every prerequisite is true**

Record `window_started_at` from broker time, not wall-clock narration. If any RED test,
descriptor read, path check, observer read or activation receipt is missing, no window
starts and the BET remains candidate/evaluating.

## Foreground Observation Protocol

The 24-hour observer is one foreground, single-writer process, not a daemon, service,
LaunchAgent, cron job or repository artifact. It writes only under the current managed
attempt, outside `ws/`:

```text
attempt/evidence/claims-authority-window-UTC_TIMESTAMP/samples.jsonl
attempt/evidence/claims-authority-window-UTC_TIMESTAMP/observer-start.json
attempt/evidence/claims-authority-window-UTC_TIMESTAMP/observer-end.json
```

The 1.7.0 binding transaction must already be closed with all locks zero before this
process starts. The observer starts no workflow, owns no root-gate or repository path
lock and consumes no built-in Agent slot. The fresh 1.7 evidence Writer is created
only after a window ends and only while materializing the two repository reports.

Create the directory with `umask 077`; files are `0600`. `observer-start.json` binds
the activation receipt digest, descriptor digest, exact root main SHA, observer
command digest, monotonic start value and broker start time. It contains no raw home,
repository remote, username or payload. The process invokes only:

```text
uv run --with pyyaml python INTEGRATION_ROOT/bin/agent-workflow.py claims-authority status --json
```

once every 60 monotonic seconds with a 30-second subprocess timeout. Each canonical
JSONL record has `sample_index`, `broker_time`, `authority_sequence`, `fresh`,
`descriptor_digest`, `status_digest`, `previous_sample_digest`, `sample_digest`,
`process_monotonic_seconds`, `return_code` and a redacted `error_code`. Compute
`sample_digest` over the record without that field, using the canonical JSON contract.
Open the JSONL with `O_APPEND`, perform one write per record, then `fsync`. There is
exactly one observer writer; reviewers tail/read only.

The observer emits read-only checkpoint summaries outside the repository:

| Broker duration | Minimum valid samples | Result label |
|---:|---:|---|
| 30 minutes | 30 | `SMOKE_PASS` |
| 2 hours | 120 | `PROVISIONAL_PASS` |
| 6 hours | 360 | `SUSTAINED_PASS` |
| 24 hours | 1440 | `GRADUATION_PASS` |

Every checkpoint additionally requires maximum sample gap at most 120 seconds,
unchanged descriptor, nondecreasing authority sequence, valid receipt/high-water
chain and zero unexplained differences, false allows or observer blindness. The first
three labels are diagnostics only: they cannot change completion/value/overall,
materialize WP2 or shorten the 24-hour gate. They may schedule unrelated work that
uses a different BET/repository and shares neither Ledger/Spec/root-gate nor this
Writer.

The process exits on the first timeout, nonzero result, malformed/noncanonical JSON,
`fresh=false`, descriptor change, sequence rollback, broker-time rollback, sample
digest mismatch or a broker-time/monotonic gap over 120 seconds. It writes
`observer-end.json` atomically with `decision=INVALIDATED`, the last valid sample
digest and typed reason, but does not restart, backfill, interpolate or repair. A host
restart, sleep, process death or missing end record invalidates the interval. A new
foreground observer may start only after prerequisites are rechecked; it gets a new
directory and a new full 24-hour clock while the failed directory remains immutable.

After at least 86,400 broker seconds, the process writes `observer-end.json` with
`decision=GRADUATION_PASS` only if there are at least 1440 valid samples, the final
status is fresh and the sample chain is continuous. An independent verifier rereads
every JSONL line, recomputes every digest,
requires indices without gaps, nondecreasing authority sequence, identical descriptor,
maximum adjacent broker/monotonic gap at most 120 seconds, end minus start at least
86,400 seconds and an activation time no later than the first sample. A successful
observer window proves continuity only; lifecycle/RED/effect-owner acceptance remains
separate.

### Task 17: Observe 24 hours, exercise three lifecycles and decide graduation honestly

**Files:**
- Create or Modify: `.omo/_truth/governance-evidence/claims-authority-bridge-wp1-shadow-graduation.json`
- Create or Modify: `.omo/_knowledge/retros/BET-Y1Q4-T10-145.md`

**Interfaces:**
- Consumes: continuous broker receipts and exact activation descriptor.
- Produces: a non-terminal report or a complete acceptance/retro record; never a value claim.

- [ ] **Step 1: Start the lock-free observation interval**

Prove the 1.7.0 binding run is closed, live/stale locks are zero and no T10-145
evidence Writer exists. Start only the `Foreground Observation Protocol` outside the
clone. Read-only reviewers may tail its digest-bound samples; they may not write
authority, hold a workflow lock or refresh a failed sample.

- [ ] **Step 2: Exercise the three mandatory lifecycle classes**

Use three different, real production workflow run IDs after activation. Each must bind
an accepted WorkPacket and canonical production-authority receipt chain; `test:*`,
copied records, simulated runs and fixture-only results do not count.

1. Valid managed-clone run: v1 fixed-root deny plus v2 `would_allow`, classified only
   as `expected_managed_clone_difference`, with zero publication.
2. V1-allowed legacy run: under its own exact publication authorization, obtain one
   fence, enter publishing, execute one real canonical publication effect, reread the
   remote twice and settle the same fence. If no safely authorized real legacy
   publication occurs in the window, AC-08 remains unproven.
3. Expiry/replay run: issue a real production legacy fence for a separately scoped
   non-publishing workflow, let broker time expire it, then present that same fence
   again and prove zero effect/no replacement. It must not reuse either prior run ID.

Record request/receipt/digest references, not raw usernames, paths, remotes or payloads.
Fake Git tests from B1 remain required engineering evidence for interlock negatives,
but cannot substitute for these three operational lifecycle receipts.

- [ ] **Step 3: Monitor continuously for at least 24 broker hours**

Execute the `Foreground Observation Protocol` exactly. The final repository report
summarizes start/end, sample count, sequence range, chain/high-water integrity,
lifecycle IDs, classifications, false-allow count, unexplained count, observer gaps
and reset history.

- [ ] **Step 4: Reset on any invalidating event**

An unexplained difference, false allow, chain/high-water/identity/descriptor drift,
observer blindness over 120 seconds, broker clock rollback or alternate publication
owner invalidates the window. Preserve the failed interval, write a non-terminal
report, correct only through a separately scoped transaction, and start a new full
24-hour window after all prerequisites pass again.

- [ ] **Step 5: Evaluate every acceptance criterion and WP2 absence**

Map CAB-WP1-AC-01 through AC-13 one-to-one to immutable evidence. Require zero
unresolved fences and zero unresolved claim-mutation batches. Search the Ledger,
Specs, runs and locks to prove WP2 is absent. Confirm operational/value remain
`NOT_PROVEN` and `value_indicator_policy=false`.

- [ ] **Step 6: Open the fresh 1.7.0 evidence Writer only after the interval ends**

Only after `GRADUATION_PASS` or a preserved invalidated/non-terminal interval exists,
create one fresh bound evidence run from then-latest main and claim exactly the two
Task 17 paths. Keep one Writer; bind the external observation-directory digest and
decision. If another Ledger/Spec/root-gate Writer is active, wait rather than holding
this run through unrelated work.

- [ ] **Step 7: Write the evidence and retrospective**

The JSON report uses stable keys:

```json
{
  "schema": "claims-authority-wp1-graduation/v1",
  "bet_id": "BET-Y1Q4-T10-145",
  "descriptor_digest": null,
  "window": {"started_at": null, "ended_at": null, "continuous_seconds": 0},
  "sequence": {"first": null, "last": null, "chain_ok": false, "highwater_ok": false},
  "samples": {"total": 0, "expected_difference": 0, "equivalent": 0, "unexplained": 0, "false_allow": 0},
  "lifecycles": {"managed_clone": false, "legacy_regression": false, "expiry_replay": false},
  "observer": {"max_gap_seconds": 0, "repeatable": false},
  "checkpoints": {"smoke": false, "provisional": false, "sustained": false, "graduation": false},
  "acceptance": {},
  "decision": "NOT_READY"
}
```

The illustrative values above are a schema fixture, never positive evidence. Populate
only from verified receipts. The retro records deviations, recovery burden, operator
decisions, mechanism debt and whether the 12-day appetite was re-baselined.

- [ ] **Step 8: Perform independent audit and transition conservatively**

Two read-only reviewers independently recompute the receipt chain, descriptor digest,
window duration, maximum observation gap, three lifecycle results, source inventory
and AC matrix. Only if all criteria are directly proven may a separately scoped BET
truth transition mark engineering complete/overall done. This plan does not pre-authorize
that transition. If any criterion is missing, merge only an honest non-terminal report
and keep candidate/evaluating.

- [ ] **Step 9: Close, verify and retire**

Run evidence schema/lint, Ledger lint, workflow verify/compliance, full GaC, required
PR contexts and exact post-merge object checks. Close the 1.7.0 evidence run, confirm
zero locks and retire only the successful clean clone. Preserve production store,
high-water, backups and immutable receipts.

## Named RED/GREEN Fixture Matrix

The test names below are contractual. A worker may factor shared fixtures but may not
rename away, combine or skip an individual attack. `child` means
`projects/omo/tests/test_workflow_claims_authority_bridge.py`; `root-b1` means
`tests/test_clone_lifecycle.py` or `tests/test_agent_workflow.py`; `local-effects`
means `tests/test_git_publication_effect_owner.py`; `cloud-effects` means
`tests/test_github_publication_effect_owner.py`.

| Spec §11 case | Exact test function | Wave / file |
|---|---|---|
| clone-local or arbitrary external authority root | `test_red_authority_root_is_account_resolved` | A / child |
| hand-created, copied or modified run/receipt | `test_red_unverifiable_run_or_receipt_is_rejected` | A / child |
| environment, cwd or CLI redirects production store | `test_red_caller_cannot_redirect_production_store` | A / child |
| broker unavailable with pristine total absence or verified unactivated witness | `test_green_broker_unavailable_pristine_or_unactivated_preserves_v1_bytes` | A / child |
| broker unavailable with prepared/active/invalid/rollback/missing-after-init witness | `test_red_broker_unavailable_prepared_active_invalid_rollback_blocks_v1_write` | A / child |
| crash between prepared witness, activation CAS, high-water and active replacement | `test_red_activation_crash_boundaries_require_same_receipt_reconciliation` | A / child |
| unsafe SQLite or failure to enter WAL before store creation | `test_red_unsafe_sqlite_wal_admission_has_zero_mutation` | A / child |
| store/high-water/backup/clone symlink escape | `test_red_authority_paths_reject_every_symlink_escape` | A / child |
| wrong owner or unsafe mode | `test_red_authority_paths_reject_wrong_owner_or_mode` | A / child |
| actor/attempt/repository/branch/HEAD mismatch | `test_red_identity_tuple_mismatch_is_denied` | A / child |
| identity/manifest/readiness digest drift | `test_red_identity_receipt_digest_drift_is_denied` | A / child |
| unbound/stale WorkPacket or scope overflow | `test_red_work_packet_binding_and_scope_are_exact` | A / child |
| clone-local WorkPacket is self-consistent but integration-root rebuild differs | `test_red_integration_root_work_packet_rebuild_rejects_clone_drift` | A / child |
| affected graph/path mismatch | `test_red_affected_graph_path_mismatch_is_denied` | A / child |
| broker claim version/lease race, expiry, takeover or replay | `test_red_claim_cas_lease_and_takeover_races_are_denied` | A / child |
| local update lock is unlinked after 30 seconds while first batch remains reserved | `test_red_local_lock_timeout_overlap_performs_zero_second_v1_write` | A / child |
| post-activation force request targets an existing live lock | `test_red_post_activation_force_preserves_live_lock_and_v1_bytes` | A / child |
| broker clock rollback over 30 seconds | `test_red_broker_clock_rollback_issues_nothing` | A / child |
| fence consumed twice or refreshed after expiry | `test_red_fence_replay_and_expiry_issue_no_replacement` | A / child |
| claim mutation or second fence while publishing | `test_red_publishing_claim_is_frozen_until_settlement` | A / child |
| legacy epoch closes between v1 snapshot and Git | `test_red_epoch_drain_race_stops_before_git` | B1 / root-b1 |
| graduation with unresolved fence | `test_red_graduation_rejects_every_unresolved_fence_state` | A / child |
| request ID reused with changed payload | `test_red_request_id_reuse_with_changed_payload_is_denied` | A / child |
| settlement response lost after commit | `test_green_settlement_confirmation_after_commit_replays_response_only` | A / child |
| settlement response lost before commit | `test_green_settlement_confirmation_before_commit_commits_once` | A / child |
| broker unavailable during settlement confirmation | `test_red_settlement_confirmation_unavailable_preserves_reserved_or_publishing` | A / child |
| expected remote OID changes before effect | `test_red_remote_oid_drift_stops_before_git` | B1 / root-b1 |
| descriptor closure or managed-Python receipt drift | `test_red_descriptor_or_python_receipt_drift_is_unprovable` | B1 / root-b1 |
| root, policy, gitlink, dependency, Python or verifier closure differs | `test_red_activation_closure_binds_every_dependency_and_verifier` | A / child |
| policy embeds self-referential descriptor digest | `test_red_descriptor_rejects_policy_self_reference` | B1 / root-b1 |
| two authority reads disagree | `test_red_double_read_disagreement_issues_no_fence` | B1 / root-b1 |
| store rollback, high-water gap or broken chain | `test_red_store_chain_or_highwater_drift_fails_closed` | A / child |
| test authority receipt reaches production verifier | `test_red_test_authority_receipt_is_never_publishable` | A / child |
| R0 receipt labeled adversarial | `test_red_r0_receipt_cannot_claim_adversarial_security` | A / child |
| projection overwrites authority | `test_red_projection_cannot_mutate_authority_store` | B1 / root-b1 |
| projection disagrees with authority | `test_green_projection_drift_rebuilds_projection_only` | B1 / root-b1 |
| v1 authorizes a managed clone during WP1 | `test_red_v1_managed_clone_allow_is_forbidden` | A / child |
| v1 authorizes publication after future cutover | `test_red_future_cutover_rejects_v1_publication_fixture` | A / child |
| v1 run/claim is copied or promoted into v2 | `test_red_v1_record_cannot_be_promoted_to_v2` | A / child |
| v2 changes the effective v1 verdict | `test_red_shadow_result_never_changes_effective_v1` | A / child |
| shadow hook changes push argv/adds push/creates PR | `test_red_shadow_adapter_cannot_change_publication_effect` | B1 / root-b1 |
| B1/B2/B3/B4/C requires fence before activation | `test_red_pre_activation_delivery_preserves_bootstrap` | B1 / root-b1 |
| broker/fence failure followed by Git | `test_red_broker_or_fence_failure_has_zero_effect` | B1 / root-b1 |
| tracked local script/API/wrapper publishes outside owner | `test_red_local_entries_have_zero_alternate_publication_effect` | B2+B3 / local-effects |
| tracked cloud workflow publishes outside owner | `test_red_cloud_workflows_have_zero_publication_effect` | B4 / cloud-effects |
| valid legacy claim, exact HEAD and fresh fence | `test_green_legacy_fence_executes_one_canonical_effect` | B1 / root-b1 |
| identical repeated settlement | `test_green_repeated_settlement_returns_same_receipt` | A / child |
| operator evidence is expired, redirected, malformed or cross-target replayed | `test_red_operator_evidence_schema_path_time_and_target_are_exact` | A / child |
| structurally valid production evidence precedes verifier binding | `test_red_production_operator_recovery_requires_bound_verifiers` | A / child |
| exact test-store evidence settles its own unknown only | `test_green_test_store_operator_recovery_settles_same_unknown_only` | A / child |
| valid managed clone shadow comparison | `test_green_managed_clone_is_expected_difference_without_publication` | A+B1 / child and root-b1 |

For the two inventory rows, parameterize a case for every exact production path in
B2, B3 and B4 and print the case ID in test output. A single aggregate source scan is
not sufficient. The final effect-owner inventory additionally scans all tracked shell,
Python and workflow files for newly introduced writers and requires each candidate
either to be the canonical owner or to have a named negative fixture above.

The following implementation-boundary tests are also mandatory even though they
refine rather than replace a Spec §11 row:

| Boundary | Exact test function | Wave / file |
|---|---|---|
| production lifecycle never imports clone-local broker | `test_red_lifecycle_calls_only_integration_root_broker` | A / child |
| broker CLI dispatch precedes every repository import | `test_red_claims_authority_dispatch_is_standard_library_first` | B1 / root-b1 |
| run-wide mutation batch and fence entry exclude each other | `test_red_claim_mutation_and_fence_entry_are_mutually_exclusive` | A+B1 / child and root-b1 |
| unknown resolution lacks authorization/process/remote proof | `test_red_unknown_resolution_requires_all_operator_proofs` | A+B1 / child and root-b1 |
| mutation recovery lacks authorization/process/v1 proof | `test_red_unknown_mutation_resolution_requires_all_operator_proofs` | A+B1 / child and root-b1 |
| run-wide mutation omits one of several v1 claims | `test_red_run_mutation_batch_requires_every_claim_member` | A / child |
| broker-owned versions leak into v1 YAML/result | `test_red_broker_versions_never_mutate_v1_bytes` | A / child |
| heartbeat proof ignores lock-only mutation | `test_red_heartbeat_settlement_binds_complete_lockset_digest` | A / child |
| prune rescans and deletes an unreserved candidate | `test_red_prune_deletes_only_frozen_revalidated_candidates` | A / child |
| broker attempts Git/`gh` remote read | `test_red_broker_has_no_remote_transport` | A / child |
| effect-owner remote pair differs or is unbound | `test_red_remote_observation_pair_must_match_descriptor_and_oid` | B1 / root-b1 |
| Git worktree is never cast as managed clone | `test_red_worktree_submit_emits_successor_proposal_only` | B2 / local-effects |
| activation enum/state are distinct | `test_red_shadow_active_is_not_an_operating_mode` | A+B1 / child and root-b1 |
| backup manifest omits/mismatches descriptor | `test_red_backup_manifest_binds_descriptor_digest` | A / child |
| committed request replay is read-only despite later source drift | `test_green_committed_request_replay_skips_source_dependent_mutation` | A / child |

## Full RED-to-Acceptance Traceability

| RED family | Primary task | Acceptance | Mandatory proof |
|---|---:|---|---|
| Authority/path redirection and unsafe filesystem | 2–3, 16 | AC-01 | negative path/owner/mode/symlink tests plus host preflight |
| Idempotency, receipt chain, CAS, high-water and backup | 3 | AC-02 | fresh-store replay, corruption negatives and three rotations |
| Activation witness outage and crash reconciliation | 2–4 | AC-02, AC-14 | named witness-state and four-boundary crash tests; only pristine/unactivated may bootstrap |
| SQLite WAL admission | 3 | AC-02, AC-04 | unsafe-runtime/pre-existing-store/failed-WAL tests prove zero mutation and no DELETE fallback |
| Local-lock overlap, force and prune races | 4 | AC-02, AC-04 | durable broker CAS rejects the second writer; live locks/v1 bytes and changed candidates survive |
| Shadow non-authority and legacy fence | 4, 6 | AC-03, AC-13 | byte-equivalence and pre/post activation fake-effect pair |
| Complete attack matrix and false allow | 2–4, 6, 8, 10, 12 | AC-04 | one named negative mutation per Spec §11 row |
| Ordered repository delivery | 4–14 | AC-05 | child/B1/B2/B3/B4/C merge and exact-object receipts |
| Stable comparison pairs | 4, 17 | AC-06 | repeated immutable fixture report |
| Redacted, non-instructional fresh observer | 4, 16–17 | AC-07 | status contract tests and max-gap calculation |
| Three lifecycle classes | 17 | AC-08 | independently verified lifecycle receipt references |
| Continuous 24-hour clean window | 17 | AC-09 | broker-time interval, zero gaps/unexplained/false allow |
| Cooperative R0 and value isolation | every task | AC-10 | schema, registry and Ledger assertions |
| WP2 non-materialization | every task, 17 | AC-11 | repository/Ledger/run/lock absence scan |
| Single publication effect owner | 8, 10, 12 | AC-12 | dynamic fake-effect suite plus tracked-source inventory |
| Deny-only activation witness boundary | 2–4, 16 | AC-14 | all witness states plus activation crash ordering |
| Auxiliary operator evidence provenance and non-authority | 2–4 | AC-15 | exact schema/path/time/target REDs and test-store-only positive |
| Complete activation dependency closure | 2–3, 6, 16 | AC-16 | per-entry drift/race negatives, exact pre-activation double-read, and closure-match GREEN proof: not a repeatable pytest fixture — the only positive evidence is the single, non-replayable Task 16 Step 4 host activation CAS |
| Integration-root WorkPacket authority | 2–4 | AC-17 | clone-local drift RED, canonical rebuild GREEN and committed replay exception |
| Idempotent settlement confirmation | 2–4, 6 | AC-18 | lost-before/lost-after/unavailable cases with underlying effect count at most one |

## Verification Matrix

| Layer | Required before each merge | Additional final proof |
|---|---|---|
| Scope | WorkPacket hash, exact claims, diff path equality | every version is a replacement, never a union |
| Unit/TDD | named RED captured, focused GREEN | full §11 negative matrix |
| Static | compile/shell/YAML/registry lint, `git diff --check` | tracked effect-owner inventory |
| Workflow | default verify and compliance | all runs closed and locks zero |
| Governance | full local GaC | exact merge-tree post-merge GaC |
| Repository | one non-force branch publication and one PR | source-to-squash patch/object equivalence |
| Submodule | child main ancestry and post-merge CI | recursive root clone and require-main |
| Runtime | none before Task 16 | descriptor receipt, store/chain/high-water/path safety |
| Operational | no claim before 24 hours | three lifecycles, continuous window and independent audit |
| Value | always isolated | remains `NOT_PROVEN`; no personal-value metric ingestion |

## Stop Conditions and Recovery Decisions

Stop the current transaction without expanding scope when any of these occurs:

- Spec digest, WorkPacket hash, identity, affected graph, broker claim version or exact path differs;
- a prior run/lock/PR is still active or a version is skipped/unioned;
- child/root main changes after its guarded double-read;
- a required context fails with real steps, an exact object differs, or a gitlink is unreachable;
- production path ownership/mode/symlink, descriptor, chain, high-water or clock is unsafe;
- a v2 result changes v1, produces a false allow, or becomes instruction-capable;
- an unfenced post-activation Git/PR effect or any alternate publication owner is observed;
- a push outcome is unknown, a fence or claim-mutation batch is unresolved, or
  an observer gap exceeds 120 seconds;
- the current 1.1.2 Spec digest, WorkPacket, three-path scope or accepted 12-day appetite cannot be reproduced exactly.

For a moving main, create a new immutable successor from the new exact main; do not
rebase, merge or rewrite an immutable writer. For a transient network error before an
effect, preserve the attempt and diagnose before any new bounded decision. For an
unknown publication effect, query only the same fence/ref and never retry. Every
failed interval, run, receipt and review remains evidence; it is never rewritten into
a success.

## Rollback Execution Order

1. Record the rollback decision and stop activation/observation/fence issuance. First
   create a fresh, complete, non-union stop/freeze successor binding with
   `implementation_authorized=false` and a newly computed safe WorkPacket. That
   binding authorizes no rollback write; never restore version 1.1.1 as current
   authority.
2. Block new publication while any fence or claim-mutation batch is unresolved;
   settle or separately escalate only that same object.
3. Preserve the production DB, WAL/high-water, backups and observation artifacts read-only.
4. Give each actual rollback partition its own later fresh accepted binding, exact
   rollback paths, Spec digest and WorkPacket with
   `implementation_authorized=true`; reject every historical hash and never union
   forward and rollback surfaces. After the partition closes, replace it with the
   next rollback-specific binding or a new `implementation_authorized=false`
   stop/freeze binding before pausing.
5. Revert B4 cloud convergence, then B3 wrappers/API, B2 local entries and B1 root
   adapter in separate reviewed root PRs.
6. Revert the root gitlink only to a child commit reachable from authoritative child main.
7. Revert the Wave A child code in its own child PR, then update the root pointer last if required.
8. Run the full pre-WP1 regression and publication inventory before restoring legacy effect routes.
9. Leave WP1 candidate/evaluating and WP2 absent; a future attempt requires fresh bindings and a fresh 24-hour window.

## Execution Handoff

Execute one task at a time with `subagent-driven-development` or `executing-plans`.
The orchestrator owns binding order, exact path claims, guarded main reads, final-tree
verification and closeout. A writer owns only the current WorkPacket. A separate
read-only reviewer checks design/contract and another checks tests/gates. No worker may
start the next task merely because its local tests pass.

Before every task, the orchestrator must print and archive: exact base SHA, Spec
version/digest, WorkPacket hash, claimed paths, active lock count, expected output,
rollback and stop condition. After every task, it must archive: actual diff paths,
RED/GREEN evidence, reviewer verdicts, source/merge SHA, required contexts, exact-object
comparison, post-merge verification, closeout and clone-retirement disposition.

For Wave A, the immutable handoff is Spec `1.1.2` at
`sha256:bc1de057c28ce91aec5120396bcdedebb3b93b1289fcdc8c81387554efd47192`
and WorkPacket
`sha256:73b4d19af02326d33d0969e7c85aba83a4fbffa762615dbb798e1572b0a8e613`.
After this plan-convergence PR closes, create a fresh successor from then-current
authoritative child main and replay only the reviewed three-path patch from blocked
run `20260910T110304Z-bet-execution-74895d83`. The old clone remains immutable
evidence. Do not rebase it, resume its run, reuse its WorkPacket receipt or treat its
passing prototype tests as delivered implementation.
