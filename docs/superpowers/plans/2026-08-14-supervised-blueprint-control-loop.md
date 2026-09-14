---
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-08-13
last_updated: 2026-09-03
title: Supervised Blueprint Control Loop Implementation Plan
type: doc
---

# Supervised Blueprint Control Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one production OMO control-loop entrypoint that deterministically compiles an accepted candidate BET into a WorkPacket, obtains explicit human release, dispatches and observes a supervised Codex worker, collects a contract-bound CompletionManifest, independently verifies it, and rolls back a rejected candidate to the exact baseline.

**Architecture:** OMO remains the single control-plane truth and reuses the existing BET ledger, Task YAML, Workflow Mesh, worker admission, and ECOS contracts. A focused `BlueprintControlService` freezes the baseline, starts an Orca-managed interactive Codex TUI, pauses for the user's click, then collects Git and acceptance evidence after the same worker settles. It writes only projection/evidence artifacts under the existing worker-run surface. Orca remains transport and never decides completion.

**Tech Stack:** Python 3.13, PyYAML, Pydantic-generated ECOS models, OMO Workflow Mesh, Git binary patches, Orca CLI, interactive Codex TUI, pytest, Ruff.

## Global Constraints

- Codex is manually supervised. The production path uses an Orca-retained interactive TUI; every provider approval is clicked by the user. The bounded `exec --approve-for-me --ephemeral` adapter is diagnostic-only because it cannot carry or resume an interactive approval.
- `Orca ready`, `workerStart ready`, `tui-idle`, `dispatch_input=accepted`, and process exit 0 never imply model readiness or completion.
- Controller approval, interactive session start, `awaiting_human_action`, provider approval, model-output observation, candidate collection, and independent verification remain distinct states.
- Task YAML is the only task SSOT; the BET ledger is the only strategy/specification-acceptance SSOT; Workflow Mesh is the only execution/verification event truth.
- Reuse ECOS `WorkPacket`, `CompletionManifest`, `VerificationReceipt`, `canonicalize`, and `compute_packet_hash`; do not add or alter ECOS M2 in this BET.
- Do not add a scheduler, daemon, watchdog, task database, blueprint-run database, second ledger, second live adapter, Cockpit UI, account switcher, or automatic merge.
- All subprocess invocations use argv lists and `shell=False`, have bounded timeouts, and report non-zero/timeout/cleanup failures without fallback.
- A candidate may produce `EvidenceRecorded` only after identity, scope, receipt, diff, budget, claims, and checks validation. Only independent verifier accept may produce `WorkflowVerified`.
- Verification reject keeps valid candidate evidence, performs controlled compensation, and proves the repository baseline hash was restored before closing.
- Root/submodule delivery follows independent-clone, child-main-first, reachable-gitlink, PR, tag, and cleanup discipline.

## Fresh admission-bound approval-wait canary invariants

- Provider launch must always require a fresh `WorkflowAdmitted` grant bound to the current `bet_id`, `task_id`, `workflow_run_id`, and `dispatch_id`; stale grants, replayed runs, or cross-run carryover must fail closed.
- `ApprovalRequested` is treated as durable evidence that is recoverable only through replay with matching worker identity and explicit Orca re-attestation of the same run; a `collect` path must refuse completion if projection binding is incomplete.
- `input_accepted` is only transport evidence (`transport_accepted` path) and never model readiness nor completion evidence; it cannot satisfy `EvidenceRecorded` or `WorkflowVerified` preconditions.
- `WorkflowVerified` is gated by independent direct measurement and may only be emitted after verifier checks pass on the manifest, receipts, and measured outputs; executor self-reporting, exit status, `ready`, or `input_accepted` are out-of-band and must not produce `WorkflowVerified`.

---

### Execution preflight: initialize OMO path dependencies in the independent clone

Before Task 2 or any `cd projects/omo && uv run ...` command, initialize the path dependencies declared by the OMO project. This is clone setup only; it does not change the root gitlink or count as implementation:

```bash
git submodule update --init --recursive \
  projects/aetherforge projects/agora projects/bus-foundation projects/ecos
test -f projects/aetherforge/pyproject.toml
test -f projects/agora/pyproject.toml
test -f projects/bus-foundation/pyproject.toml
test -f projects/ecos/pyproject.toml
```

If any dependency cannot be initialized at the pinned SHA, stop. Do not replace it with a sibling checkout, an editable install from the shared Workspace, or an unpinned branch.

