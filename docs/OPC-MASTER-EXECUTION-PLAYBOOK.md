# OPC Master Execution Playbook

> Date: 2026-06-11
> Status: execution control baseline
> Scope: all remaining OPC phases after P2 material closeout
> Owner of final acceptance: Codex (this thread)

---

## 1. Purpose

This document is the single execution playbook for all remaining OPC work.

It exists to stop three recurring failures:

1. declaring a phase passed before real evidence exists
2. mixing design completion with implementation completion
3. letting docs, task files, and runtime evidence drift apart

From this point on, all agents should execute against this playbook, submit evidence by sub-gate, and avoid applying for broad acceptance before the current sub-gate is actually closed.

---

## 2. Current Baseline

As of this document:

- P0: passed
- P1: conditionally passed
- P1.5: governance baseline accepted
- P2: implementation complete; Gate C passed (2026-06-11)
- P3: implementation complete; Gate D passed (2026-06-12)
- P4: implementation complete; Gate E passed (2026-06-12, E1-E4 closed)

Current known truths:

- T2: `cockpit search --all` unified response wired into CLI output (text + JSON consistent)
- T3: multi-zone recall verified {local:0, kos:10, vault:10} for q='AGENTS'
- T4: 8/8 source metadata complete on local search
- C4: trace writeback to cockpit research verified (dedup window, archive retention)
- D3: planner/researcher/reviewer thin-binding role split verified
- D4: completed-result handoff index + reclaim_due follow-up verified
- D5: replayable three-worker thin-binding demo verified
- cross-repo persistence risks remain tracked via formal OMO debt

---

## 3. Execution Contract

All remaining work must follow the same contract:

1. only execute the current sub-phase
2. only apply for the current sub-gate
3. include real command output, not prose-only claims
4. update docs and task status only after evidence exists
5. keep `docs`, `.omo/tasks`, and runtime behavior aligned

No agent may apply for a later gate while an earlier gate in the same phase is still open.

---

## 4. Global Red Lines

These are non-negotiable.

### 4.1 Evidence red lines

- Do not write `passed`, `complete`, `ready`, or `opened` before runtime evidence exists.
- Do not replace failed evidence with narrative explanation.
- Do not present mock output, placeholder output, or pasted expected output as actual evidence.
- Do not treat help text, comments, or design diagrams as implementation proof.

### 4.2 Architecture red lines

- Do not introduce a new external entry path outside cockpit CLI, Agora MCP, and cockpit HTTP.
- Do not bypass Agora for cross-layer agent calls.
- Do not build trusted memory on raw ungoverned JSONL or non-atomic writes.
- Do not let business modules call model providers directly once P4 execution starts.
- Do not let product journeys depend on manual repo-by-repo operator knowledge.

### 4.3 Governance red lines

- Do not change phase status in one file only.
- Do not mark P3 opened before Gate C passes.
- Do not mark P4 production-ready before model routing, fallback, and cost telemetry are verified.
- Do not mark P5 passed from demos alone; scenario runs must be repeatable.
- Do not mark P6 passed if automated upgrade suggestions can become active without human approval.
- Do not mark P7 passed without release-train evidence and retrospective coverage.

### 4.4 Delivery red lines

- Do not submit giant mixed batches across multiple phases.
- Do not bundle speculative refactors with gate-close work.
- Do not move to the next phase until the current phase gate note, readiness doc, and task file all match.

---

## 5. Required Self-Check Before Any Acceptance Request

Every agent must run this self-check before asking for review:

1. What exact sub-gate is being requested?
2. What exact command or test proves it?
3. What exact file/line records the new state?
4. What is still not done?
5. What debt or risk remains open?

If any of those five answers is vague, the gate request is invalid.

---

## 6. Standard Acceptance Package Format

Every sub-gate request must use this format:

```text
Gate Request: <Phase>-<Subgate>

1. Objective
2. Commands run
3. Runtime evidence summary
4. Files changed + line references
5. Self-check against gate criteria
6. Open items / residual risk
7. Requested verdict: pass / conditional / reject
```

No agent should submit broad summaries without the command and file evidence sections.

---

## 7. Phase P2 — Memory Spine Closeout

### Phase outcome target

Pass Gate C and close P2 as a working memory spine baseline.

### P2.1 — Local Contract Hardening

Goal:
- make `cockpit search --all` a stable unified response path

Tasks:
- P2.1-T1 unify top-level response fields: `zone`, `query`, `zone_count`, `results`, `total`
- P2.1-T2 make `--json` and text mode represent the same facts
- P2.1-T3 normalize local item shape and defaults
- P2.1-T4 harden BOS failure handling so local path still returns successfully
- P2.1-T5 add focused tests for local-only, `--all`, `--json`, and empty results

