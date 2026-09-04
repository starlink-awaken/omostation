---
title: knowledge_capture_run_record_spec
type: doc
---

# Knowledge Capture Run Record Spec

> Scenario: `knowledge-capture-search`
> Status: draft, ready for first real run
> Date: 2026-06-05

## Purpose

This spec defines the smallest single-run record that can join:

- OMO scenario identity
- kairon route / event / trace identity
- gbrain execution identity
- OMO closeout evidence identity

It is intentionally narrow.

It does not define a general workflow engine.
It defines one correlation record for one main path.

## Non-Goals

This spec does not:

- replace OMO scenario or closeout documents
- replace `kairon` route/event logs
- replace `gbrain` receipts or eval capture rows
- claim a live run already exists

## Record Shape

One run record must carry at least these fields:

```text
scenario_id
request_id
request_mode
kairon_trace_id
kairon_route_surface
gbrain_execution_ref
result_status
capture_receipt
search_hit_refs
omo_evidence_refs
verification_refs
limits
```

## Field Rules

### scenario_id

- fixed to `knowledge-capture-search`
- comes from OMO scenario truth

### request_id

- unique per run attempt
- may be fixture-backed for dry runs
- must be the top-level correlation key when no stronger cross-system key exists

### request_mode

Allowed values:

- `template`
- `fixture-backed`
- `low-risk-live`

### kairon_trace_id

- the correlation id from `kairon` route / event / trace surface
- may come from `trace_id`, emitted event id, or a stable derived run id
- must not be omitted in non-template runs

### kairon_route_surface

Expected values for current architecture:

- `agora.server.mcp.route_call`
- `agora.web.events`
- `wksp.contracts`

Multiple values are allowed when one run crosses more than one `kairon` surface.

### gbrain_execution_ref

- points to the downstream execution identity
- can be a capture receipt, eval capture row, or a stable operation ref
- in a template run, placeholder is allowed

### result_status

Allowed values:

- `completed`
- `failed_with_recovery`
- `blocked`

### capture_receipt

- must be present for `completed`
- may be empty only when `result_status != completed`

### search_hit_refs

- zero or more downstream result refs
- for `completed`, at least one ref is expected

### omo_evidence_refs

Must include pointers to:

- scenario shell
- walkthrough
- closeout or recovery

### verification_refs

Must point to the verification commands or files that justify the run record.

### limits

- list what is still not proven by this run
- especially important for fixture-backed and low-risk-live runs

## Current Integration Points

This record is meant to sit on top of existing assets, not replace them:

- `docs/knowledge_capture_binding_walkthrough.md`
- `docs/knowledge_capture_scenario_binding_packet.md`
- `/Users/xiamingxing/Workspace/.omo/_truth/scenarios/knowledge-capture-search.yaml`
- `/Users/xiamingxing/Workspace/.omo/_delivery/evidence/phase16/scenario-shell.yaml`
- `/Users/xiamingxing/Workspace/.omo/_delivery/evidence/phase16/capture-search-walkthrough.yaml`

## First Acceptable Real Use

The first acceptable real record can still be non-production and low-risk.

It is enough if it proves:

```text
one scenario request
-> one kairon trace id or event id
-> one gbrain execution ref
-> one OMO evidence bundle
```

That is the minimum point where the path becomes "run-evidenced" instead of "audit-assembled".