---

### Task 1: Freeze the governed BET and correct the Codex approval contract

**Files:**
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Modify: `.omo/standards/agent-cli-worker-collaboration.md`
- Modify: `.omo/_truth/registry/workers.yaml`
- Create: `docs/superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md`
- Create: `docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md`

**Interfaces:**
- Consumes: `BET-Y1Q2-T1-17`, existing Codex worker record, accepted spec digest.
- Produces: `BET-Y1Q2-T1-18` with exact `accepted_specifications`; a supervised Codex policy consumed by Tasks 3–5.

- [ ] **Step 1: Add the candidate BET with exact accepted specification binding**

Add `BET-Y1Q2-T1-18`, increment `meta.total_bets`, and copy the spec SHA-256 into:

```yaml
accepted_specifications:
- spec_ref: repo://docs/superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md
  spec_version: 1.0.0
  content_digest: sha256:0c344987452535e9e8ac4bd871311bd3c206f21a5bfac6376b1ecf317b79b836
```

Use the design's eight acceptance criteria verbatim, set `human_gate: true`, `risk_level: L1`, appetite `3 days`, and dependency `BET-Y1Q2-T1-17`.

- [ ] **Step 2: Correct the public Codex contract**

Replace claims that `--approve-for-me` removes interactive prompts with:

```text
Codex production execution is manually supervised through an Orca-retained interactive
TUI. The user must click provider approvals in that same terminal. --approve-for-me is
diagnostic-only and cannot prove or carry the click. Controller approval and provider
approval are separate evidence fields; an unresolved provider approval remains
awaiting_human_action.
```

In `workers.yaml`, add a `supervision` map to the existing Codex record:

```yaml
supervision:
  controller_approval: required
  provider_review: manual_click_required
  waiting_state: awaiting_human_action
  readiness_evidence: settled_worker_done_and_transcript_digest
  transport_ack_is_readiness: false
```

- [ ] **Step 3: Validate governance surfaces**

Run:

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py lint
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q2-T1-18
git diff --check -- docs/plans/3y-bet-ledger.yaml .omo/standards/agent-cli-worker-collaboration.md .omo/_truth/registry/workers.yaml docs/superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md
```

Expected: `claim-check` and `diff --check` exit 0. The global lint currently exits 1 with exactly the 25 pre-existing T6-04/T6-06..T6-10 findings recorded in the Task 1 evidence; it must not add any T1-18 finding. This is a scoped baseline exception, not a claim that global ledger health is green. If the count or identities change, stop and investigate.

- [ ] **Step 4: Commit the governance slice**

```bash
git add docs/plans/3y-bet-ledger.yaml .omo/standards/agent-cli-worker-collaboration.md .omo/_truth/registry/workers.yaml docs/superpowers/specs/2026-08-14-supervised-blueprint-control-loop-design.md docs/superpowers/plans/2026-08-14-supervised-blueprint-control-loop.md
git commit -m "docs: define supervised blueprint control loop"
```

### Task 2: Make candidate specification binding executable and compensation honest

**Files:**
- Modify: `projects/omo/src/omo/orchestration_contract.py`
- Modify: `projects/omo/src/omo/workflow_mesh.py`
- Modify: `projects/omo/tests/test_orchestration_contract.py`
- Modify: `projects/omo/tests/test_workflow_mesh.py`

**Interfaces:**
- Consumes: v2 `spec_binding` and accepted ledger entry from Task 1.
- Produces: `_validate_spec_binding` accepting unfinished but accepted BETs; generic `record_candidate`; a legal `succeeded -> compensating` transition.

- [ ] **Step 1: Write failing candidate-BET and generic-candidate tests**

Add tests asserting:

```python
def test_candidate_bet_with_exact_accepted_spec_is_executable(...):
    # ledger status=candidate and exact accepted_specifications succeeds

def test_candidate_bet_without_exact_binding_is_rejected_without_events(...):
    # no matching spec/version/digest is fail-closed

def test_generic_candidate_receipt_binds_dispatch_and_manifest(...):
    # record_candidate validates workflow, step, assignment, dispatch and receipt
