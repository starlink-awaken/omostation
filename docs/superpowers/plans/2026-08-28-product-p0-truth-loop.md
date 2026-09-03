---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 Truth Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the canonical completion-policy prerequisite, then coordinate six independent Product P0 WorkPackets into one honest principal-bound execution, outcome, and recovery loop.

**Architecture:** Extend only the existing BET ledger completion validator so non-value delivery BETs can reach `delivery_accepted` while value remains `NOT_PROVEN`; preserve current value-required behavior by default. Execute WP1-WP6 through their own accepted Specs, independent clones, workflows, child PRs, evidence matrices, and rollback boundaries; the parent only serializes shared SSOT/root integration and verifies the final chain.

**Tech Stack:** Python 3.13, PyYAML, pytest, `bin/plan/bet-ledger.py`, Agent Workflow, Orca orchestration, GitHub PR/Actions, existing OMO/eCOS/Cockpit/Agora contracts.

## Global Constraints

- Parent BET: `BET-Y1Q3-T4-02`; canonical packet: `WP-BET-Y1Q3-T4-02`.
- Accepted parent Spec: `docs/superpowers/specs/2026-08-28-product-p0-truth-loop-design.md` version `1.0.0`.
- Historical BETs with no `value_indicator_policy` retain the existing value-required semantics.
- `value_indicator_policy=false` requires value=`NOT_PROVEN`; it never fabricates, copies, or upgrades value evidence.
- WP1/WP2/WP3/WP4/WP6 complete as `delivery_accepted`; WP5 completes as `outcome_accepted`.
- The parent may reference WP5 immutable value receipts but may not create a second value sample.
- Maximum two implementation writers per wave; shared ledger, completion evidence, retros, and root gitlinks are coordinator-serialized.
- Wave A: WP1 + WP4 in parallel. Wave B: WP2 then WP3. Wave C: WP5 + WP6 in parallel.
- Every writer uses an independent clone, normal `bootstrap -> start --bet -> affected receipt -> claim -> RED -> GREEN -> verify -> closeout`, and a child-first/root-last PR sequence.
- Root shared `/Users/xiamingxing/Workspace` remains read-only for writers.
- No second ledger, workflow engine, dispatcher, WorkPacket schema, identity registry, outbox, value writer, or runtime database.
- Tests, PRs, CI, transport receipts, agent self-reports, synthetic data, and `user_provided` samples never prove principal-bound value.

---

### Task 1: Add Value-Exempt Completion Semantics

**Files:**
- Modify: `bin/plan/bet-ledger.py`
- Modify: `tests/test_spec_binding_lint.py`

**Interfaces:**
- Consumes: `completion_evidence` using `completion-evidence-matrix/v1` and the BET-level boolean `value_indicator_policy`.
- Produces: `validate_completion_evidence(matrix, *, value_indicator_policy: bool = True, workspace: Path = WS) -> tuple[str, list[str]]`.
- Produces: derived state `delivery_accepted` only for `engineering=VERIFIED`, `operational=PROVEN`, `value=NOT_PROVEN`, and `value_indicator_policy=False`.
- Preserves: default `value_indicator_policy=True`, credential-bound `outcome_accepted`, `REJECTED`, `blocked`, and `evaluating` behavior.

- [ ] **Step 1: Write RED tests for the new derivation and value firewall**

Add to `tests/test_spec_binding_lint.py`:

```python
def test_value_exempt_verified_delivery_derives_delivery_accepted(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
    )

    state, errors = bl.validate_completion_evidence(
        matrix,
        value_indicator_policy=False,
        workspace=tmp_path,
    )

    assert state == "delivery_accepted"
    assert errors == []


def test_value_exempt_bet_rejects_accepted_value(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="blocked",
    )

    state, errors = bl.validate_completion_evidence(
        matrix,
        value_indicator_policy=False,
        workspace=tmp_path,
    )

    assert state == "blocked"
    assert any("COMPLETION_VALUE_POLICY_VIOLATION" in error for error in errors)


def test_unspecified_value_policy_keeps_outcome_required(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="blocked",
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert errors == []
```

- [ ] **Step 2: Run the derivation tests and confirm RED**

