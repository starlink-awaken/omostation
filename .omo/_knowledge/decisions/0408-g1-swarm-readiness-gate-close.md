---
id: ADR-0408
title: G-1 Swarm Readiness Gate Close — six SR direct evidence
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-11
related:
  - ADR-0407
  - ADR-0371
  - ADR-0220
type: ssot
---

# ADR-0408: G-1 Swarm Readiness Gate Close — Six SR Direct Evidence

## WHY

G-1 (Swarm Readiness) is the control-infrastructure gate defined in
`docs/architecture/blueprint-multi-agent-execution-control-v1.md` §18.
Before any business swarm (W0–W6) launches, the blueprint requires six
Swarm Readiness scenarios (SR-01–SR-06) to pass with direct evidence.

Prior to this decision, G-1 remained open because the 2026-08-09 baseline
(blueprint §3, lines 67-73) showed multiple BLOCKED conditions: workflow
`status.ok=false` with halt decision, stale closed-run locks, active runs
missing expected locks, closed runs without evidence/verify events,
delegation preflight unreachable, and Agora port 7431 down. The risk of
keeping G-1 open indefinitely
is that it blocks all downstream waves and allows nonblocking follow-ups
to accumulate without a forcing function.

The governed run `20260811T102723Z-governance-audit-c4b27a2e` and the
independent recertification (Orca task `task_38cfad0c0128`) produced all
six SR evidence trails. This ADR formally records that closure.

## WHAT

**Decision**: G-1 closes on six SR direct evidence, each with a distinct
evidence type — NOT six HTTP calls.

### Evidence by SR

| SR | Evidence type | Key result |
|----|--------------|------------|
| **SR-01** Workflow compliance | `agent-workflow.py status` + compliance | `status: ok`, 0 stale locks, P74 OK, `compliance=continue` |
| **SR-02** Delegation infrastructure | `delegation-preflight.py` + `delegation-alias-check.py` | Preflight PASS; endpoint reachable; 7 actual dispatch bindings resolved |
| **SR-03** A2A / Agora | `curl http://127.0.0.1:7431/health` + Orca dependency-task receipt | Services 35/35, audit chain 75/75; 6× HTTP 200 with lifecycle submitted/submitted/canceled/canceled |
| **SR-04** Work Packet M2 | `pytest test_work_packet_compiler.py test_mof_agent_execution_contracts.py` | 46 tests passed; same hash across platforms |
| **SR-05** Independent verifier | `pytest TestBuildVerificationReceipt` | 11 tests passed; read-only, direct-measurement, model-independence enforced |
| **SR-06** R1 rehearsal | `pytest test_sr06_rehearsal.py` + `sr06_rehearsal.py` script | 37 tests + script exit 0; `all_verdicts_valid=true`, `rollback_verified=true` |

**Total ECOS tests**: 105 passed via
`uv run --with pytest python -m pytest tests/test_mof_agent_execution_contracts.py tests/test_work_packet_compiler.py tests/test_sr06_rehearsal.py -q`.

### SR-03 detail

SR-03 is the **only** SR with HTTP 200 observations. The identifiers are:

- **trace_id**: `g1-sr03-recert-20260811T101647Z`
- **A2A task id**: `task_3bbcbfeb410402cf`
- **Orca evidence task**: `task_50f6dcc7a7af`

Health metrics (services 35/35, audit chain 75/75) are **Agora health output**,
not `gac-local-gate` output.

### Boundaries

- **SR-06 implementation evidence ran in a temp sandbox, NOT a production
  Agent dispatch.** The rehearsal script exercised dispatch→verify→reject/accept→rollback
  mechanics in a temp sandbox. Closing G-1 does not assert SR-06 is
  production-ready.
- **Health/audit metrics belong to SR-03**, not to a generic gate check.
  Services 35/35 and audit chain 75/75 are Agora health indicators.
- **No broad completion claim beyond G-1.** This ADR certifies only the
  G-1 Swarm Readiness gate; it does not assert the completion status of
  later waves. Wave completion remains governed by their own BET/evidence.

### Carried-forward nonblocking follow-ups

These items are carried forward as nonblocking. This audit cites no registry
IDs for them and registration has not been proven. They are **not assigned to W2-03**:

1. SR-02: `mid-local` / `mythos-fast` gateway routing gaps (not actual dispatch bindings)
2. SR-02: gateway `/v1/models` behind auth (indirect listing only)
3. SR-03: send/get/cancel not independently replayed (dependency-task receipt only)

### W2-03 scope (next gate)

W2-03 is PDP/PEP enforcement at the Capability Gateway with `PolicyDecision`
and `ActionReceipt` written to the Ledger, dependent on W2-02. It does NOT
include alias/model/setup debt resolution.

W2-04 remains Episode / Role Portfolio / Inbox projections.

## Rejected Alternatives

### Alternative A: Close G-1 on aggregate health/audit scores alone (no SR receipts)

Rejected. Health 35/35 and audit chain 75/75 demonstrate Agora stability but
do not constitute per-SR execution evidence. The blueprint §18 explicitly
requires each SR to have its own direct evidence — workflow compliance,
preflight, A2A lifecycle, Work Packet hash, verifier enforcement, and
rehearsal chain. Aggregate scores are a byproduct of SR-03, not a substitute
for the other five.

### Alternative B: Close G-1 only after SR-06 is promoted to production dispatch

Rejected. The blueprint §18 requires a bounded R1 dispatch→verify→reject/accept→rollback
rehearsal; it does not mandate production dispatch. This implementation evidence
ran in a temp sandbox and directly verified dispatch→reject→accept→rollback mechanics
with `all_verdicts_valid=true` and `rollback_verified=true`. Bundling production
promotion into G-1 would conflate two distinct concerns (readiness vs production
readiness) and delay G-1 indefinitely.

### Alternative C: Map all six SRs to HTTP 200 observations

Rejected. The six SRs have fundamentally different evidence types:
SR-01 is workflow status, SR-02 is preflight, SR-03 is A2A lifecycle,
SR-04 is schema/hash, SR-05 is verifier enforcement, SR-06 is rehearsal
script output. Collapsing them into six identical HTTP calls would erase
the distinction between control-plane compliance, delegation infrastructure,
A2A transport, contract integrity, verification independence, and end-to-end
rehearsal — defeating the purpose of a six-faceted readiness gate.

## NEXT

1. **W2-03** (PDP/PEP enforcement at Capability Gateway) is the next gate,
   dependent on W2-02.
2. **Audit trail**: This ADR and the companion audit
   (`2026-08-11-g1-swarm-readiness-closeout.md`) form the persistent evidence
   record. If G-1 is re-opened, both documents must be re-validated.
3. **Carried-forward follow-ups** are carried by this audit pending separate
   registration/triage. They must not be silently resolved without updating
   this ADR's status if the resolution changes any SR evidence boundary.