```

Run:

```bash
cd projects/omo && uv run python -m pytest tests/test_orchestration_contract.py -q
```

Expected: new tests fail because the current implementation requires `status: done` and hardcodes Kandev.

- [ ] **Step 2: Implement exact candidate binding and a generic candidate method**

Change `_validate_spec_binding` to accept only:

```python
EXECUTABLE_BET_STATES = frozenset({"candidate", "in_progress", "review", "done"})
```

while retaining exact BET id, `spec_ref`, `spec_version`, content digest, repo-relative path, read-surface, and measured-byte checks.

Add:

```python
def record_candidate(
    self,
    *,
    workflow_run_id: str,
    step_run_id: str,
    packet: Mapping[str, Any],
    manifest: Mapping[str, Any],
    transport_receipt: Mapping[str, Any],
) -> dict[str, Any]: ...
```

The transport receipt must bind `workflow_run_id`, `step_run_id`, `bet_id`, `packet_id`, `packet_hash`, `assignment_id`, `dispatch_id`, `worker_id`, `output_digest`, `changed_paths`, and `receipt_digest`. Keep `record_kandev_candidate` only as a compatibility wrapper that calls this generic method.

- [ ] **Step 3: Write the compensation RED test**

Add a state-machine test:

```python
def test_succeeded_candidate_can_enter_compensation_and_close_cancelled(...):
    # succeeded -> CompensationStarted -> WorkflowRecovered -> WorkflowCancelled -> WorkflowClosed
```

Run:

```bash
cd projects/omo && uv run python -m pytest tests/test_workflow_mesh.py -q
```

Expected: fail at `CompensationStarted` from succeeded.

- [ ] **Step 4: Add the narrow transition**

Extend only the existing state machine:

```python
"succeeded": {"succeeded", "verified", "compensating", "closed"}
```

and allow `CompensationStarted` from `succeeded`. Do not add an event type or second state machine.

- [ ] **Step 5: Run focused regression**

```bash
cd projects/omo && uv run python -m pytest tests/test_orchestration_contract.py tests/test_workflow_mesh.py tests/test_omo_external_receipt.py -q
cd projects/omo && uv run ruff check src/omo/orchestration_contract.py src/omo/workflow_mesh.py tests/test_orchestration_contract.py tests/test_workflow_mesh.py
git -C projects/omo diff --check
```

Expected: all pass.

- [ ] **Step 6: Commit the OMO contract slice**

```bash
git -C projects/omo add src/omo/orchestration_contract.py src/omo/workflow_mesh.py tests/test_orchestration_contract.py tests/test_workflow_mesh.py
git -C projects/omo commit -m "feat: generalize supervised orchestration evidence"
```

### Task 3: Build the OMO compile, dispatch, and observation controller

**Files:**
- Create: `projects/omo/src/omo/blueprint_control.py`
- Modify: `projects/omo/src/omo/workflow_dispatch.py`
- Modify: `projects/omo/src/omo/omo_worker_dispatch.py`
- Create: `projects/omo/tests/test_blueprint_control.py`
- Modify: `projects/omo/tests/test_workflow_dispatch.py`

**Interfaces:**
- Consumes: `admit_workflow`, `dispatch_task`, ECOS WorkPacket compiler, worker registry and Task approval record.
- Produces: `BlueprintControlService.compile_packet(...)`, `dispatch_packet(...)`, and `observe_dispatch(...)`.

- [ ] **Step 1: Write compile RED tests**

Tests must cover deterministic packet id/hash, candidate BET, exact spec digest, missing accepted binding, fake ledger, Task without human gate, unsafe output path, and zero Mesh writes on compile failure.

Run:

```bash
cd projects/omo && uv run python -m pytest tests/test_blueprint_control.py -q
```

Expected: collection fails because `omo.blueprint_control` does not exist.

- [ ] **Step 2: Implement deterministic compile**

Define:

```python
@dataclass(frozen=True)
class CompiledBlueprintPacket:
    packet: dict[str, Any]
    packet_hash: str

class BlueprintControlService:
    def compile_packet(
        self,
        *,
        bet_id: str,
        task_id: str,
        spec_ref: str,
        spec_version: str,
        expires_at: str,
    ) -> CompiledBlueprintPacket: ...
