---
title: Capability Federation Contract v1
lifecycle: contract
owner: architecture-governance
last_updated: 2026-08-23
type: doc
---

# Capability Federation Contract v1

## 1. Purpose

This contract joins specification binding, Workspace skills, Agent Workflow,
MCP/BOS tools, workers, providers and external transports into one inspectable
execution chain without creating another registry, scheduler or completion
authority.

“Unified” means a shared discovery envelope, identity chain, failure vocabulary
and receipt boundary. Native owners still load and execute each capability.

The target chain is:

```text
accepted spec binding
  -> skill and workflow resolution
  -> capability discovery
  -> observation and admission
  -> native adapter execution
  -> OMO evidence and independent verification
  -> human-facing Cockpit projection
```

Finding a record, observing an online process, loading metadata, receiving an
exit code or seeing a UI success state never advances a WorkflowRun by itself.

## 2. Existing authorities

The federation layer reads the following owners and stores only references and
digests. It does not copy their executable fields into a new source of truth.

| Concern | Authority | Federation operation |
|---|---|---|
| Accepted specification | accepted `spec_binding` in the BET/WorkPacket chain | `resolve`, `revalidate` |
| Agent Workflow lifecycle | `.omo/_truth/registry/agent-workflows/` and the OMO runner | `inspect`, `suggest`, brokered `start` |
| Workspace skill instructions | `.agents/skills/<id>/SKILL.md` plus the active client inventory | `inspect`, exact `read` |
| Provider declaration | `.omo/_truth/registry/capability-providers.yaml` | `discover`, `observe` |
| Worker admission and transport policy | `.omo/_truth/registry/workers.yaml` | `inspect`, brokered `dispatch` |
| BOS routing | `projects/agora/etc/bos-services.yaml` and Agora runtime reconciliation | `load`, brokered `invoke` |
| MCP inventory | native MCP server metadata and bounded runtime `initialize`/`tools/list` | `inspect`, brokered `call` |
| Machine service lifecycle | `.omo/_truth/registry/services.yaml` | `inspect`, `observe` |
| MOF tools | `.omo/_truth/registry/mof-capabilities.yaml` | `inspect` |
| Static human-facing capability map | `docs/generated/capability-registry.yaml` | read-only projection |
| Evidence, verification and completion | OMO Workflow Mesh and orchestration contract | `record`, `verify`, `close` |

`docs/generated/capability-registry.yaml` is a deterministic discovery
projection. Its `exists` fields and generated counts are not runtime health,
admission, authorization or invocation evidence. A partial clone must be
reported as `unprovable`; it must not silently retire a capability.

## 3. Federation envelope

A read-only resolver MAY return `capability-federation-envelope/v1`:

```yaml
schema: capability-federation-envelope/v1
kind: spec | skill | workflow | mcp_server | mcp_tool | bos_service | worker | provider | service | plugin
id: <native stable id>
source_ref: <repository-relative or opaque native reference>
source_digest: sha256:<digest>
source_schema: <native schema and version>
native_owner: <ecos | omo | agora | runtime | cockpit | client>
lifecycle: <native lifecycle value>
states:
  declared: true | false | unknown
  discovered: true | false | unknown
  observed: true | false | unknown
  healthy: true | false | unknown
  admitted: true | false | unknown
  authorized: true | false | unknown
  invoked: true | false | unknown
  evidenced: true | false | unknown
adapter:
  kind: <native adapter kind>
  target_ref: <opaque native target>
restrictions:
  mutation: forbidden
  invocation: forbidden
```

Rules:

1. The envelope is deterministic for the same source bytes and selectors.
2. Absolute machine paths, prompts, transcripts, environment values, tokens,
   account identifiers and provider output are forbidden.
3. Missing or uninitialized authority sources produce `unprovable`; they do not
   produce `absent`, `retired` or `deprecated`.
4. State fields are independent. No state is inferred from a later or earlier
   field.