Gate C1 criteria:
- `search --all --json` returns valid JSON
- top-level response fields are complete
- no traceback when KOS is unavailable
- tests exist and pass

Red lines:
- no fake `zone_count`
- no crash path hidden by docs-only updates

### P2.2 — KOS Activation

Goal:
- make KOS a real queried zone, not a placeholder blob

Tasks:
- P2.2-T1 verify actual query propagation into `bos://memory/kos/search`
- P2.2-T2 parse KOS results into unified result items
- P2.2-T3 make `zone_count["kos"]` a real count, not a stub
- P2.2-T4 implement first-pass dedupe between local and KOS
- P2.2-T5 add tests or replayable verification for KOS-active and KOS-fail paths

Gate C2 criteria:
- one real query returns non-empty local and/or KOS results through unified format
- KOS output is structured as result items, not raw stdout
- `zone_count.kos` matches actual merged items

Red lines:
- do not count a single subprocess stdout blob as one valid knowledge hit
- do not call Gate C2 passed if query does not actually reach KOS

### P2.3 — Vault Activation

Goal:
- activate one real document-vault source into unified search

Tasks:
- P2.3-T1 choose one concrete vault source
- P2.3-T2 build unified result mapping for vault items
- P2.3-T3 connect vault into `--all`
- P2.3-T4 produce one real hit from vault data
- P2.3-T5 add source attribution and zone counting for vault

Gate C3 criteria:
- at least one real query hits two zones
- `zone_count` shows more than one non-zero zone in at least one acceptance run
- vault results carry T4 metadata

Red lines:
- no file listing masquerading as search
- no empty shell route counted as zone activation

### P2.4 — Real Trace Closure

Goal:
- prove one real question can complete the minimum recall loop

Tasks:
- P2.4-T1 define two fixed acceptance queries
- P2.4-T2 capture real collect/search/output evidence
- P2.4-T3 identify actual ingest landing point in current system
- P2.4-T4 identify actual archive landing point in current system
- P2.4-T5 write a `Real Trace` section into the P2 phase doc

Gate C4 criteria:
- at least one query has a trace with input, zones queried, result count, and writeback/archive evidence
- trace is reproducible by command and file reference

Red lines:
- do not claim ingest/archive from design text alone
- do not close Gate C with local-only prose and no trace

### P2 Final Gate C

Gate C passes only when:
- C1 passed
- C2 passed
- C3 passed
- C4 passed

Only then may agents write:
- `Gate C: passed`
- `P2: complete`
- `P3: opened`

---

## 8. Phase P3 — Swarm Execution Spine

### Phase outcome target

Turn P3 from design baseline into a governed runnable swarm path.

### P3.1 — Task Object Runtime Binding

Goal:
- bind the P3 task object schema to actual OMO/swarm/runtime execution records

Tasks:
- P3.1-T1 map OMO task state to swarm task state
- P3.1-T2 define persisted worker-task IDs and parent/child links
- P3.1-T3 define required audit fields at runtime
- P3.1-T4 define result artifact references
- P3.1-T5 verify one task record can be created and updated through lifecycle

Gate D1 criteria:
- one task can move through planned/assigned/running/completed
- audit fields update through runtime
- parent/child lineage is inspectable

Red lines:
- no standalone design schema accepted as runtime proof

### P3.2 — Dispatch and Heartbeat

Goal:
- make worker dispatch, heartbeat, retry, and dead-letter behavior real

Tasks:
- P3.2-T1 implement dispatch path
- P3.2-T2 implement heartbeat emission and timeout policy
- P3.2-T3 implement retry accounting
- P3.2-T4 implement dead-state transition
- P3.2-T5 bind dead transition to debt registration trigger

Gate D2 criteria:
- one worker success path verified
- one worker failure path verified
- one retry/dead path verified

Red lines:
- no “retry by rerunning command manually” counted as retry logic

### P3.3 — Role Realization

Goal:
- make core agent roles operational rather than descriptive

Tasks:
- P3.3-T1 activate planner role
- P3.3-T2 activate researcher role
- P3.3-T3 activate coder/reviewer split
- P3.3-T4 activate verifier/operator path where needed
- P3.3-T5 verify one decomposition run uses at least three roles

Gate D3 criteria:
- at least three roles participate in one real goal
- each role has clear input/output boundaries

Red lines:
- no single omnipotent worker pretending to be a swarm

### P3.4 — Result Writeback and Audit

Goal:
- write worker results back to memory and governance

Tasks:
- P3.4-T1 define result writeback sink
- P3.4-T2 connect writeback to memory/audit
- P3.4-T3 connect failure to debt
- P3.4-T4 expose task result lookup path
- P3.4-T5 verify result traceability end to end

Gate D4 criteria:
- one completed worker result is queryable after execution
- one failed worker creates governed follow-up