```

The packet id is a stable prefix plus the first 16 hex characters of the ECOS canonical hash input. The packet includes Task read/write surfaces, capabilities, non-goals, evidence requirements, BET done-when/verify commands, explicit `human_gate: true`, rollback/circuit-breaker text, and the exact v2 spec binding. Validate it with generated `WorkPacket` and recompute with `canonicalize`/`compute_packet_hash` before returning.

- [ ] **Step 3: Write dispatch RED tests**

Test exact event order, valid approval, missing/expired/mismatched approval, worker capability mismatch, Mesh append failure, and explicit proof that the returned state is `transport_accepted`, not ready/succeeded. The Mesh failure test must exercise `omo_worker_dispatch._bridge_dispatch_to_mesh`; an append failure must propagate and the controller must not report transport acceptance.

- [ ] **Step 4: Implement dispatch and observe**

Extend the existing active-Task `admit_workflow` with an optional validated request-identity mapping containing `bet_id`, `packet_id`, `packet_hash`, and `task_ref`; merge it into the existing `WorkflowRequested` payload rather than creating a second request implementation. Dispatch with `launch=False`. The dispatch artifact stores:

```yaml
blueprint:
  packet_id: ...
  packet_hash: ...
  bet_id: ...
control_state:
  controller_approval: granted
  transport: accepted
  readiness: unproven
  provider_review: unknown