Run:

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_spec_binding_lint.py::test_value_exempt_verified_delivery_derives_delivery_accepted \
  tests/test_spec_binding_lint.py::test_value_exempt_bet_rejects_accepted_value \
  tests/test_spec_binding_lint.py::test_unspecified_value_policy_keeps_outcome_required -q
```

Expected: FAIL because `validate_completion_evidence` does not accept `value_indicator_policy` and has no `delivery_accepted` state.

- [ ] **Step 3: Implement the minimal backward-compatible validator**

Change the signature and derivation in `bin/plan/bet-ledger.py`:

```python
def validate_completion_evidence(
    matrix: Any,
    *,
    value_indicator_policy: bool = True,
    workspace: Path = WS,
) -> tuple[str, list[str]]:
    """Validate three axes and derive value-required or value-exempt completion."""
```

After collecting the three axis statuses, add the fail-closed value policy check and derivation in this order:

```python
    value_status = statuses.get("value")
    if not value_indicator_policy and value_status != "NOT_PROVEN":
        errors.append(
            "COMPLETION_VALUE_POLICY_VIOLATION: "
            "value_indicator_policy=false requires value.status=NOT_PROVEN"
        )

    if set(statuses) != set(COMPLETION_AXIS_STATUSES):
        derived = "blocked"
    elif not value_indicator_policy and (
        statuses["engineering"] == "VERIFIED"
        and statuses["operational"] == "PROVEN"
        and statuses["value"] == "NOT_PROVEN"
    ):
        derived = "delivery_accepted"
    elif statuses["value"] == "REJECTED":
        derived = "rejected"
    elif (
        statuses["engineering"] == "VERIFIED"
        and statuses["operational"] == "PROVEN"
        and statuses["value"] == "ACCEPTED"
    ):
        derived = "outcome_accepted"
    elif statuses["engineering"] == "VERIFIED" or statuses["operational"] == "DEGRADED":
        derived = "blocked"
    else:
        derived = "evaluating"

    if errors:
        derived = "blocked"
```

- [ ] **Step 4: Pass the BET policy through lint and complete callers**

In `cmd_lint`, pass the policy into validation and derive the required terminal state:

```python
            value_indicator_policy = bool(b.get("value_indicator_policy", True))
            state, completion_errors = validate_completion_evidence(
                completion_matrix,
                value_indicator_policy=value_indicator_policy,
                workspace=WS,
            )
            required_done_state = (
                "outcome_accepted" if value_indicator_policy else "delivery_accepted"
            )
            if transitioned_to_done and state != required_done_state:
                errs.append(
                    f"{b['id']}.completion_evidence: "
                    f"BET_DONE_REQUIRES_{required_done_state.upper()}"
                )
```

In `cmd_complete`, use the same policy and required terminal state:

```python
    value_indicator_policy = bool(b.get("value_indicator_policy", True))
    completion_state, completion_errors = validate_completion_evidence(
        completion_matrix,
        value_indicator_policy=value_indicator_policy,
        workspace=WS,
    )
    required_completion_state = (
        "outcome_accepted" if value_indicator_policy else "delivery_accepted"
    )
    if completion_errors or completion_state != required_completion_state:
        for error in completion_errors:
            print(f"[complete] ❌ {b['id']}.completion_evidence: {error}")
        if completion_state != required_completion_state:
            print(
                f"[complete] ❌ {b['id']}.completion_evidence: "
                f"derived state is {completion_state}, not {required_completion_state}"
            )
        return 1
```

- [ ] **Step 5: Add transition and completion command tests**

Add focused tests using the existing `_bet`, `_completion_matrix`, `_transition_base`, and `cmd_complete` helpers:

```python
def test_lint_accepts_value_exempt_done_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-28"
    bet["value_indicator_policy"] = False
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="candidate")

    assert bl.cmd_lint(_lint_data(bet), type("Args", (), {})()) == 0


def test_complete_accepts_value_exempt_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bet = _bet(status="review")
    bet["value_indicator_policy"] = False
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    monkeypatch.setattr(bl, "LEDGER", tmp_path / "docs/plans/3y-bet-ledger.yaml")
    monkeypatch.setattr(bl, "_d0_surface_tracked", lambda path: (True, "tracked"))
    monkeypatch.setattr(bl, "save", lambda data: None)

    args = type("Args", (), {"bet_id": "BET-TEST", "force": True})()
    assert bl.cmd_complete(_lint_data(bet), args) == 0
    assert bet["status"] == "done"
