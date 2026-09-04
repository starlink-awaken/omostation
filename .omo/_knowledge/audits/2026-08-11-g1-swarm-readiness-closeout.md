---
lifecycle: history
owner: governance-team
last_updated: 2026-08-11
related:
  - ../decisions/0408-g1-swarm-readiness-gate-close.md
  - ../decisions/0407-truthful-ci-local-fast.md
  - ../decisions/0371-pasw-submodule-isolation.md
  - ../decisions/0220-swarm-coordination-discipline-m1-gate.md
---

# G-1 Swarm Readiness Closeout Audit — 2026-08-11

> **Governed run**: `20260811T102723Z-governance-audit-c4b27a2e`
> **Base commit**: `211a2a47` (origin/main)
> **Orca run**: `run_0c67696f96a7`
> **Independent recertification**: Orca task `task_38cfad0c0128`
> **Blueprint authority**: `docs/architecture/blueprint-multi-agent-execution-control-v1.md` §18
> **Scope**: Six Swarm Readiness (SR-01–SR-06) direct-evidence verification for G-1 gate close

---

## 1. Six-Row SR Evidence Matrix

Each row cites an exact authority check, a result, and a coverage limitation.
The six SRs do NOT each map to an HTTP call — only SR-03 carries HTTP lifecycle
observations.

| SR | Blueprint Definition (§18) | Authority Check | Result | Exact Evidence | Coverage Limitation |
|----|---------------------------|-----------------|--------|----------------|---------------------|
| **SR-01** Workflow compliance | `status.ok=true`, no stale/orphan/missing locks, no missing-evidence closeout | `PYTHONPATH="projects/omo/src" uv run --with pyyaml python bin/agent-workflow.py status` + `… compliance` | **PASS** | `status: ok`; `runs active=0 closed=0 locks=0 stale=0`; `compliance=continue`; `P74 solidification: [OK] 0 silent workflow(s)`; `requirement_iteration: [OK] mode=required` | None — direct authoritative tool output |
| **SR-02** Delegation infrastructure | canonical preflight PASS, endpoint reachable, every actual dispatch alias has routing | `PYTHONPATH="projects/omo/src" uv run --with pyyaml python bin/delegation-preflight.py` + `bin/delegation-alias-check.py` | **PASS** (nonblocking debt) | `RESULT: OK`; endpoint reachable HTTP 401 @ `127.0.0.1:4000`; 7 actual dispatch bindings resolved (build / coder / explore / plan / researcher / reviewer / scribe) | `mid-local` and `mythos-fast` exist only in opencode config — NOT among the 7 actual dispatch bindings; gateway `/v1/models` behind auth (indirect listing only); nonblocking per SR-02 wording |
| **SR-03** A2A / Agora | Agora healthy; send/get/cancel smoke test passes | `curl http://127.0.0.1:7431/health` + Orca dependency-task receipt | **PASS** | Live health: `services 35/35 healthy`, `audit_chain ok (75/75 verified)`, `backends 7 alive / 23 standby / 0 dead`, `issues: 0`, `debt: 0 open`. Dependency task send/get/cancel lifecycle: trace_id `g1-sr03-recert-20260811T101647Z`, A2A task id `task_3bbcbfeb410402cf`, Orca evidence task `task_50f6dcc7a7af`. **Six HTTP 200 observations** with task lifecycle states: submitted → submitted → canceled → canceled | send/get/cancel receipt is from the Orca dependency task (not independently replayed — `/v1/tools/call` MCP returned internal error); live health and audit chain are fresh and directly verified |
| **SR-04** Work Packet M2 | M2/Schema/Compiler generate same-hash platform instructions | `cd projects/ecos && uv run pytest tests/test_work_packet_compiler.py tests/test_mof_agent_execution_contracts.py -v` | **PASS** | 46 tests passed. M2 schemas: `work_packet.yaml` (10K), `completion_manifest.yaml` (8.2K). Same hash verified across platforms (opencode / kilocode / claude-code). Key tests: `test_hash_identical_across_platforms`, `test_payload_identical_across_platforms`, `test_rejects_done`, 4-state lifecycle (candidate/blocked/failed/archived), R0 empty-write-surface rule, R2 independent-verification requirement | None — hash identity, schema validation, platform rendering all directly tested |
| **SR-05** Independent verifier | Verifier read-only, independent model checks, direct measurement receipt | `cd projects/ecos && uv run pytest tests/test_work_packet_compiler.py::TestBuildVerificationReceipt -v` | **PASS** | 11 tests passed. `VerificationReceipt` enforces: `read_only=True` (rejects non-read-only), `direct_measurement=True` (rejects indirect), same model family rejected without override (`test_same_model_family_rejected_without_override`), deterministic receipt_hash, receipt_hash changes with verdict, at least one command check required, `__post_init__` enforces invariants even on direct construction | None — independence enforcement, read-only constraint, direct-measurement constraint all directly tested at schema + compiler level |
| **SR-06** R1 rehearsal chain | One R1 doc/small-code package completes dispatch→verify→reject/accept→rollback full chain | `cd projects/ecos && uv run pytest tests/test_sr06_rehearsal.py -v` + `uv run python src/ecos/ssot/tools/sr06_rehearsal.py` | **PASS** | 37 tests passed + direct script exit 0. Full chain: dispatch → reject → accept → rollback. Script reported `all_verdicts_valid: true`, `rollback_verified: true`. StateMachine bypass prevention (6 tests), tampered candidate → reject + different hash, wrong packet_hash → reject, rollback restores snapshot, revise loops back. Dispatch envelopes for 3 platforms share identical hash | Rehearsal runs in temp sandbox (not live production worktree); state-machine + hash + rollback mechanics fully exercised but not against a real Agent platform dispatch |