```

`observe_dispatch` derives state from Mesh plus the dispatch/receipt/manifest projection; it never maps transport ack or exit 0 to readiness.

Remove the broad `except Exception: pass` around the production Mesh bridge. Duplicate/idempotent events may be handled explicitly by the existing store contract, but any unclassified append failure must abort dispatch before the controller emits `transport_accepted`.

- [ ] **Step 5: Run focused tests and commit**

```bash
cd projects/omo && uv run python -m pytest tests/test_blueprint_control.py tests/test_workflow_dispatch.py tests/test_omo_worker_admission_gate.py -q
cd projects/omo && uv run ruff check src/omo/blueprint_control.py src/omo/workflow_dispatch.py src/omo/omo_worker_dispatch.py tests/test_blueprint_control.py tests/test_workflow_dispatch.py
git -C projects/omo diff --check
git -C projects/omo add src/omo/blueprint_control.py src/omo/workflow_dispatch.py src/omo/omo_worker_dispatch.py tests/test_blueprint_control.py tests/test_workflow_dispatch.py
git -C projects/omo commit -m "feat: add supervised blueprint controller"
```

### Task 4: Keep the bounded exec adapter fail-closed and add the Orca interactive supervisor

**Files:**
- Modify: `bin/gac/codex-worker-adapter.py`
- Modify: `tests/unit/gac/test_codex_worker_adapter.py`
- Create: `bin/gac/orca-codex-supervisor.py`
- Create: `tests/unit/gac/test_orca_codex_supervisor.py`

**Interfaces:**
- Consumes: the T1-17 diagnostic exec adapter and Orca's interactive Codex worker contract.
- Produces: a diagnostic adapter that fails on approval, plus a thin start/collect supervisor that binds OMO and Orca identities without storing prompt/transcript content.

- [ ] **Step 1: Write failing receipt tests**

Add tests for:

```python
assert receipt["supervision"]["controller_approval"] == "granted"
assert receipt["supervision"]["provider_review"] in {
    "human_required", "unknown", "timed_out"
}
assert receipt["readiness"] == "model_output_observed"
assert receipt["baseline_digest"].startswith("sha256:")
assert receipt["patch_digest"].startswith("sha256:")
```

Also cover timeout/partial JSONL as `timed_out` or `human_required` when an approval event is observed, with no success receipt or patch application.

- [ ] **Step 2: Implement minimal event classification and rollback evidence**

Parse only documented/observed JSONL event types; unknown events remain unknown. Any approval request makes the diagnostic exec adapter fail closed before applying a patch. It never claims the user clicked or that the ephemeral session can resume.

The Orca supervisor must run `status -> run-create -> task-create -> worker-start`, bind workflow/task/packet/hash/OMO dispatch/prompt digest, and return `awaiting_human_action`. Its collect side accepts only the same worker's settled+succeeded+worker_done plus a non-empty transcript, and stores only the transcript digest. It never treats ready/input accepted as completion and never stores prompt/transcript content.

- [ ] **Step 3: Run adapter regression**

```bash
uv run --no-project --with pytest --with pyyaml python -m pytest tests/unit/gac/test_codex_worker_adapter.py -q
uv run --no-project --with pytest python -m pytest tests/unit/gac/test_orca_codex_supervisor.py -q
uv run --with ruff ruff check bin/gac/codex-worker-adapter.py bin/gac/orca-codex-supervisor.py tests/unit/gac/test_codex_worker_adapter.py tests/unit/gac/test_orca_codex_supervisor.py
git diff --check -- bin/gac/codex-worker-adapter.py bin/gac/orca-codex-supervisor.py tests/unit/gac/test_codex_worker_adapter.py tests/unit/gac/test_orca_codex_supervisor.py
```

Expected: all pass and existing transactional rollback tests remain green.

- [ ] **Step 4: Commit the root adapter slice**

```bash
git add bin/gac/codex-worker-adapter.py bin/gac/orca-codex-supervisor.py tests/unit/gac/test_codex_worker_adapter.py tests/unit/gac/test_orca_codex_supervisor.py
git commit -m "feat: supervise interactive Codex through Orca"
```

### Task 5: Pause, collect, independently verify, and compensate rejected candidates

**Files:**
- Modify: `projects/omo/src/omo/blueprint_control.py`
- Modify: `projects/omo/src/omo/orchestration_contract.py`
- Modify: `projects/omo/tests/test_blueprint_control.py`
- Modify: `projects/omo/tests/test_orchestration_contract.py`

**Interfaces:**
- Consumes: Task 3 dispatch projection, Task 4 adapter receipt, ECOS manifest/receipt builders, generic `record_candidate`.
- Produces: `start_supervised_execution(...)`, `collect_supervised_execution(...)`, `verify_candidate(...)`, and `rollback_candidate(...)` with idempotent Mesh evidence. The old bounded `execute_and_collect(...)` remains test/diagnostic compatibility only and is not the production CLI path.

- [ ] **Step 1: Write the golden-path RED test**

Use a real temporary Git repository and injected bounded runner. Assert:

```text
compile -> requested -> admitted -> StepDispatched -> StepStarted ->
real file delta -> WorkflowSucceeded -> EvidenceRecorded -> WorkflowVerified
```

The runner returns a valid model-output receipt and changes one declared file. Build a CompletionManifest whose claims cover every packet AC and whose checks are measured command receipts.

- [ ] **Step 2: Write negative collection tests**

Cover receipt digest drift, wrong dispatch/assignment/packet, out-of-scope path, missing model output, extra changed path, non-zero check, and transport ack without receipt. Assert no `EvidenceRecorded` and no `WorkflowVerified`.

- [ ] **Step 3: Implement execute and collect**

`start_supervised_execution` freezes the Git baseline before invoking the Orca supervisor, appends `StepStarted` only after a valid worker-start receipt, persists an atomic execution projection, and returns `awaiting_human_action`. `collect_supervised_execution` reloads and binds that projection, rejects active/unknown workers without candidate events, accepts only the settled worker receipt, then directly measures Git delta and one deterministic command per Task acceptance criterion. Only after those direct measurements may it build the manifest, append `WorkflowSucceeded`, and call `record_candidate`.

- [ ] **Step 4: Write verifier and rollback RED tests**

Test an independent all-green verifier and a failing verifier. For reject, assert:

```text
EvidenceRecorded exists
WorkflowVerified does not exist
CompensationStarted -> WorkflowRecovered -> WorkflowCancelled -> WorkflowClosed
git diff is empty and baseline digest matches
```

Also test patch tamper/preimage mismatch leaves the run unclosed and returns `rollback_unconfirmed`.

- [ ] **Step 5: Implement independent verification and compensation**

Run each packet `verify_commands` as `shell=False` with timeout. Build ECOS command checks and a VerificationReceipt with `executor_model_family="codex"`, `verifier_model_family="deterministic-runner"`. On accept call `accept_verification`. On reject append `CompensationStarted`, reverse only the stored patch after preimage validation, verify baseline identity, then append recovered/cancelled/closed events.

- [ ] **Step 6: Run integration regression and commit**

```bash
cd projects/omo && uv run python -m pytest tests/test_blueprint_control.py tests/test_orchestration_contract.py tests/test_workflow_mesh.py tests/test_workflow_dispatch.py tests/test_omo_worker_admission_gate.py -q
cd projects/omo && uv run ruff check src/omo/blueprint_control.py src/omo/orchestration_contract.py src/omo/workflow_dispatch.py tests/test_blueprint_control.py tests/test_orchestration_contract.py tests/test_workflow_dispatch.py
git -C projects/omo diff --check
git -C projects/omo add src/omo/blueprint_control.py src/omo/orchestration_contract.py tests/test_blueprint_control.py tests/test_orchestration_contract.py
git -C projects/omo commit -m "feat: verify and compensate blueprint candidates"
```

### Task 6: Add the thin OMO CLI and end-to-end command tests

**Files:**
- Modify: `projects/omo/src/omo/cli.py`
- Modify: `projects/omo/src/omo/blueprint_control.py`
- Modify: `projects/omo/tests/test_blueprint_control.py`

**Interfaces:**
- Consumes: `BlueprintControlService` from Tasks 3 and 5.
- Produces: `omo blueprint compile|dispatch|observe|execute|collect|verify|rollback` without duplicate business logic.

- [ ] **Step 1: Write CLI RED tests**

Invoke `omo.cli.main([...])` against a temporary authority root. Assert JSON output, stable non-zero error codes, no raw traceback, and no success for missing approval, input-only ack, verifier reject, or rollback mismatch.

- [ ] **Step 2: Implement the facade**

Add one route in `omo.cli.main`:

```python
if args and args[0] == "blueprint":
    from omo.blueprint_control import main as blueprint_main
    return blueprint_main(args[1:])