5. The envelope carries no command, argv, Python module or arbitrary
   `entrypoint` that a generic executor can run.
6. Query ambiguity fails closed. Only an exact stable ID may cross into a native
   adapter.

## 4. Native adapter semantics

There is no universal `load` or universal shell executor. The common facade
selects a kind-specific adapter and each adapter keeps a narrow verb set.

| Kind | Read-only verbs | Mutating/executing verb | Explicitly forbidden |
|---|---|---|---|
| Spec | `resolve`, `revalidate` | none | invoke a spec as a tool |
| Skill | `inspect`, exact `read` | client-native application | copying machine inventory into Git |
| Agent Workflow | `inspect`, `suggest` | OMO brokered `start/claim/verify/closeout` | direct run-state writes |
| MCP server/tool | `inspect`, bounded `initialize`, `tools/list` | native `tools/call` after admission | executing registry strings |
| BOS service | `load` with runtime reconciliation | Agora native `invoke` | bypassing Agora admission |
| Worker | `observe` | OMO `dispatch/collect/interrupt` | worker self-declaring Done |
| Provider | `discover`, bounded health/quota observation | native worker/compute adapter | observation implying admission |
| Service | `inspect`, health observation | service owner lifecycle command | discovery starting a daemon |
| Plugin | `discover`, `inspect` | client-owned install/enable workflow | automatic install/update |

All process adapters use code-owned fixed argv, `shell=False`, a bounded timeout,
explicit cancellation and residue checks. Registry strings are display or
compatibility metadata only.

## 5. Execution binding and trace

Discovery receipts and execution receipts are different artifacts. An execution
request MUST bind the existing causal identities where they apply:

```text
principal_id / actor_id
  -> workflow_run_id
  -> packet_id + packet_hash
  -> assignment_id
  -> dispatch_id
  -> delivery_attempt_id
  -> native capability id + source digest
  -> external_task_id or invocation_id
  -> EvidenceRecorded
  -> VerificationReceipt
```

`trace_id` correlates these records but does not replace any existing identity.
It is generated from a canonical, privacy-safe binding projection. Prompt text,
timestamps, UI metadata, provider names and transport selection do not alter a
WorkPacket hash.

The compatible receipt sequence is:

```text
capability-resolution-receipt/v1
  -> capability-admission-receipt/v1
  -> native-execution-receipt/v1
  -> OMO EvidenceRecorded
  -> VerificationReceipt
```

A resolution receipt keeps `invocation.allowed=false`. A native execution
receipt proves only the measured native action and cleanup result. Only OMO may
promote eligible evidence, and only independent verification may produce
`WorkflowVerified`.

### 5.1 B4-B resolution binding

B4-B adds a deterministic binding only to the existing read-only exact
capability resolver. It is neither admission nor an execution request. The
caller supplies a JSON object with exactly these causal identities:

```yaml
correlation_id: <existing correlation id>
workflow_run_id: <existing workflow run id>
packet_id: <existing packet id>
packet_hash: sha256:<64 lowercase hex characters>
assignment_id: <existing assignment id>
dispatch_id: <existing dispatch id>
actor_id: <stable actor id>
delivery_attempt_id: <one delivery attempt id>
```

Use the existing public command; its CLI owns bounded input-file reading and
redacted error-receipt orchestration, while the standard-library-only
`lib/capability_trace_binding.py` owns deterministic canonicalization,
validation, binding construction and replay checking. The input file is read,
never copied into a registry, Workflow Mesh or runtime store:

```bash
uv run --with pyyaml python bin/capability-sync.py find \
  --id mcp-tool:example:inspect \
  --binding-json /path/to/causal-binding.json
```