Red lines:
- no swarm result accepted if it cannot be found later

### P3.5 — Minimal Demo

Goal:
- execute one governed three-worker demo

Tasks:
- P3.5-T1 pick fixed goal
- P3.5-T2 decompose into at least three tasks
- P3.5-T3 execute with role separation
- P3.5-T4 collect results and audit trail
- P3.5-T5 update P3 implementation doc with replay instructions

Gate D5 criteria:
- one replayable three-worker demo succeeds

P3 Final Gate D:
- D1-D5 all passed

---

## 9. Phase P4 — Model Gateway and Compute Mesh

### Phase outcome target

Centralize model and compute selection through governed infrastructure.

### P4.1 — LLM Gateway Enforcement

Tasks:
- P4.1-T1 inventory direct provider calls
- P4.1-T2 route supported paths through `llm-gateway`
- P4.1-T3 define gateway request/response contract
- P4.1-T4 define model capability metadata
- P4.1-T5 verify one business path uses gateway only

Gate E1 criteria:
- at least one business execution path uses `llm-gateway`
- direct provider calls are removed or registered as debt

Red lines:
- no new direct provider integration outside gateway

### P4.2 — Selection and Budget Policy

Tasks:
- P4.2-T1 define selection modes: cost/speed/capability/balanced
- P4.2-T2 define token/cost/time budget schema
- P4.2-T3 attach budget policy to swarm tasks
- P4.2-T4 enforce budget failure behavior
- P4.2-T5 verify policy changes model selection in practice

Gate E2 criteria:
- model choice is explainable by policy
- budget breach has observable behavior

### P4.3 — Compute Mesh Activation

Tasks:
- P4.3-T1 define worker registration contract
- P4.3-T2 define heartbeat and health policy
- P4.3-T3 define allocation/scheduling policy
- P4.3-T4 connect swarm dispatch to compute availability
- P4.3-T5 verify one task scheduled against live worker availability

Gate E3 criteria:
- worker availability influences execution path

### P4.4 — Telemetry and Fallback

Tasks:
- P4.4-T1 record provider, model, cost, latency
- P4.4-T2 record compute allocation
- P4.4-T3 define provider fallback policy
- P4.4-T4 verify one fallback path
- P4.4-T5 surface metrics into OMO reporting

Gate E4 criteria:
- one fallback path verified
- cost/latency visible per task or run

P4 Final Gate E:
- E1-E4 all passed

---

## 10. Phase P5 — North Star Product Scenarios

### Phase outcome target

Make OPC feel like one product through repeatable user-value journeys.

### P5.1 — Technical Radar

Tasks:
- P5.1-T1 define ingest sources
- P5.1-T2 define ranking/scoring logic
- P5.1-T3 define output format
- P5.1-T4 write results back to memory and OMO tasks
- P5.1-T5 verify one repeatable weekly radar run

Gate F1 criteria:
- one radar run produces sourced upgrade candidates

### P5.2 — Work Assistant

Tasks:
- P5.2-T1 define one real work-assistant question path
- P5.2-T2 use memory recall and structured response
- P5.2-T3 surface source/timestamp/next action
- P5.2-T4 write useful result back to memory
- P5.2-T5 verify repeatability with a second prompt

Gate F2 criteria:
- at least two work questions produce sourced useful outputs

### P5.3 — Family Health

Tasks:
- P5.3-T1 define privacy class and access boundaries
- P5.3-T2 define record ingestion and normalization
- P5.3-T3 define summary and next-action outputs
- P5.3-T4 define safe memory writeback rules
- P5.3-T5 verify one controlled scenario end to end

Gate F3 criteria:
- one family-health scenario runs with privacy classification and source attribution

Red lines:
- no unsourced medical summary
- no privacy-blind provider routing

### P5.4 — Product Surface Consolidation

Tasks:
- P5.4-T1 choose primary user-facing surfaces
- P5.4-T2 remove repo-knowledge dependency from user flow
- P5.4-T3 define scenario launch points in cockpit/Web
- P5.4-T4 define scenario result review flow
- P5.4-T5 verify a user can run at least two scenarios from product surfaces

Gate F4 criteria:
- at least two scenarios are runnable without repo-level operator knowledge

P5 Final Gate F:
- F1-F4 all passed

---

## 11. Phase P6 — Self-Evolution Loop

### Phase outcome target

Create a governed recurring improvement loop without self-activating unsafe changes.

### P6.1 — Candidate Discovery

Tasks:
- P6.1-T1 define radar inputs
- P6.1-T2 define gap extraction logic
- P6.1-T3 define evidence link requirement
- P6.1-T4 define candidate registry
- P6.1-T5 verify weekly candidate generation

Gate G1 criteria:
- one weekly run yields at least three evidence-backed candidates

