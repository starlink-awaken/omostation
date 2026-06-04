# Phase 11 Wave 3 review

Wave 3 has been activated.

## Activation evidence

1. `goals/current.yaml` promotes `G11.3` and `current_wave: 3`
2. `tasks/active/P11-W3-USER-MVP.yaml` is the sole active packet
3. `tasks/done/P11-W2-CORE-DEBT.yaml` records the prior packet closeout
4. `python3 -m pytest .omo/tests -q` → `158 passed`

Review evidence should accumulate here as the user-layer MVP tasks land.

## T3.8 / T3.9 — first identity slice landed

Delivered:

1. `projects/kairon/packages/agora/src/agora/identity.py`
   - adds `Identity`
   - adds `normalize_identity()`
2. `projects/kairon/packages/agora/src/agora/router.py`
   - normalizes `caller_id` once at the route boundary
   - emits canonical identity into accounting, audit, and `route:call.*` payloads
3. `projects/kairon/packages/agora/src/agora/accounting.py`
   - adds `CallRecord.from_identity()`
4. `projects/kairon/packages/agora/src/agora/audit.py`
   - direct audit logging now accepts typed identity input
5. `projects/kairon/packages/agora/src/agora/audit_subscriber.py`
   - event-trail actor now resolves from payload identity
6. `projects/kairon/packages/agora/src/agora/server/mcp.py`
   - `route_call(...)` now accepts optional `caller_identity` JSON and forwards it into the router boundary
7. `projects/kairon/packages/agora/src/agora/a2a/task_manager.py`
   - A2A tasks now persist `caller_identity` and execute with that identity at the router boundary
8. `projects/kairon/packages/agora/src/agora/web/app.py`
   - `/api/a2a/tasks/send` now accepts `caller_identity` and forwards it into the task manager

Verification:

- `uv run pytest packages/agora/tests/test_identity.py packages/agora/tests/test_accounting.py packages/agora/tests/test_audit.py packages/agora/tests/test_audit_subscriber.py packages/agora/tests/test_router.py packages/agora/tests/test_mcp_server.py packages/agora/tests/test_a2a.py packages/agora/tests/test_governance.py -q`
  - result: `152 passed, 1 skipped`
- `ruff check packages/agora/src/agora/identity.py packages/agora/src/agora/router.py packages/agora/src/agora/accounting.py packages/agora/src/agora/audit.py packages/agora/src/agora/audit_subscriber.py packages/agora/src/agora/server/mcp.py packages/agora/src/agora/a2a/task_manager.py packages/agora/src/agora/web/app.py packages/agora/tests/test_identity.py packages/agora/tests/test_accounting.py packages/agora/tests/test_audit.py packages/agora/tests/test_audit_subscriber.py packages/agora/tests/test_router.py packages/agora/tests/test_mcp_server.py packages/agora/tests/test_a2a.py`
  - result: clean

## T3.8 / T3.9 — pipeline identity follow-up landed

Delivered:

1. `projects/kairon/packages/agora/src/agora/pipeline.py`
   - `run(...)`, `run_stream(...)`, and `run_parallel(...)` now accept optional `caller_identity`
   - pipeline tool invocations now forward that identity into `router.route(...)`
   - `pipeline:started`, `pipeline:step:*`, and `pipeline:completed` events now include normalized identity payloads when provided
2. `projects/kairon/packages/agora/tests/test_pipeline_identity.py`
   - proves structured identity reaches the router boundary from pipeline callers
   - proves pipeline event payloads retain normalized identity fields for downstream audit/event consumers

Verification:

- `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_identity.py packages/agora/tests/test_pipeline_eventbus_integration.py packages/agora/tests/test_pipeline_identity.py -q`
  - result: `12 passed`

## T3.8 / T3.9 — MCP auth-context fallback closed the last entry seam

Delivered:

1. `projects/kairon/packages/agora/src/agora/server/mcp.py`
   - `route_call(...)` now resolves structured identity from the current FastMCP access token when explicit `caller_identity` is absent
   - explicit JSON `caller_identity` still wins when provided
