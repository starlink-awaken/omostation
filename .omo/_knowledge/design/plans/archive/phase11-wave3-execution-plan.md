---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Phase 11 Wave 3 execution plan: User layer MVP

> Packet: P11-W3-USER-MVP
> Status: completed
> Entry gate: Wave 2 closeout GO (D2/D3/D7 verified + SB decision completed + KOS ruff ≤500)

---

## 1. Goal

User layer MVP — users can see, search, and operate their data through unified tools and interfaces.

---

## 2. Scope & deliverables

### G11.3.1 — Centralized data index

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T3.1 | Unified data directory API — `data/_index` metadata catalog | `wksp.data_index` + `workspace data index` | `workspace data index --json` enumerates workspace data dirs |
| T3.2 | Data type registry — per-project format registration | `data/_index/types.json` + `workspace data types` | At least 5 data types registered |
| T3.3 | TTL/GC policy v1 — `data/tmp/` auto-cleanup | `data/_index/gc-policy.json` + `workspace data gc` | Expired `data/tmp/` files removed without touching runtime logs |

### G11.3.2 — Basic user tools

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T3.4 | SQLite FTS5 full-text search — `kairon-cli search` with FTS5 backend | `kairon-cli` compatibility entrypoint over `kos` search | `kairon-cli search --help` and `kairon-cli search "keyword"` both execute |
| T3.5 | HTTP health check endpoint — unified `/health` | `kairon-web health` or FastAPI endpoint | `curl localhost:8080/health` returns `{"status":"ok"}` |
| T3.6 | macOS notifications — pipeline completion/error alerts | Generic pipeline notification helpers + import/research hooks | Import/research success+error paths emit macOS notification events |
| T3.7 | Workspace dashboard — minimal Web UI (project status, task stats, health score) | Agora dashboard + workspace research/service APIs | Dashboard HTML and live research/service APIs render real data |

### G11.3.3 — Identity structuring

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T3.8 | Structured identity model — replace `string caller_id` with typed identity | `agora.identity.Identity` data class | Caller identity validated across modules |
| T3.9 | Identity audit trail — operation log bound to identity | Audit log module | Every operation logged with identity |

Current Wave 3 progress note:

- 2026-06-01: `packages/kos/src/kos/web/app.py` now exposes `/health` and returns `{"status":"ok", ...}` with workspace + database reachability
- Search scout confirms T3.4 backend already materially exists in `packages/kos` (`kos search` + SQLite FTS5); remaining gap was packet wording / exposure
- Data scout recommends implementing T3.1-T3.3 in `packages/wksp`, persisting metadata under `data/_index/`, and limiting first GC scope to `data/tmp/`
- 2026-06-01: `packages/wksp/src/wksp/data_index.py` now materializes `data/_index/catalog.json`, `types.json`, and `gc-policy.json`
- `workspace data index|types|gc` are now routed through `wksp` CLI, with GC explicitly scoped to `data/tmp/`
- Verification for the new data slice:
  - `uv run pytest packages/wksp/src/wksp/tests/test_cli_main_routing.py packages/wksp/src/wksp/tests/test_data_index.py packages/wksp/src/wksp/tests/test_cli_dashboard.py packages/wksp/src/wksp/tests/test_cli_import.py -q`
  - result: `65 passed`
  - `uv run ruff check packages/wksp/src/wksp/cli.py packages/wksp/src/wksp/data_index.py packages/wksp/src/wksp/commands/data.py packages/wksp/src/wksp/tests/test_cli_main_routing.py packages/wksp/src/wksp/tests/test_data_index.py`
  - result: clean
- 2026-06-01: `packages/kos/kairon-cli.py` and `packages/kos/pyproject.toml` now expose `kairon-cli` as a compatibility search entrypoint over `kos`
- `packages/kos/kos-cli.py` now self-bootstraps `src/`, so direct script execution no longer depends on the package already being installed
- 2026-06-01: `wksp.commands.base` now exposes generic pipeline success/error notifications; import success/error paths now emit macOS notification events in addition to research completion
- 2026-06-01: Agora dashboard evidence was revalidated through `packages/agora/tests/test_web_api.py -k 'TestDashboard or TestApiResearch'`, confirming HTML plus live research/service data APIs remain wired
- 2026-06-01: first Agora-local identity slice landed with `agora.identity.Identity` + `normalize_identity()`
- Router now normalizes typed identity once and propagates canonical actor/billing identity to accounting, direct audit, and `route:call.*` event payloads
- `AuditSubscriber` now binds route-event actor from payload identity instead of generic `route`
- 2026-06-01: `agora.pipeline.Pipeline` now accepts `caller_identity`, forwards it to `router.route(...)`, and emits normalized identity payloads on `pipeline:*` events
- Verification for the pipeline identity slice:
  - `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_identity.py packages/agora/tests/test_pipeline_eventbus_integration.py packages/agora/tests/test_pipeline_identity.py -q`
  - result: `12 passed`
- 2026-06-01: `agora.server.mcp.route_call(...)` now derives structured identity from the current FastMCP access token when explicit `caller_identity` is omitted
- Existing A2A `caller_identity` flow was revalidated after the pipeline/MCP identity follow-up:
  - `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_mcp_server.py packages/agora/tests/test_identity.py packages/agora/tests/test_pipeline_eventbus_integration.py packages/agora/tests/test_pipeline_identity.py -q -k 'RouteCall or identity or eventbus'`
  - result: `17 passed`
  - `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_a2a.py -q -k 'caller_identity or passes_caller_identity'`
  - result: `1 passed`
- T3.8/T3.9 are now materially closed across router, MCP, pipeline, and A2A entry seams
- 2026-06-01: the 12 previously blocked scenarios were reassessed in `.omo/summaries/phase11-wave3-scenario-assessment.md`
- Scenario assessment judgment:
  - `D2` (register MCP service) and `D9` (permission configuration) are now **manual-feasible**, not hard-blocked
  - the remaining blocked set shrank from `12` to `10`
  - Wave 3 MVP success metric remains `32/60 ✅`; T3.10 is satisfied by assessment and disposition, not by implementing all 12 scenarios

### G11.3.4 — Scenario assessment

| # | Task | Deliverable |
|---|------|-------------|
| T3.10 | ❌ scenario feasibility assessment — evaluate 12 blocked scenarios for viability or closeout | `.omo/summaries/phase11-wave3-scenario-assessment.md` |

---

## 3. Exit gate checklist

- [x] Data directory index API operational
- [x] Data type registry with ≥5 types
- [x] TTL/GC policy v1 deployed
- [x] `kairon-cli search` with FTS5 works
- [x] `/health` endpoint responsive
- [x] macOS notification works
- [x] Workspace dashboard renders real project data
- [x] Structured identity replaces `caller_id`
- [x] Audit trail bound to identity
- [x] 12 ❌ scenarios assessed
- [ ] Wave 3 closeout recorded in `summaries/phase11-wave3-closeout.md`
- [ ] Wave 4 execution plan reviewed and approved

---

## 4. Task mapping

```
P11-W3-USER-MVP:
  tasks:
    - T3.1 — Unified data directory API
    - T3.2 — Data type registry
    - T3.3 — TTL/GC policy v1
    - T3.4 — SQLite FTS5 search CLI
    - T3.5 — HTTP health check endpoint
    - T3.6 — macOS notifications
    - T3.7 — Workspace dashboard Web UI
    - T3.8 — Structured identity model
    - T3.9 — Identity audit trail
    - T3.10 — ❌ scenario assessment
```