The binding requires `--id`, an exact successful resolution and a readable
generated projection. It rejects unknown fields (including prompts, provider
or transport labels), empty identifiers, absolute paths and non-SHA-256 packet
hashes. Every non-hash identity is at most 256 characters and uses only
A-Za-z0-9._:@/-; whitespace, control characters and .. are rejected. A bound
receipt additionally requires the projection's complete canonical schema,
owner and writer metadata. Legacy compatibility input remains discoverable
without a binding, but is source_unprovable for B4-B. The receipt contains only
the allowlisted identities, stable capability ID/kind/native owner/adapter kind,
the opaque
`generated:capability-registry/v1` source reference and the projection digest.
Its `resolution_source.authority` is the machine-readable literal `projection`:
it is not an SSOT or a native source proof.
It deliberately omits adapter targets, command/argv, native module paths,
provider or transport choices, prompts, transcripts, environment/account data,
timestamps and output.

`trace_id` is the SHA-256 digest of the canonical binding plus capability and
projection-digest projection; `receipt_digest` covers the canonical complete
receipt. A pure replay validator recomputes both and rejects tampering,
invocation/evidence/verification promotion, or any value-indicator promotion.
The receipt always fixes:

```yaml
invocation:
  allowed: false
states:
  invoked: false
  evidenced: false
  independently_verified: false
value_indicator_policy: false
```

Resolution failure remains fail-closed. A missing, unreadable or non-canonical
projection is reported as `source_unprovable`; unmatched and non-unique exact
selectors are respectively `resolution_not_found` and `resolution_ambiguous`.
Neither result is evidence of absence, retirement, successful dispatch or
completion.

**Boundary:** B4-B resolves and binds a generated projection only. The B4-B
library remains pure; `capability-sync.py` retains registry I/O and CLI
compatibility. B4-C is responsible for native inspect/load and native
source/version/digest proof. B4-D is responsible for kind-specific execution
receipts, cleanup and the OMO evidence handoff. Neither B4-B nor B4-C may
invoke a capability, write Workflow Mesh evidence, or create a value/human
outcome.

### 5.2 B4-C static native inspection

B4-C adds one non-executing public operation for exact Skill, Workflow, MCP and
BOS IDs:

```bash
uv run --with pyyaml python bin/capability-sync.py inspect \
  --id skill:example \
  --binding-json /path/to/causal-binding.json

uv run --with pyyaml python bin/capability-sync.py inspect \
  --id mcp-tool:example:inspect \
  --resolution-receipt-json /path/to/b4-b-resolution-receipt.json
```

Skill and Workflow are not represented by the generated capability projection,
so they bind the B4-B causal identity directly and record
`upstream_resolution.status=not_applicable` with reason
`native_kind_not_in_projection`. MCP and BOS require a replay-valid B4-B
resolution receipt whose registry digest exactly matches the projection bytes
used for inspection. The projection is only a locator: MCP proof requires an
exact static FastMCP declaration in the repository-relative Python source, and
BOS proof requires one unique URI in `projects/agora/etc/bos-services.yaml`.
FastMCP proof additionally requires the exact `fastmcp.FastMCP` import, one
top-level authority binding and a literal native server name equal to the
registry ID. An explicit safe literal `version=` is proved from that same call;
an absent or dynamic version remains unprovable. Workflow proof compares two
full canonical-directory snapshots (sorted names plus complete YAML bytes)
around validation and requires exactly one matching ID. Dynamic MCP
registration, display-name/ID mismatch, unreadable competitors and non-unique
claims fail closed.

`native-capability-inspection-receipt/v1` records only the causal binding,
exact kind/ID, repository-relative source reference, source digest/schema,
static proof method/strength, upstream relation and a bounded native version.
When the authority has no explicit version, `native_version` is null and
`native_version_status=unprovable`; no version is inferred. The receipt never
contains source content, Skill instructions, command/argv, module/function
names, provider fields, prompts, environment data or absolute paths. Stable
FD-bound component-by-component no-follow reads reject parent/final symlinks,
replacement, concurrent same-size changes and source replay mismatch. Every
source is reread through the same descriptor and its final directory entry must
still name the original inode.