### Matrix summary

- **SR-03 is the only SR with HTTP 200 observations**: 6× HTTP 200 from the Agora send/get/cancel lifecycle.
- **SR-01 through SR-06 each has a distinct evidence type** — they are NOT six HTTP calls.
- **SR-03 health**: services 35/35 and audit chain 75/75 are Agora health metrics, not `gac-local-gate` output.
- **Total ECOS tests**: 105 passed across the three test files run together (SR-04 + SR-05 + SR-06 surfaces).

---

## 2. ECOS Test Command

The fresh ECOS evidence command was:

```bash
cd projects/ecos && uv run --with pytest python -m pytest \
  tests/test_mof_agent_execution_contracts.py \
  tests/test_work_packet_compiler.py \
  tests/test_sr06_rehearsal.py \
  -q
# → 105 passed
```

NOT `make test`. The 105 tests cover agent execution contracts, WorkPacket/compiler
and VerificationReceipt behavior, and SR-06 rehearsal mechanics — all green.

---

## 3. Merged PRs

### 3.1 Root repository (starlink-awaken/omostation)

| PR | Title |
|----|-------|
| #1341 | feat(sovereignty): land W2-02 delegation mandates |
| #1343 | fix(g1): make ci-local-fast evidence truthful |
| #1344 | chore(g1): advance OMO runtime state isolation |
| #1345 | chore(submodule): advance Agora SR-03 health |
| #1346 | chore(submodule): advance OMO heartbeat hardening |

### 3.2 OMO submodule (starlink-awaken/omostation-omo)

| PR | Title |
|----|-------|
| #27 | feat(sovereignty): add W2-02 delegation mandate runtime |
| #28 | fix(runtime): isolate adjudication observation state |
| #29 | fix(workflow): add fail-closed run heartbeat |
| #30 | fix(workflow): serialize run heartbeat renewal |

### 3.3 Agora submodule (starlink-awaken/omostation-agora)

| PR | Title |
|----|-------|
| #25 | fix(health): treat standby backends as non-fault |

---

## 4. Independent Recertification

The independent read-only recertification was performed as Orca task
`task_38cfad0c0128` on branch `starlink-awaken/g1-final-recert`, base
`origin/main @ 211a2a47b`. The report lives at
`/tmp/g1-recert-report-task_38cfad0c0128.md`.

**Recommendation: CLOSE (PASS)** — all six SRs pass with direct evidence.
105 total tests green across SR-04/05/06. SR-01 compliance is clean.
SR-02 preflight passes with nonblocking alias drift. SR-03 Agora is
live-healthy with dependency-task send/get/cancel receipt.

---

## 5. Carried-Forward Nonblocking Follow-Ups

The following items are carried forward as **nonblocking** follow-ups.
They are not assigned to W2-03; this audit cites no registry IDs and
registration has not been proven.

| Follow-up | Origin SR | Why nonblocking |
|-----------|-----------|-----------------|
| `mid-local` / `mythos-fast` gateway routing gaps | SR-02 | Not among the 7 actual dispatch bindings; informational per SR-02 wording |
| Gateway `/v1/models` behind auth — model listing indirect only | SR-02 | Does not affect dispatch alias resolution |
| SR-03 send/get/cancel not independently replayed in this session | SR-03 | Dependency-task receipt provides lifecycle evidence; live health directly verified |

These items are carried by this audit pending separate registration/triage.
They must not be conflated with W2-03 scope.

---

## 6. Next Gate: W2-03 Scope

**W2-03** scope is PDP/PEP enforcement at the Capability Gateway with
`PolicyDecision` and `ActionReceipt` written to the Ledger, dependent on
W2-02. It does NOT include alias/model/setup debt resolution.

**W2-04** remains Episode / Role Portfolio / Inbox projections.

---

## 7. Boundary

This audit covers only G-1 Swarm Readiness. It does not assert:
- Production-readiness of SR-06 (sandbox rehearsal only, not production dispatch).
- Resolution of carried-forward nonblocking follow-ups.
- Readiness of any wave beyond G-1.
