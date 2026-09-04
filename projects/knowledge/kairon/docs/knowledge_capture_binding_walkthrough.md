---
title: knowledge_capture_binding_walkthrough
type: doc
---

# Kairon Knowledge Capture Binding Walkthrough

> Scope: `projects/kairon`
> Scenario: `knowledge-capture-search`
> Date: 2026-06-05
> Purpose: prove what `kairon` already contributes to the main path, and what it still does not prove.

## Conclusion

`kairon` is no longer only a planned binding layer.

It already provides a real engine-side surface for:

- authenticated entry
- route and service selection
- event publication and retrieval
- trace / audit hook attachment
- operator-facing CLI entry

What it does **not** yet prove is a single live walkthrough where `knowledge-capture-search` is bound from scenario context to `gbrain` execution and then closed back into a user-visible result.

So the right status is:

- local binding evidence: `available`
- scenario-level live binding walkthrough: `not yet complete`

## Scenario Mapping

For `knowledge-capture-search`, `kairon` is responsible for the engine-side middle section:

```text
runtime / user intent
-> kairon binding surface
-> selected route / event / trace
-> downstream knowledge execution
```

In the current repo, that responsibility is split across:

- `packages/agora/src/agora/server/mcp.py`
- `packages/agora/src/agora/web/app.py`
- `packages/agora/src/agora/core/event_bus.py`
- `packages/wksp/src/wksp/cli.py`

## Evidence

### 1. MCP entry and auth surface

File:

- `packages/agora/src/agora/server/mcp.py`

Current observable facts:

- supports bearer-token auth via `AGORA_API_KEY`
- supports JWT auth via `AGORA_JWT_SECRET`
- keeps proxy lifecycle inside server lifespan
- exposes a stable MCP-side convergence surface instead of pure package-local calls

Why this matters:

- this is the point where a normalized upstream request can enter `kairon`
- without this layer, `kairon` cannot honestly claim to be a binding plane

### 2. Web event and read/write surface

File:

- `packages/agora/src/agora/web/app.py`

Current observable facts:

- write endpoints are auth-guarded
- `/api/events` supports event read/write
- `/api/events/stream` exposes SSE event streaming
- dashboard-facing GET paths remain readable

Why this matters:

- once a scenario is routed, this layer can expose the trace and status transitions outward
- this is the closest current `kairon` surface to a user-visible or operator-visible binding trail

### 3. Event bus and trace hook surface

File:

- `packages/agora/src/agora/core/event_bus.py`

Current observable facts:

- `publish()` persists event records
- published events can carry `trace_id`
- hooks can be registered for audit / metrics / logging
- event history can be queried via `get_event_log()`

Why this matters:

- this is the current lowest-level proof that `kairon` can carry governance trace, not just route selection
- it is enough to support a future scenario-level binding evidence packet

### 4. Operator-home candidate surface

File:

- `packages/wksp/src/wksp/cli.py`

Current observable facts:

- `workspace` exposes a real human CLI, not a placeholder
- command surface already includes `research`, `status`, `contracts`, `mcp`, `governance`
- there are E2E journey tests around this entry

Why this matters:

- for the current architecture, `wksp` is the strongest candidate for operator-home
- even if it is not yet the sole entrypoint, it is already a credible binding surface for scenario launch and inspection

## Verification

These commands were re-run as targeted evidence:

```bash
cd "/Users/xiamingxing/Workspace/projects/kairon"
uv run --package agora --with pytest python -m pytest \
  packages/agora/tests/test_mcp_server.py \
  packages/agora/tests/test_web_api.py -q
```

Result:

- `53 passed`

```bash
cd "/Users/xiamingxing/Workspace/projects/kairon"
uv run --package wksp --with pytest python -m pytest \
  packages/wksp/src/wksp/tests/test_cli_main_routing.py \
  packages/wksp/src/wksp/tests/test_e2e_journey.py -q
```

Result:

- `57 passed`

```bash
cd "/Users/xiamingxing/Workspace/projects/kairon"
uv run --package sharedbrain-bridge --with pytest python -m pytest \
  packages/sharedbrain-bridge/tests/test_sharedbrain_bridge.py -q
```

Result:

- `10 passed`

Interpretation:

- `agora` entry/event surfaces are currently green under targeted package validation
- `wksp` is green as a real operator-facing entry
- `sharedbrain-bridge` is not broken at package-test level, but it is still not the trusted path for this scenario

## Current Gaps

### 1. No direct scenario-to-route proof

We still do not have one evidence item that says:

```text
knowledge-capture-search
-> kairon selected this route
-> this trace_id was emitted
-> this downstream capability was used
```

That is the next missing artifact.

### 2. SharedBrain boundary still weak

`sharedbrain-bridge` passes package tests, but it is still under-specified as the live upstream/downstream contract for this scenario.

So it should not yet be used as the primary proof point for `knowledge-capture-search`.

### 3. Package-level validation contract is not uniform

Bare `python3 -m pytest` collection is not a reliable validation path here.

The current practical contract is package-scoped execution via:

- `uv run --package agora --with pytest ...`
- `uv run --package wksp --with pytest ...`
- `uv run --package sharedbrain-bridge --with pytest ...`

This needs to be documented as the real verification baseline.

## Recommended Next Step

Create one scenario-level evidence packet that binds:

```text
phase16 scenario context
-> kairon route / event / trace
-> gbrain capture/search execution
-> OMO result closeout reference
```

That is the smallest step that upgrades `kairon` from local binding proof to main-path binding proof.

Current follow-up asset:

- `docs/knowledge_capture_scenario_binding_packet.md`
- `docs/knowledge_capture_run_record_spec.md`
- `docs/knowledge_capture_run_record_template.yaml`
- `docs/knowledge_capture_run_record_fixture_2026-06-05.yaml`