Receipt replay validates semantics in addition to its self-digest: kind-specific
source schema and proof method, deterministic Skill/Workflow/BOS source refs,
bounded control-free native versions, and every upstream/receipt SHA-256 field
are fixed contracts. Recomputing `receipt_digest` cannot legitimize a changed
proof method, source kind/reference, version or upstream digest.

Every successful or rejected inspection fixes `read_only=true` and
`executed=false`, `provider_called=false`, `invoked=false`,
`value_indicator_policy=false`. Admission, authorization, evidence and
verification remain explicitly `not_evaluated`/false. Static inspection is not
client loading, availability, provider health, admission or execution evidence.

### 5.3 B4-D1 native execution receipt and replay contract

B4-D1 defines standard-library-only model, cleanup and facade boundaries in
`lib/capability_native_execution_model.py`,
`lib/capability_native_cleanup.py` and
`lib/capability_native_execution_receipt.py`. They do not connect a provider,
invoke a native capability, persist a marker, write OMO evidence or authorize a
route. `native-execution-material/v1` embeds the complete replay-valid B4-B
binding and these exact native inputs:

```yaml
binding: <canonical capability-trace-binding/v1 identities>
capability: {kind: workflow|mcp_tool|bos_service, id: <exact native selector>}
inspection:
  receipt_digest: sha256:<64 lowercase hex characters>
  source_digest: sha256:<64 lowercase hex characters>
operation_id: <bounded opaque operation id>
request_digest: sha256:<64 lowercase hex characters>
admission:
  receipt_digest: sha256:<64 lowercase hex characters>
  admission_id: <bounded opaque id>
  step_run_id: <bounded opaque id>
  worker: {status: bound|not_applicable, id: <bounded id|null>}
authorization_source: <workflow-controller|mcp-pep|bos-pep, exactly bound to kind>
effect_classification: read_only|effectful
execution_attempt: <positive bounded integer>
```

The material validator directly calls the B4-B trace-binding validator and the
B4-C native selector parser. Kind and ID must agree; Skill and MCP-server IDs
remain inspection-only and deterministically reject execution. `invocation_id`
is the canonical SHA-256 digest of the complete material object, so changing
any causal, inspection, operation, admission, authorization, effect or attempt
field changes the identity.

`native-cleanup-proof/v1` binds capability kind, invocation ID and its closed
ownership scope (`workflow_child_run`, `mcp_proxy_entry` or
`bos_action_lease`). It records baseline/terminal digests and exactly five
measurements: owned locks, reference-count delta, connection created,
connection disconnected and owned residue. Integers are bounded and never
accept booleans. `proved` requires identical state digests, zero owned
lock/reference/residue and complete teardown of any owned connection;
`unproven` fixes `failure_code=cleanup_unproven`. The proof has its own
`receipt_digest`.

`native-execution-receipt/v1` binds `transport_state` (`confirmed`, `failed` or
`uncertain`), a phase-limited native outcome, an ActionReceipt projection, the
nested cleanup proof and its independent `cleanup_digest`. Effectful confirmed
or failed execution requires a terminal ActionReceipt; read-only confirmed or
failed execution fixes it to `not_applicable`; uncertain transport fixes it to
`missing`. Confirmed/failed transport requires proved cleanup. Uncertain
transport can preserve unproven cleanup but can never become evidence. Result
content and provider error text are never stored—only a digest for confirmed or
terminally failed native invocation. The only terminal native failure code in
the completed outcome is `native_invocation_failed`; admission, replay,
cleanup, evidence and policy codes belong to their own validators.

`native-execution-marker/v1` is a separate pre-call schema. Pure replay with no
existing record returns `needs_durable_start` and `call_allowed=false`; it does
not grant a pre-CAS call. Only the exact canonical `started` marker for the
current material is `transport_uncertain`; a valid foreign marker with another
invocation/material digest is `execution_conflict`. An identical completed
receipt returns `existing` with `call_allowed=false`; changed completed material
is `execution_conflict`.
Automatic fallback is forbidden. The facade only constructs the marker shape;
a future broker remains responsible for durable CAS persistence and atomic
completion.

