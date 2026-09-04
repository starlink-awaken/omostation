---
title: knowledge_capture_scenario_binding_packet
type: doc
---

# Knowledge Capture Scenario Binding Packet

> Scenario: `knowledge-capture-search`
> Scope: `runtime -> OMO -> kairon -> gbrain -> OMO`
> Date: 2026-06-05
> Goal: assemble one cross-project evidence packet for the current main path.

## What this packet proves

This packet does not claim a full live product loop.

It proves something narrower and more useful:

- the scenario contract already exists in OMO
- `kairon` already has a real binding surface for route / event / trace
- `gbrain` already has a real execution surface for capture/query/search
- the remaining gap is now one join: a single live trace carried end to end

## Scenario Contract

Current source-of-truth references:

- `/Users/xiamingxing/Workspace/.omo/_truth/scenarios/knowledge-capture-search.yaml`
- `/Users/xiamingxing/Workspace/.omo/_delivery/evidence/phase16/scenario-shell.yaml`
- `/Users/xiamingxing/Workspace/.omo/_delivery/evidence/phase16/capture-search-walkthrough.yaml`

Current contract:

```text
input:
  - text_or_markdown_file
  - query

output:
  - capture_receipt
  - search_hits
  - result_summary
  - evidence_refs
  - status
```

Current role split:

```text
runtime     -> entry bridge
OMO         -> scenario/policy/result closeout
kairon      -> capability binding and governance trace
gbrain      -> capture/search/retrieval
```

## Binding Chain

### 1. OMO defines the scenario boundary

Current scenario shell already binds:

- intent
- context
- policy
- execution
- verification
- recovery

For this scenario, `kairon` is the declared `governance_trace` surface.

What that means in practice:

`kairon` is expected to sit between scenario acceptance and downstream knowledge execution, and leave enough trace for inspection.

### 2. Kairon provides the route surface

Relevant file:

- `packages/agora/src/agora/server/mcp.py`

Current proof points:

- `route_call(tool_name, arguments, caller_identity)` forwards structured requests into the router
- `publish_event(...)` and `get_event_log(...)` expose an MCP-visible event surface
- service registration/removal also publishes registry events

Practical meaning:

once this scenario is normalized upstream, `kairon` already has a place to:

- accept routed tool intent
- record route-side events
- expose event history back out

### 3. Kairon provides the trace/event substrate

Relevant files:

- `packages/agora/src/agora/core/event_bus.py`
- `packages/agora/src/agora/audit_subscriber.py`
- `packages/agora/src/agora/web/app.py`

Current proof points:

- event bus persists events and carries `trace_id`
- hooks can attach audit / metrics / logging
- web API exposes `/api/events`, `/api/events/stream`, `/api/event-log`

Practical meaning:

`kairon` can already carry the middle evidence for:

```text
scenario accepted
-> route selected
-> event published
-> trace inspected
```

### 4. Kairon provides the operator-side launch/inspection surface

Relevant file:

- `packages/wksp/src/wksp/cli.py`

Supporting file:

- `packages/wksp/src/wksp/commands/contracts.py`

Current proof points:

- `workspace` is a real operator-facing CLI
- research / contracts / governance / mcp surfaces already exist
- exported research envelopes already include `trace_id`

Practical meaning:

even though `wksp` is not yet the sole operator-home, it already gives `kairon` a legitimate place to:

- launch operator-visible flows
- inspect result envelopes
- attach trace-bearing exported artifacts

### 5. Gbrain provides the execution surface

Relevant evidence:

- `projects/gbrain/test/mcp-eval-capture.test.ts`
- `projects/gbrain/test/e2e/source-isolation-pglite.test.ts`

Current proof points:

- `query` capture works for remote MCP callers
- captured rows preserve origin metadata like `remote`, `job_id`, `subagent_id`
- retrieval path respects source scoping on read-side execution

Practical meaning:

`gbrain` already proves the downstream half of the scenario:

```text
capture/query/search executes
-> receipt/candidate metadata is recorded
-> search/read path returns bounded results
```

## Current Cross-Project Assembly

Today the packet can be assembled honestly like this:

```text
knowledge-capture-search
-> OMO scenario contract exists
-> kairon route/event/trace surfaces exist
-> gbrain capture/query/search execution exists
-> OMO walkthrough/closeout evidence exists
```

This is enough to say:

- the main path is no longer imaginary
- the missing piece is not raw capability
- the missing piece is trace continuity across the whole chain

## Verification Runs

### Kairon route/event surface

```bash
cd "/Users/xiamingxing/Workspace/projects/kairon"
uv run --package agora --with pytest python -m pytest \
  packages/agora/tests/test_mcp_server.py -q -k 'publish_and_read_event or RouteCall'
```

Expected / latest verified outcome:

- `4 passed`
- route-call path green
- event publish/read path green

### Kairon operator/trace envelope surface

```bash
cd "/Users/xiamingxing/Workspace/projects/kairon"
uv run --package wksp --with pytest python -m pytest \
  packages/wksp/src/wksp/tests/test_cli_help_daily_contracts_profile.py -q -k 'trace_id'
```

Expected / latest verified outcome:

- `45 passed`
- exported envelope and contracts path carry `trace_id`
- daily/operator view keeps archived state readable as `已归档`

### Gbrain downstream execution surface

```bash
cd "/Users/xiamingxing/Workspace/projects/gbrain"
bun test test/mcp-eval-capture.test.ts test/e2e/source-isolation-pglite.test.ts
```

Latest verified outcome:

- `26 pass / 0 fail`
- op-layer query/search capture green
- source-isolated retrieval path green

## What is still missing

### Missing join 1: one carried trace

We still do not have one artifact that shows the same scenario instance carrying:

- OMO scenario id
- kairon trace/event id
- gbrain execution/ref
- OMO closeout evidence ref

That is the next concrete target.

Draft landing assets for that target now exist:

- `docs/knowledge_capture_run_record_spec.md`
- `docs/knowledge_capture_run_record_template.yaml`
- `docs/knowledge_capture_run_record_fixture_2026-06-05.yaml`

### Missing join 2: one user-visible result envelope

The current packet proves the middle and lower layers.

It still does not produce one final user-visible response envelope that is clearly derived from the same run instance.

### Missing join 3: live rather than fixture-backed closeout

Phase16 walkthrough is still fixture-backed at the final closeout layer.

So this packet upgrades the architecture truth, but it does not yet upgrade the final result state from fixture-backed to live.

## Next Step

The next artifact should be a single run record shaped like:

```text
scenario_id: knowledge-capture-search
request_id: <one id>
kairon_trace_id: <one id>
gbrain_execution_ref: <one id>
omo_evidence_refs:
  - scenario-shell
  - walkthrough
  - closeout
status: completed | failed_with_recovery
```

Once that exists, the main path moves from "assembled by audit" to "assembled by run evidence".

Current state update:

- the first fixture-backed instance record now exists at
  `docs/knowledge_capture_run_record_fixture_2026-06-05.yaml`
- it already binds one request id, one `kairon` event/trace pair, one `gbrain`
  execution ref, one capture receipt, and one retrieval hit
- it now also includes one `route:call.succeeded`-shaped `kairon` route event,
  so the middle segment is closer to real route semantics than the earlier probe-only form
- the latest route event in that record now comes from a real `router.route(...)`
  invocation with propagated `request_id` and `trace_id`