```

- [ ] **Step 6: Run GREEN and full completion-contract regression**

Run:

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_spec_binding_lint.py -q
uv run --with pyyaml python bin/plan/bet-ledger.py lint
```

Expected: focused tests PASS; the ledger introduces no new Product P0 errors. Pre-existing baseline findings must be compared by exact ID/signature and must not be modified in this task.

- [ ] **Step 7: Commit the parent prerequisite**

```bash
git add bin/plan/bet-ledger.py tests/test_spec_binding_lint.py
git commit -m "feat(plan): support value-exempt BET completion"
```

Expected: one root code-lane commit containing only the two claimed files.

---

### Task 2: Review and Merge the Completion-Policy PR

**Files:**
- Review: `bin/plan/bet-ledger.py`
- Review: `tests/test_spec_binding_lint.py`

**Interfaces:**
- Consumes: Task 1 branch and test receipts.
- Produces: merged root main supporting `delivery_accepted` with no historical semantic drift.

- [ ] **Step 1: Run an independent two-axis review**

Review Standards and Spec compliance against `origin/main...HEAD`. Required findings:

```text
historical default stays value-required
value_indicator_policy=false rejects ACCEPTED/REJECTED value
delivery_accepted requires VERIFIED + PROVEN + NOT_PROVEN
lint and cmd_complete use the same predicate
no status or completion evidence changed in the delivery diff
```

- [ ] **Step 2: Run final branch verification**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_spec_binding_lint.py -q
P0_PARENT_RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py status --json | jq -r .current_run_id)"
test -n "$P0_PARENT_RUN_ID"
PYTHONDONTWRITEBYTECODE=1 uv run --with pyyaml python bin/agent-workflow.py verify "$P0_PARENT_RUN_ID" --from-diff --execute
git diff --check origin/main...HEAD
```

Expected: all task-related checks PASS; unrelated main debt remains separately classified.

- [ ] **Step 3: Push, open one PR, and wait for required checks**

```bash
P0_PARENT_BRANCH="$(git branch --show-current)"
git push -u origin "$P0_PARENT_BRANCH"
gh pr create --base main --head "$P0_PARENT_BRANCH" \
  --title "feat(plan): support value-exempt BET completion" \
  --body "Implements BET-Y1Q3-T4-02 completion-policy prerequisite; no BET status/value evidence changes."
P0_PARENT_PR="$(gh pr view --json number --jq .number)"
gh pr checks "$P0_PARENT_PR" --watch --interval 10
```

Expected: required contexts `phase-gate` and `bet-done-transition` plus relevant CI are successful. Do not merge on queued, cancelled, startup-failure, or missing checks.

- [ ] **Step 4: Merge and verify main**

```bash
gh pr merge "$P0_PARENT_PR" --squash --delete-branch
git fetch --no-recurse-submodules origin main
git show origin/main:bin/plan/bet-ledger.py | rg "delivery_accepted"
```

Expected: merged commit is reachable from `origin/main`; the branch and owned implementation clone are retired after evidence capture.

---

### Task 3: Reconcile Child Spec and Write-Surface Drift

**Files:**
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp1-honest-scene-gate-design.md`
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp2-honest-agent-cell-receipt-design.md`
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp3-canonical-outbox-publisher-design.md`
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp4-principal-authority-binding-design.md`
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp5-human-adjudication-value-design.md`
- Review/amend under each child BET: `docs/superpowers/specs/2026-08-28-product-p0-wp6-physical-recovery-drill-design.md`
- Modify with each amendment: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Consumes: six implementation-plan code audits against current main.
- Produces: accepted child Specs whose write surfaces and acceptance claims cover the actual production path; each amendment is merged before that child implementation run starts.

- [ ] **Step 1: Apply the WP1 operational correction**

WP1 must state that the real repository blocker canary advances operational to `PROVEN`, while value remains `NOT_PROVEN`. Update its accepted Spec digest in the ledger. Do not start WP1 code work from the pre-amendment binding.