2. `projects/kairon/packages/agora/tests/test_mcp_server.py`
   - proves the MCP route surface derives and forwards structured identity from auth context fallback
3. Existing `A2A` caller identity surface was revalidated to confirm there is no remaining non-router legacy seam in the live Wave 3 entrypoints

Verification:

- `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_mcp_server.py packages/agora/tests/test_identity.py packages/agora/tests/test_pipeline_eventbus_integration.py packages/agora/tests/test_pipeline_identity.py -q -k 'RouteCall or identity or eventbus'`
  - result: `17 passed`
- `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_a2a.py -q -k 'caller_identity or passes_caller_identity'`
  - result: `1 passed`

Identity closeout judgment:

1. Router, MCP, pipeline, and A2A now all carry structured identity into the same canonical route boundary
2. Audit/event/accounting binding now follows that normalized identity everywhere exercised by the Wave 3 MVP
3. T3.8 / T3.9 can now be treated as materially closed for Wave 3

## T3.10 — blocked scenario assessment completed

Delivered:

1. `.omo/summaries/phase11-wave3-scenario-assessment.md`
   - reassesses the 12 previously blocked scenarios from `.omo/drafts/scenario-analysis.md`
   - records disposition, evidence, and carry-forward priority for each scenario

Assessment judgment:

1. `D2` 注册 MCP 服务 → reclassified from **❌ blocked** to **⚠️ manual-feasible**
2. `D9` 用户权限配置 → reclassified from **❌ blocked** to **⚠️ manual-feasible**
3. the remaining blocked set shrank from `12` to `10`
4. Wave 3 MVP success metric remains `32/60 ✅`; T3.10 is satisfied by assessment/closeout, not by implementing all 12 scenarios

## T3.5 — KOS `/health` landed

Delivered:

1. `projects/kairon/packages/kos/src/kos/web/app.py`
   - switches to the package config shim first (`kos.config`)
   - adds `get_health_status()`
   - adds FastAPI `GET /health`
2. `projects/kairon/packages/kos/tests/test_web_app.py`
   - locks `/health` response shape for `status`, `workspace`, and `database`

Verification:

- `uv run pytest packages/kos/tests/test_web_app.py -q`
  - result: `1 passed`
- `ruff check packages/kos/src/kos/web/app.py packages/kos/tests/test_web_app.py`
  - result: clean

## T3.4 — `kairon-cli search` compatibility gap closed

Delivered:

1. `projects/kairon/packages/kos/kairon-cli.py`
   - adds the explicit `kairon-cli` wrapper over `kos.cli.__main__`
   - self-bootstraps `src/` so direct script execution does not require prior installation
2. `projects/kairon/packages/kos/kos-cli.py`
   - now uses the same `src/` bootstrap pattern
3. `projects/kairon/packages/kos/pyproject.toml`
   - now exposes `kairon-cli = "kos.cli.__main__:main"`
4. `projects/kairon/packages/kos/tests/test_kairon_cli.py`
   - proves the wrapper and packaging alias both exist
5. `projects/kairon/packages/kos/tests/test_workspace_package_metadata.py`
   - guards declared package `README.md` files so `uv sync --package ...` remains buildable
6. `projects/kairon/packages/wksp/README.md`
   `projects/kairon/packages/ontoderive/README.md`
   `projects/kairon/packages/cron-service/README.md`
   - remove the package-metadata debt that was blocking package sync

Verification:

- `uv run --package kos --with pytest python -m pytest packages/kos/tests/test_workspace_package_metadata.py packages/kos/tests/test_kairon_cli.py packages/kos/tests/test_cli.py packages/kos/tests/test_web_app.py -q`
  - result: `24 passed`
- `uv sync --package kos --package wksp --package ontoderive --package cron-service --inexact`
  - result: success
- `uv run --package kos kairon-cli search --help`
  - result: help output returned successfully

## T3.6 — pipeline completion/error notifications generalized