```

`blueprint_control.main` owns argparse and JSON I/O. It must not duplicate compile, dispatch, collect, verify, or rollback logic.

- [ ] **Step 3: Run CLI regression and commit**

```bash
cd projects/omo && uv run python -m pytest tests/test_blueprint_control.py tests/test_omo_cli_modules.py -q
cd projects/omo && uv run ruff check src/omo/cli.py src/omo/blueprint_control.py tests/test_blueprint_control.py
git -C projects/omo diff --check
git -C projects/omo add src/omo/cli.py src/omo/blueprint_control.py tests/test_blueprint_control.py
git -C projects/omo commit -m "feat: expose blueprint control CLI"
```

### Task 7: Integrate the child delivery, run supervised Orca/Codex dogfood, and independently review it

**Files:**
- Create: `.omo/_knowledge/retros/BET-Y1Q2-T1-18.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: an OMO child commit already merged to child `main`, a fixed root integration checkout that pins that child commit, the reviewed root adapter/config slices, and Orca 1.4.180 task transport.
- Produces: real run/task/dispatch identifiers, privacy-safe receipts, independent review verdict, and a truthful BET closeout.

- [ ] **Step 1: Merge the reviewed OMO child PR and pin its reachable SHA in the root integration checkout**

Run the Task 8 child verification commands first, push the OMO branch, create and merge the child PR, then verify the merged child SHA is reachable from `origin/main`. Update the root integration checkout through `bin/ssot/submodule-pointer-transaction.sh` (or its exact reachability gates). The root PR is not merged yet; all dogfood below runs against this fixed integration checkout and records the root commit/base SHA plus child SHA.

- [ ] **Step 2: Create and promote a disposable R1 task through governed ingress**

Create a temporary task input YAML outside the repository with a stable test id, `status: candidate`, `risk_level: L1`, `allowed_operation_level: L1`, `human_approval_required: true`, one declared documentation deliverable/write path, the exact deterministic verify command, required Codex capabilities, and refs to this accepted spec/BET. Ingest it through the broker, never by writing `.omo/tasks` directly:

```bash
cd projects/omo
uv run python -m omo.cli governance ingress-task "$TASK_INPUT" \
  --ingress-plane projects/omo --source-ref "bet:BET-Y1Q2-T1-18:dogfood" --now "$NOW"
uv run python -m omo.cli worker task promote-eval "$TASK_ID" --omo-dir .omo
uv run python -m omo.cli worker task promotion-request-approval "$TASK_ID" \
  --requested-by "$OPERATOR" --now "$NOW" --omo-dir .omo
```

Record the emitted `approval_ref` and proposal id. Before approval, compile may succeed but dispatch/execute must return `controller_approval_required`, with no Codex process or model-output receipt.

- [ ] **Step 3: Grant the task promotion and execution release through the governance broker**

The human operator reviews the proposal and explicitly runs:

```bash
uv run python -m omo.cli governance approve "$PROPOSAL_ID" --approver "$OPERATOR" --now "$APPROVED_AT"
uv run python -m omo.cli governance apply "$PROPOSAL_ID" --now "$APPROVED_AT"
uv run python -m omo.cli worker task promote-eval "$TASK_ID" --omo-dir .omo
uv run python -m omo.cli worker task promote-apply "$TASK_ID" \
  --promoted-by "$OPERATOR" --now "$APPROVED_AT" --omo-dir .omo
```