- [ ] **Step 2: Apply the WP2 authority and regression-surface correction**

WP2 must consume WP4's merged `validate_admitted_principal_context` helper, limit its only successful effect to `sandbox_digest_ref`, and authorize `tests/test_age_v2_e2e.py` plus `tests/test_age_v2_production.py`. It must not describe the no-external-side-effect sandbox digest as a generated document, backup, or real test execution.

- [ ] **Step 3: Apply the WP3 production-consumer correction**

WP3 must authorize the existing OMO ledger entrypoint and its focused tests, specify the one real destination adapter and lifecycle owner, add `outbox_receipt(event_id, destination)`, and freeze the migration strategy. If no existing owner can run `publish_due` without adding a second scheduler/dispatcher, stop and return to design review; a library-only publisher cannot claim operational `PROVEN`.

- [ ] **Step 4: Apply the WP4 production-propagation correction**

WP4 must cover the actual OMO PEP propagation seam, Cockpit credential-bound auth seam, and WorkflowAdmitted propagation needed for the production canary. If native ECOS `PolicyDecision` fields are required, add consumer-first/schema-last write surfaces explicitly; do not hide that model change in generated files.

- [ ] **Step 5: Apply the WP5 canonical lineage/query correction**

WP5 must specify one `DecisionOutcome.Recorded.v1` Event Ledger event containing adjudication and outcome logical objects, add the missing Cockpit outcomes test, and prevent file/YAML shadow projections from becoming qualifying truth. It may depend only on WP4's verified authority receipt, not caller-supplied principal text.

- [ ] **Step 6: Apply the WP6 two-stage human confirmation correction**

WP6 must distinguish pre-execution `approval_ref` from post-result `confirmation_ref`. Equal digests without external post-result confirmation keep `human_confirmed=false` and `meets_physical_gate=false`.

- [ ] **Step 7: Validate every amendment before implementation**

For each child: merge the Spec/digest amendment, verify `prepare_bet_execution` compiles the new WorkPacket, close the superseded planning run as blocked, and start a fresh implementation run from merged main. Expected: no child edits against an unmerged or drifted Spec binding.

---

### Task 4: Execute Wave A with Two Independent Writers

**Files:**
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp1-honest-scene-gate.md`
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp4-principal-authority-binding.md`

**Interfaces:**
- Consumes: merged Task 2 completion policy.
- Produces: WP1 and WP4 child/root mainline evidence, each with `delivery_accepted` and value `NOT_PROVEN`.

- [ ] **Step 1: Confirm both BETs are claimable and the parent prerequisite is merged**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-03
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-04
git show origin/main:bin/plan/bet-ledger.py | rg "delivery_accepted"
```

Expected: both child BETs are claimable; the value-exempt predicate is present on main.

- [ ] **Step 2: Create one Orca Run and two independent Tasks**

```bash
P0_WAVE_A_RUN="$(orca orchestration run-create --objective "Product P0 Wave A: honest Scene gate and principal authority" --json | jq -r .result.run.id)"
P0_WP1_TASK="$(orca orchestration task-create --spec "Execute BET-Y1Q3-T4-03 exactly from its accepted Spec and WP1 plan; root-only writer." --json | jq -r .result.task.id)"
P0_WP4_TASK="$(orca orchestration task-create --spec "Execute BET-Y1Q3-T4-04 exactly from its accepted Spec and WP4 plan; OMO then Cockpit then Agora then root." --json | jq -r .result.task.id)"
test -n "$P0_WAVE_A_RUN" && test -n "$P0_WP1_TASK" && test -n "$P0_WP4_TASK"
```

Expected: two ready tasks, no third implementation writer.

- [ ] **Step 3: Start both workers in independent top-level clones**

```bash
orca orchestration worker-start --task "$P0_WP1_TASK" --worktree new-top-level \
  --repo path:/Users/xiamingxing/Workspace --name product-p0-wp1 --agent codex --setup run --json
orca orchestration worker-start --task "$P0_WP4_TASK" --worktree new-top-level \
  --repo path:/Users/xiamingxing/Workspace --name product-p0-wp4 --agent codex --setup run --json