Delivered:

1. `projects/kairon/packages/wksp/src/wksp/commands/base.py`
   - adds generic `_notify_pipeline_success()` / `_notify_pipeline_error()` helpers
   - keeps `_notify_research_complete()` as the research-specific convenience wrapper
2. `projects/kairon/packages/wksp/src/wksp/commands/importer.py`
   - emits success notifications on completed imports
   - emits error notifications on empty/missing/unreadable import sources
3. `projects/kairon/packages/wksp/src/wksp/tests/test_base_notify.py`
   - locks notification formatting for success/error pipeline events
4. `projects/kairon/packages/wksp/src/wksp/tests/test_cli_import.py`
   - proves import success/error paths call the new notification helpers

Verification:

- `uv run --package wksp --with pytest python -m pytest packages/wksp/src/wksp/tests/test_cli_main_routing.py packages/wksp/src/wksp/tests/test_data_index.py packages/wksp/src/wksp/tests/test_cli_dashboard.py packages/wksp/src/wksp/tests/test_cli_import.py packages/wksp/src/wksp/tests/test_base_notify.py -q`
  - result: `70 passed`

## T3.7 — dashboard evidence revalidated

Delivered / confirmed:

1. `projects/kairon/packages/agora/src/agora/web/dashboard.html`
   - already provides the live dashboard shell
2. `projects/kairon/packages/agora/src/agora/web/app.py`
   - already serves dashboard HTML plus `/api/services`, `/api/research`, `/api/research/{id}`, and `/api/health`
3. `projects/kairon/packages/agora/tests/test_web_api.py`
   - already proves dashboard HTML and real research data API responses

Verification:

- `uv run --package agora --with pytest python -m pytest packages/agora/tests/test_web_api.py -q -k 'TestDashboard or TestApiResearch'`
  - result: `13 passed, 21 deselected`

## Search/data scout decisions

1. T3.4 search is largely pre-existing in `packages/kos`
   - `kos search` already exists
   - SQLite FTS5 backend already exists
   - naming/exposure gap is now closed by the `kairon-cli` wrapper + package script alias
2. T3.1-T3.3 should start in `packages/wksp`
   - public surface: `workspace data ...`
   - metadata home: `data/_index/`
   - first GC scope: `data/tmp/` only

## T3.1 / T3.2 / T3.3 — first data index slice landed

Delivered:

1. `projects/kairon/packages/wksp/src/wksp/data_index.py`
   - resolves the workspace root from env/cwd/module parents
   - writes `data/_index/catalog.json`, `types.json`, and `gc-policy.json`
   - seeds 5 data types and limits GC to `data/tmp/`
2. `projects/kairon/packages/wksp/src/wksp/commands/data.py`
   - adds `workspace data index`
   - adds `workspace data types`
   - adds `workspace data gc`
3. `projects/kairon/packages/wksp/src/wksp/cli.py`
   - routes the new `data` command group
   - keeps the existing CLI monkeypatch surface stable for current tests
4. `projects/kairon/packages/wksp/src/wksp/tests/test_data_index.py`
   - proves metadata materialization and seeded type registration
   - proves TTL cleanup only deletes expired files under `data/tmp/`
5. `projects/kairon/packages/wksp/src/wksp/tests/test_cli_main_routing.py`
   - proves `data index|types|gc` route through the top-level CLI

Verification:

- `uv run pytest packages/wksp/src/wksp/tests/test_cli_main_routing.py packages/wksp/src/wksp/tests/test_data_index.py packages/wksp/src/wksp/tests/test_cli_dashboard.py packages/wksp/src/wksp/tests/test_cli_import.py -q`
  - result: `65 passed`
- `uv run ruff check packages/wksp/src/wksp/cli.py packages/wksp/src/wksp/data_index.py packages/wksp/src/wksp/commands/data.py packages/wksp/src/wksp/tests/test_cli_main_routing.py packages/wksp/src/wksp/tests/test_data_index.py`
  - result: clean