Unknown or raw request/result, prompt, transcript, credential, environment,
absolute-path, command/argv, module, provider or transport-override fields are
rejected. Receipt replay also rejects snake-case or camel-case forms of
`human_verdict`, `decision_outcome`, personal/value metrics, fallback
promotion, evidence promotion and independent-verification promotion even when
an attacker recomputes every self-digest. Cleanup and execution receipts fix
`value_indicator_policy=false`; execution states fix exact boolean
`invoked=true`, `evidenced=false` and `independently_verified=false`. OMO
evidence handoff and independent verification are later, distinct phases.

## 6. Availability and fallback

“Available” is never a single boolean. Operators must be able to distinguish:

```text
declared -> discovered -> observed -> healthy -> admitted -> authorized
         -> invoked -> evidenced -> independently verified
```

Tool diversity improves resilience through visibility, explicit assignment and
recovery—not silent substitution.

1. No first-match selection.
2. No automatic switch after EOF, timeout or an uncertain transport outcome.
3. A scene may opt into `fallback-with-audit` only when its policy names the
   successor, idempotency boundary and rollback condition.
4. A successor receives a new assignment/dispatch identity and references the
   predecessor uncertainty; it never reuses an ambiguous completion state.
5. Discovery, health and quota observations may inform a human or controller
   decision but cannot authorize provider actions.

## 7. Stable failure vocabulary

The federation audit and public validators use stable codes rather than
provider messages. The phase column is normative: a validator rejection is not
automatically a completed native outcome.

| Code | Phase | Meaning |
|---|---|---|
| `source_unprovable` | discovery/inspection | authority source is missing, uninitialized or unreadable |
| `source_schema_unsupported` | inspection | native schema/version is not supported |
| `source_digest_mismatch` | inspection/replay | source bytes changed after binding |
| `duplicate_authority_claim` | discovery | more than one surface claims canonical ownership |
| `dangling_reference` | discovery/inspection | a native cross-reference has no target |
| `resolution_not_found` | resolution | exact native ID does not exist in a proved source |
| `resolution_ambiguous` | resolution | selector has more than one candidate |
| `upstream_resolution_required` | inspection | the kind-specific B4-B binding or resolution receipt is missing |
| `upstream_resolution_invalid` | inspection | the supplied upstream binding/receipt cannot be replay-validated for the exact native ID |
| `inspection_receipt_invalid` | execution material | the B4-C receipt/source-digest projection is incomplete or malformed |
| `observation_stale` | observation/admission | runtime observation is outside its declared freshness window |
| `admission_contradiction` | admission | admission state and required transport contract disagree |
| `admission_receipt_invalid` | execution material/admission | the admission receipt, step or worker binding is incomplete or malformed |
| `admission_expired` | admission | an otherwise valid admission is outside its bounded validity window |
| `authorization_required` | authorization/material | the exact kind-bound authorization source is missing or mismatched |
| `native_execution_unprovable` | material/execution receipt/marker | the capability is inspection-only or the execution/marker receipt cannot be replay-proved |
| `native_route_unprovable` | execution material | selector, B4-B binding, operation, request, effect or attempt material is invalid |
| `execution_conflict` | replay | current material conflicts with an existing completed receipt or foreign marker |
| `transport_uncertain` | marker/transport | the exact durable started marker exists or transport completion cannot be proved |
| `native_invocation_failed` | terminal native outcome | the invoked native operation reached a confirmed terminal failure |
| `cleanup_unproven` | cleanup | owned locks, references, connections, residue or baseline restoration cannot be proved |
| `execution_evidence_missing` | action receipt | the required terminal/missing/not-applicable ActionReceipt state is invalid |
| `verification_unprovable` | independent verification | downstream verification cannot prove the eligible engineering evidence |
| `value_promotion_forbidden` | value firewall | engineering evidence attempted to create a human or personal-value outcome |
| `fallback_forbidden` | fallback policy | receipt or replay state attempted automatic fallback |