```

Expected: exactly two supervised Dispatches. Shared ledger, retros, and root pointer finalization remain coordinator-owned and serialized.

- [ ] **Step 4: Wait for both terminal outcomes and release resources**

```bash
P0_WAVE_A_DELIVERY="$(orca orchestration check --wait --types worker_done,escalation,question --timeout-ms 60000 --json)"
P0_SETTLED_DISPATCH="$(printf '%s' "$P0_WAVE_A_DELIVERY" | jq -r '.result.messages[] | select(.type=="worker_done") | (.payload | fromjson | .dispatchId)' | head -1)"
test -n "$P0_SETTLED_DISPATCH"
orca orchestration worker-release --dispatch "$P0_SETTLED_DISPATCH" --json
```

Repeat bounded waits until both Dispatches settle. Expected: worker terminals archived/released; no terminal is released on timeout, heartbeat, or question.

- [ ] **Step 5: Independently verify, merge, and serialize completion evidence**

Execute each child plan's review/CI/main/root-pointer steps. Update WP1 then WP4 completion matrices in separate coordinator commits only after direct receipts exist. Expected: both BETs derive `delivery_accepted`; both value axes remain `NOT_PROVEN`.

---

### Task 5: Execute Wave B Sequentially

**Files:**
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp2-honest-agent-cell-receipt.md`
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp3-canonical-outbox-publisher.md`

**Interfaces:**
- Consumes: WP4 authority receipt contract.
- Produces: WP2 durable effect receipts, then WP3 canonical outbox delivery.

- [ ] **Step 1: Confirm WP2 unlocks only after WP4 is done**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-05
```

Expected: claimable only when `BET-Y1Q3-T4-04` is `done` with `delivery_accepted`.

- [ ] **Step 2: Execute, review, merge, and close WP2**

Use the WP2 plan in one independent OMO child clone, then one root pointer PR. Expected: every effect success has a durable receipt; all rejection paths prove zero side effects; WP2 becomes `delivery_accepted`, value `NOT_PROVEN`.

- [ ] **Step 3: Confirm WP3 unlocks after WP2**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-06
```

Expected: claimable only after WP2 is `done`.

- [ ] **Step 4: Execute, review, merge, and close WP3**

Use the WP3 plan in one independent OMO child clone, then one root pointer PR. Expected: one canonical production consumer, lease exclusion, deterministic retry/backoff, uncertain transport preservation, restart replay, and `delivery_accepted` with value `NOT_PROVEN`.

---

### Task 6: Execute Wave C with Two Independent Writers

**Files:**
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp5-human-adjudication-value.md`
- Plan: `docs/superpowers/plans/2026-08-28-product-p0-wp6-physical-recovery-drill.md`

**Interfaces:**
- Consumes: WP1 honest scene gate, WP4 authority identity, and WP3 durable publication path.
- Produces: WP5 real principal-bound outcome and WP6 measured physical recovery.