Then `omo blueprint dispatch` creates the packet-bound WorkflowRequested/Admitted/StepDispatched projection but still does not launch Codex. `omo blueprint execute --supervised --approval-ref "$APPROVAL_REF"` is the separate execution release. Both approval refs and their exact scopes must be retained in the controller projection.

- [ ] **Step 4: Execute through Orca and handle any Codex confirmation manually**

The task changes one declared documentation fixture, requires explicit human approval, and has one deterministic verify command. Record baseline tree/diff digest before release.

Run `omo blueprint execute`, which creates the Orca Run/Task/Dispatch and retained interactive Codex terminal, then returns `awaiting_human_action`. The user opens that exact terminal and clicks the Codex approval. Until that happens, repeated collect calls must remain non-success and emit no candidate evidence. After the same worker emits `worker_done`, collect stores only identifiers and digests. Orca `ready`, `tui-idle`, or `input_accepted` remains transport evidence only.

- [ ] **Step 5: Collect and independently verify**

Run the OMO collect/verify CLI. Assert real changed path, adapter receipt, CompletionManifest, EvidenceRecorded, direct command checks, and WorkflowVerified for the accepted case.

- [ ] **Step 6: Run a reject/rollback canary**

On a second disposable run, inject a failing verify command after a valid candidate. Assert candidate evidence remains, WorkflowVerified is absent, compensation runs, and final tree/diff digest equals baseline.

- [ ] **Step 7: Independent reviews**

Dispatch one spec/compliance reviewer and one code/security reviewer. Both must read the design, plan, diff package, test report and privacy-safe run receipts. Critical/Important findings return to a single fix wave and re-review.

- [ ] **Step 8: Write the retro and mark the BET done only with real evidence**

The retro must separate controller approval, provider review, transport ack, model readiness, candidate evidence, verification and rollback; report false-ready findings and remaining boundaries. If real supervised Codex cannot complete, leave the BET `review` or `blocked`, not `done`.

### Task 8: Deliver the root PR, tag, close out, and clean

**Files:**
- Modify: `projects/omo` gitlink already pinned to the merged child SHA by Task 7.
- Modify: `docs/plans/3y-bet-ledger.yaml` only for final evidence/status.

**Interfaces:**
- Consumes: reviewed commits and real dogfood receipts.
- Produces: reachable root gitlink, root PR, D0 tag, closed workflow and removed completed worktree/branches.

- [ ] **Step 1: Re-verify the merged child SHA and fixed root integration checkout**

```bash
cd projects/omo && uv run python -m pytest tests/test_blueprint_control.py tests/test_orchestration_contract.py tests/test_workflow_mesh.py tests/test_workflow_dispatch.py tests/test_omo_worker_admission_gate.py -q
cd projects/omo && uv run ruff check src/omo/blueprint_control.py src/omo/orchestration_contract.py src/omo/workflow_mesh.py src/omo/cli.py tests/test_blueprint_control.py tests/test_orchestration_contract.py tests/test_workflow_mesh.py
git -C projects/omo diff --check
```

- [ ] **Step 2: Run the governed root verification**

```bash
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
uv run --no-project --with pytest --with pyyaml python -m pytest tests/unit/gac/test_codex_worker_adapter.py -q
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q2-T1-18
git diff --check
```

- [ ] **Step 3: Commit, PR, merge and tag the root delivery**

Split commits by the repository change-lane gate. Open the root PR, wait for required checks and independent reviewer approval, merge, then create a durable tag such as:

```text
bet/BET-Y1Q2-T1-18-<UTC timestamp>
```

- [ ] **Step 4: Close workflow and clean completed resources**

Run agent-workflow closeout, then remove only clean, merged worktrees and obsolete local branches through the governed cleanup tools. Keep dirty/unmerged worktrees and privacy-safe run receipts. Verify `git worktree list`, local branch ancestry and Orca worker/terminal cleanup after removal.

## Plan Self-Review

- Spec coverage: Tasks 1–8 cover all eight acceptance criteria and the design's compile, approval, dispatch, model-readiness, collect, verify, compensation, review and delivery stages.
- Placeholder scan: no implementation step delegates unspecified error handling or testing; runtime-generated ids/digests are explicitly measured rather than hard-coded.
- Type consistency: the plan consistently uses `BlueprintControlService`, `CompiledBlueprintPacket`, `record_candidate`, ECOS WorkPacket/CompletionManifest/VerificationReceipt, and the existing Workflow Mesh event names.