Only `native_invocation_failed` may appear as the failure code inside a
completed `native-execution-receipt/v1` terminal native outcome. Admission,
material, replay, marker, cleanup, ActionReceipt, verification, fallback and
value-policy codes are emitted by their owning validators and must not be
copied into that terminal outcome. An uncertain transport uses
`transport_state=uncertain` with an `unknown` outcome and no native failure
code.

Provider error text, stack traces and raw output stay in bounded local logs and
are not copied into federation receipts.

## 8. Value and privacy firewall

Capability discovery, tool health, execution success, PR merge, issue status,
terminal state and worker receipts are engineering/operational evidence. They
must not create `human_verdict`, `decision_outcome` or a personal value metric.

Engineering-delivery observation remains shadow-only until a credential-bound,
non-test human adjudication is directly readable through the authorized outcome
path. Multica and Orca UI/runtime state are transport observations only.

Receipts store relative repository references or opaque IDs. They never persist
machine-absolute paths, account data, prompts, transcripts, model output,
credentials, environment maps or approval content.

## 9. Multica and external transports

Multica is initially admitted only as `shadow transport telemetry`:

- allowed: version, daemon health, workspace/runtime inventory, activity and
  existing binding observation;
- forbidden: creating repos, tasks, agents, squads or autopilots; sending model
  input; changing profiles; claiming completion;
- current production eligibility: `not_enabled` until repository/clone binding,
  WorkPacket identity, cancel/cleanup semantics, canonical receipt, quota
  circuit breaker and independent verifier all pass canary evidence.

Orca remains a supervised transport/break-glass surface where its native
contract applies. Runtime-ready, terminal-ready and input-accepted are not
worker completion.

## 10. Read-only audit

The first executable implementation is:

```bash
make capability-federation-audit
uv run --with pyyaml python bin/capability-sync.py federation-audit --json
```

The public command reuses the existing capability CLI; the implementation is a
`lib/capability_federation_audit.py` shared library so this contract does
not add a second active `bin/` command. It reads native authorities, emits
deterministic diagnostics and never writes registries, runtime state or
observations. Its default report is honest about warnings and `unprovable`
sources; `--strict` is suitable only after the current baseline has been
deliberately converged.

Minimum checks:

- worker `provider_ref` integrity;
- admitted transport acknowledgement and provider-conformance metadata;
- workflow canonical directory versus legacy projection drift;
- generated capability projection authority wording and metadata;
- partial-clone/uninitialized-source detection;
- duplicate authority claims and admission contradictions;
- no inference from discovery/online/existence to admission or completion.

## 11. Delivery sequence

The capability foundation evolves in bounded steps:

1. **B4-A — federation audit and contract**: read-only graph, stable findings,
   authority map and state separation.
2. **B4-B — trace binding**: bind intent/spec resolution, Workflow run and
   exact generated-capability resolution receipts without changing execution;
   the receipt is replay-verifiable and value-isolated.
3. **B4-C — static native inspect adapter**: Skill, Workflow, MCP and BOS
   bounded source/version proof; it neither loads clients/providers nor infers
   native proof from a B4-B projection receipt.
4. **B4-D — execution receipts**: kind-specific execution binding, cleanup and
   OMO evidence handoff; only its native owner may request execution.
5. **B5 — canary and resilience**: real single-path canaries, explicit recovery,
   no-auto-fallback fault injection and value-firewall tests.

Plugin installation, Multica production dispatch, remote ACP/A2A, automatic
model/quota selection and cross-host multi-tenancy remain deferred until the
preceding evidence is complete.

## Exact Capability Binding rollout status (2026-08-26)

Enforcement: `warning` (promoted from shadow; scans in
docs/reports/2026-08-26-binding-enforcement-scan.md). Delivered tags:
agora/cockpit/ecos/omo-integrity 20260824 v1 set; omo-consumer pending.
Fail promotion and positive-topology canary remain gated on OMO Tasks 2/3.