- [ ] **Step 1: Confirm both dependency sets are complete**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-07
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check BET-Y1Q3-T4-08
```

Expected: both claimable; no unresolved dependency remains.

- [ ] **Step 2: Dispatch exactly two independent writers**

Create one Orca Run with WP5 and WP6 Tasks, then start two independent top-level workers. WP5 owns OMO/Cockpit child-first code; WP6 owns root recovery code. Shared ledger, value evidence, and root pointer changes remain serialized by the coordinator.

- [ ] **Step 3: Complete engineering PRs before human/physical canaries**

Expected: WP5 and WP6 focused RED/GREEN suites and child/root CI pass before any real adjudication or physical drill. Test fixtures do not count as operational or value evidence.

- [ ] **Step 4: Run the two human-gated canaries**

WP5: present one real Decision Inbox item and record one authority-bound human verdict. WP6: run backup/restore/integrity/replay against one explicitly approved non-production source and empty isolated target. Expected: direct immutable receipts; no automatic human confirmation.

- [ ] **Step 5: Serialize final completion matrices**

Expected: WP5 derives `outcome_accepted` only with `real_signal`, `human_verdict`, `revision`, `time_burden`, authority digest, and durable `decision_outcome`. WP6 derives `delivery_accepted` with value `NOT_PROVEN`.

---

### Task 7: Parent Cross-WorkPacket Acceptance and Cleanup

**Files:**
- Create: `docs/reports/2026-08-28-product-p0-truth-loop-closeout.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`
- Create: `.omo/_knowledge/retros/BET-Y1Q3-T4-02.md`

**Interfaces:**
- Consumes: six child completion matrices, merged mainline receipts, operational canaries, and WP5 value evidence.
- Produces: one parent completion decision referencing WP5 immutable value evidence without copying the value sample.

- [ ] **Step 1: Run the cross-workpacket engineering regression**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_scene_card_lifecycle_check.py -q
cd projects/omo && uv run pytest \
  tests/test_resident_executor_truth.py \
  tests/test_event_outbox_publisher.py \
  tests/test_sovereignty_policy_enforcement.py \
  tests/test_sovereignty_mandate_admission.py \
  tests/test_personal_episode.py \
  tests/test_engineering_delivery_consumer.py -q
cd ../cockpit && uv run pytest \
  src/cockpit/tests/test_agent_runtime_server.py \
  src/cockpit/tests/test_agent_runtime_mcp_server.py \
  src/cockpit/tests/test_api_decision_inbox.py \
  src/cockpit/tests/test_api_outcomes.py -q
cd ../agora && uv run pytest tests/unit/test_capability_gateway.py -q
```

Expected: all focused suites PASS on the final root tree.

- [ ] **Step 2: Verify root/child main ancestry and no stale gitlink**

```bash
python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main --json
```

Expected: every changed gitlink resolves to an authoritative child-main descendant.

- [ ] **Step 3: Re-read operational and value receipts after restart**

Re-run the canonical read-only observers for effect receipts, outbox state, principal authority digest, decision outcomes, and recovery receipts. Expected: stable IDs/digests/counts after process restart; no fixture or synthetic record qualifies.

- [ ] **Step 4: Write the closeout report and retro**

The report must contain six independent verdicts, exact PR/merge SHAs, CI URLs, main ancestry, canary/replay/cleanup receipts, remaining debt, and the value firewall. The retro must state where concurrency helped, where shared SSOT/root pointer serialization was required, and what mechanism changed.

- [ ] **Step 5: Update the parent completion matrix without duplicating value truth**

Reference WP5's immutable `real_signal`, `human_verdict`, `revision`, `time_burden`, attestation, authority digest, and decision outcome receipts. Do not generate a second sample. Expected: parent derives `outcome_accepted` only if every child is `done` and all parent `done_when` assertions are directly proven.

- [ ] **Step 6: Run final gates and close the parent workflow**

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py lint
make doc-ssot-lint
make gac-local-gate
P0_PARENT_RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py status --json | jq -r .current_run_id)"
test -n "$P0_PARENT_RUN_ID"
uv run --with pyyaml python bin/agent-workflow.py verify "$P0_PARENT_RUN_ID" --from-diff --execute
make agent-workflow-closeout RUN_ID="$P0_PARENT_RUN_ID"
```

Expected: Product P0 introduces no new baseline errors; all task-related required checks PASS.

- [ ] **Step 7: Merge the final parent PR and retire all owned resources**

After required checks pass, squash merge the final parent PR. Verify `origin/main`, release all workflow locks, delete merged remote branches, and retire every owned clone through the registered lifecycle or a recoverable Trash move with a receipt. Expected: zero live/stale Product P0 locks and zero retained writer terminals unless explicitly requested by the user.

---

## Self-Review

- Spec coverage: parent completion policy, child Spec reconciliation, Wave A/B/C, all six child Specs, root/child ordering, value firewall, canaries, and cleanup are mapped to Tasks 1-7.
- Placeholder scan: no unspecified implementation, error handling, test, command, or owner remains.
- Type consistency: `value_indicator_policy` is a BET-level boolean; `validate_completion_evidence` receives it explicitly; `delivery_accepted` never accepts value evidence; WP5 remains `outcome_accepted`.
- Concurrency consistency: Wave A and C have two independent implementation writers; Wave B is sequential; all shared SSOT/root integration is coordinator-serialized.