### P6.2 — Scoring and Planning

Tasks:
- P6.2-T1 define value/risk/cost/dependency/verification scoring
- P6.2-T2 define ranking output
- P6.2-T3 map candidates to planned OMO tasks
- P6.2-T4 require human approval marker
- P6.2-T5 verify one candidate becomes a planned task only

Gate G2 criteria:
- approved candidate enters planned state
- unapproved candidate cannot become active

### P6.3 — Swarm Execution Link

Tasks:
- P6.3-T1 connect approved planned task to swarm execution intake
- P6.3-T2 connect execution results to memory and audit
- P6.3-T3 connect failures to debt
- P6.3-T4 define retrospective writeback
- P6.3-T5 verify one approved improvement loop end to end

Gate G3 criteria:
- one approved candidate completes the loop from suggestion to audit

### P6.4 — Drift Detection

Tasks:
- P6.4-T1 detect entry drift
- P6.4-T2 detect doc drift
- P6.4-T3 detect memory-source duplication drift
- P6.4-T4 detect Agora bypass drift
- P6.4-T5 verify one drift case becomes debt or remediation

Gate G4 criteria:
- one real drift case is detected and routed correctly

P6 Final Gate G:
- G1-G4 all passed

---

## 12. Phase P7 — Governance Hardening and Release Train

### Phase outcome target

Turn OPC into a maintainable long-running operating system.

### P7.1 — Release Train

Tasks:
- P7.1-T1 define release cadence
- P7.1-T2 define release artifact checklist
- P7.1-T3 define phase summary template
- P7.1-T4 define rollback / hold rules
- P7.1-T5 verify one release cycle artifact pack

Gate H1 criteria:
- one full release package exists with summary, evidence, blockers, and debt

### P7.2 — Dashboard and Reporting

Tasks:
- P7.2-T1 define dashboard phase/blocker/debt view
- P7.2-T2 define scenario health view
- P7.2-T3 define model/compute cost view
- P7.2-T4 define memory quality view
- P7.2-T5 verify dashboard reflects current system state

Gate H2 criteria:
- dashboard surfaces current phase, blockers, debt, and quality signals

### P7.3 — Documentation Sync Discipline

Tasks:
- P7.3-T1 define SSOT mapping for roadmap docs
- P7.3-T2 define mandatory sync points after gate changes
- P7.3-T3 define stale-doc detection
- P7.3-T4 define remediation path
- P7.3-T5 verify one stale-doc case is caught and corrected

Gate H3 criteria:
- one stale-doc drift is detected and corrected through process

### P7.4 — Final Hardening Retrospective

Tasks:
- P7.4-T1 compile open debt and closed debt summary
- P7.4-T2 compile phase-by-phase retrospective excerpts
- P7.4-T3 compile product scenario readiness summary
- P7.4-T4 compile architecture constraints compliance summary
- P7.4-T5 prepare final acceptance package for unified review

Gate H4 criteria:
- final acceptance pack exists and is internally consistent

P7 Final Gate H:
- H1-H4 all passed

---

## 13. Unified Final Acceptance

I will only issue final unified acceptance when all of the following are true:

1. Gate C passed
2. Gate D passed
3. Gate E passed
4. Gate F passed
5. Gate G passed
6. Gate H passed
7. docs, task files, and runtime evidence are mutually consistent
8. at least two real product scenarios run repeatably
9. self-evolution remains human-approved
10. release-train evidence exists

Final acceptance signal target:

```text
opc_master_roadmap_complete
```

No intermediate agent may emit that signal.

---

## 14. What Agents Must Update At Every Gate

At minimum, after every sub-gate they must update:

1. the relevant phase doc under `docs/OPC-PHASE*.md`
2. the relevant readiness or closeout doc
3. the corresponding `.omo/tasks/...` record

If the task file moved from `planned/` to `done/`, all docs must update the path immediately.

---

## 15. Dispatch Prompt For External Agents

Use this exact instruction skeleton when delegating:

```text
You are executing one OPC sub-gate only.

Target sub-gate: <fill here>
Authority boundary: do not claim any later gate
Primary doc: docs/OPC-MASTER-EXECUTION-PLAYBOOK.md

Required output:
1. objective
2. commands run
3. runtime evidence
4. changed files + line references
5. self-check against gate criteria
6. residual risk
7. requested verdict

Red lines:
- no prose-only completion claims
- no status changes before evidence
- no cross-phase bundling
- no fake multi-zone or fake swarm execution
```

---

## 16. Reviewer Note

All later acceptance requests should be phrased as:

- `验收 Gate C1`
- `验收 Gate C2`
- `验收 Gate D3`
- `验收 Gate F2`
- `最终验收 OPC`

Do not ask for broad `验收` without naming the exact sub-gate.
