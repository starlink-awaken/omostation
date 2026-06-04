# Phase 11 Wave 4 review

Wave 4 has been activated.

## Current execution snapshot

Wave 4 is now materially underway. The first hardening slices landed across governance CI, absolute-path guarding, FastMCP convergence, Minerva temp cleanup, and KOS MetaType/storage calibration.

## Landed evidence

### T4.1 — Absolute path hardening (delivery-boundary slice)

- Added `.omo/tests/test_phase11_wave4_absolute_paths.py`
- Tightened the guard to the active Phase 11 delivery boundary: `projects/kairon/packages/**/*.py`
- Removed the last live `/Users/` offender inside that boundary from:
  - `projects/kairon/packages/codeanalyze/src/codeanalyze/commands/documents_cmd.py`
- Verification:
  - `python3 -m pytest .omo/tests/test_phase11_wave4_absolute_paths.py -q`

Judgment:

- **Completed**
- follow-up verification across the active production-code surface now returns no `/Users/` hits:
  - `rg -n '/Users/' projects --glob '**/*.{py,ts,tsx,js,jsx,go,java,sh}'`
  - result: **no matches**

### T4.2 — `pip install kairon` audit

Audit conclusion:

- The original gap was real: repo root was a metadata shell with no `src/kairon` import surface
- `pip install kairon` from package index required a real publish/release step after the root package was made buildable

Landed changes:

- root `projects/kairon/pyproject.toml` now has a real build backend
- added `projects/kairon/src/kairon/__init__.py`
- root `README.md` is now non-empty package metadata
- local source install smoke now succeeds:
  - `python3 -m venv /tmp/kairon-smoke-venv`
  - `/tmp/kairon-smoke-venv/bin/pip install .`
  - `/tmp/kairon-smoke-venv/bin/python -c 'import kairon'`
- release artifacts now build cleanly:
  - `uv build`
  - produced `dist/kairon-0.1.0.tar.gz`
  - produced `dist/kairon-0.1.0-py3-none-any.whl`
- wheel install smoke succeeds:
  - `/tmp/kairon-wheel-venv/bin/pip install dist/kairon-0.1.0-py3-none-any.whl`
  - `/tmp/kairon-wheel-venv/bin/python -c 'import kairon'`
- `https://pypi.org/pypi/kairon/json` currently returns `404`, so the public name is not already occupied on PyPI
- GitHub remote staging repo now exists:
  - `https://github.com/starlink-awaken/kairon`
  - root package files were submitted via `gh api` to seed `main`
- trusted publishing workflow landed at:
  - `https://github.com/starlink-awaken/kairon/blob/main/.github/workflows/publish.yml`
- TestPyPI publish workflow succeeded:
  - `https://github.com/starlink-awaken/kairon/actions/runs/26731397401`
- PyPI publish workflow succeeded:
  - `https://github.com/starlink-awaken/kairon/actions/runs/26731556051`
- clean-environment index install smoke now succeeds on both indexes:
  - `pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple kairon==0.1.0`
  - `pip install kairon==0.1.0`
  - `python -c 'import kairon; print(kairon.__version__)'`

Judgment:

- **Completed**
- root package is now installable from source, TestPyPI, and PyPI
- public `pip install kairon` is no longer a blocker for Phase 11 closeout

### T4.3 — KOS indexer hardening baseline

- Verified current KOS lint debt is already below the Wave 4 threshold:
  - `uv run --package kos ruff check packages/kos --statistics --exit-zero`
  - current result: **78 errors**
- Revalidated indexer-related tests:
  - `uv run --package kos --with pytest python -m pytest packages/kos/tests/test_indexer.py packages/kos/tests/test_mcp_server.py -q -k 'indexer or run_indexer'`
  - current result: **11 passed**

Judgment:

- **Current threshold satisfied**
- deeper debt reduction still optional, but not required to pass the stated Wave 4 gate

### T4.4 — OntoDerive FastMCP migration closeout

Audit conclusion:

- `agora` and `minerva` were already FastMCP-native
- the last live dual-stack surface was `ontoderive`

Landed changes:

- `ontoderive.engine.mcp_server` now owns the active JSON-RPC compatibility bridge through `handle_mcp_request(...)`
- `ontoderive.engine.web_server` no longer dispatches through `engine.mcp_handlers`
- `ontoderive.engine.toolforge.mcp_server` now delegates to the FastMCP-backed bridge
- OntoDerive MCP tests now assert the canonical **5-tool FastMCP** surface instead of the old 17-tool JSON-RPC surface
- CLI / serve copy now reflects FastMCP rather than “17 tools”

Verification:

- `uv run --package ontoderive --with pytest python -m pytest packages/ontoderive/tests/test_mcp_server.py packages/ontoderive/tests/test_toolforge_mcp.py packages/ontoderive/tests/test_e2e.py packages/ontoderive/tests/test_cli.py -q`
  - result: **24 passed**

Judgment:

- **Completed**

### T4.6 — Minerva temp cleanup

Landed change:

- `minerva.knowledge.mineru_adapter.parse_to_text(...)` now runs `parse_document(...)` inside a `tempfile.TemporaryDirectory()`
- markdown extraction now uses an ephemeral output directory instead of leaving residue behind
- `minerva.knowledge.mineru_adapter.cleanup_stale_mineru_outputs(...)` now removes stale `*_mineru_output` directories
- `minerva maintenance --action cleanup-temp --path <dir> --older-than-hours <n>` now exposes an operational cleanup trigger

Verification:

- `uv run --package minerva --with pytest python -m pytest packages/minerva/tests/unit/test_mineru_adapter.py -q`
  - result: **13 passed**
- `uv run --package minerva --with pytest python -m pytest packages/minerva/tests/unit/test_mineru_adapter.py packages/minerva/tests/unit/test_mcp_server.py -q -k 'cleanup'`
  - result: **3 passed**

Judgment:

- **Completed**
- Wave 4 now has both an ephemeral ingestion path and an explicit cleanup trigger for persistent MinerU output directories

### T4.7 — KOS storage format / MetaType calibration

Problem found:

- CLI exposed 8 canonical MetaType filters, but ingest persisted only `document/constraint/unknown`

Landed changes:

- added `projects/kairon/packages/kos/src/kos/meta_types.py`
- centralized:
  - `CANONICAL_META_TYPES`
  - `FILTERABLE_META_TYPES`
  - `infer_meta_type(...)`
- `kos.commands.ingest` now writes canonical MetaType values from kind + source-path hints
- KOS CLI help now reads the shared MetaType surface instead of a duplicated hardcoded string
- ADR recorded at:
  - `.omo/summaries/phase11-wave4-adr-kos-canonical-metatype.md`

Verification:

- `uv run --package kos --with pytest python -m pytest packages/kos/tests/test_ingest.py packages/kos/tests/test_indexer.py packages/kos/tests/test_mcp_server.py -q -k 'canonical_meta_types or indexer or run_indexer'`
  - result: **12 passed**

Judgment:

- **Completed**

### T4.8 — Governance CI enforcement

Landed changes:

- `.github/workflows/governance-check.yml` now hard-fails on:
  - `bash scripts/check-system-consistency.sh`
  - `python3 scripts/omo_worker.py task validate --all-active`
  - `python3 -m pytest .omo/tests -q`
- added `.omo/tests/test_phase11_wave4_governance_ci.py`

Verification:

- `python3 -m pytest .omo/tests/test_phase11_wave4_governance_ci.py -q`
- included in full `.omo/tests -q`

Judgment:

- **Completed**

### T4.5 — Hermes broken-link audit

Historical context:

- earlier phases recorded a `179` broken-symlink baseline in the Hermes bridge layer

Wave 4 audit:

- workspace-local check:
  - `cd /Users/xiamingxing/Workspace && find -L .hermes/scripts -type l | wc -l`
  - current result: **0**
- recorded audit:
  - `.omo/summaries/phase11-wave4-hermes-broken-links-audit.md`

Judgment:

- **Completed**

### T4.9 / T4.10 — Eidos protocol-contract pilot

Problem:

- `eidos.protocols` exposed runtime `Protocol`s, but did not yet provide explicit serialized payload contracts for cross-package validation

Landed changes:

- added `projects/kairon/packages/eidos/src/eidos/protocols/contracts.py`
- added first contract registry + validator:
  - `knowledge-card-v0.3`
  - `fact-v0.3`
- exported contract surface from `eidos.protocols`
- KOS ingest now consumes the contract validator as a preflight on supported Eidos payloads
- ADR recorded at:
  - `.omo/summaries/phase11-wave4-adr-eidos-protocol-contract-surface.md`

Verification:

- `uv run --package eidos --with pytest python -m pytest packages/eidos/tests/test_protocol_contracts.py -q`
  - result: **2 passed**
- `uv run --package kos --with pytest python -m pytest packages/kos/tests/test_eidos_contracts.py packages/kos/tests/test_ingest.py -q -k 'contract or canonical_meta_types'`
  - result: **2 passed**

Judgment:

- T4.9 — **completed**
- T4.10 — **completed**

### T4.11 — Phase 12 / 13 pre-planning gates

Wave 4 review confirmed the planning drafts already exist as live pre-planning artifacts:

- `.omo/plans/phase12-planning-gate.md`
- `.omo/plans/phase13-metacognition-preplanning.md`

Judgment:

- **Completed** at the document layer

## Current program judgment

Wave 4 now has meaningful executed evidence rather than only activation scaffolding.

Current status by task:

- T4.1 — **completed**
- T4.2 — **completed** (trusted publishing workflow is live; TestPyPI + PyPI publishes succeeded; `pip install kairon==0.1.0` is verified)
- T4.3 — **satisfied at current threshold**
- T4.4 — **completed**
- T4.5 — **completed**
- T4.6 — **completed**
- T4.7 — **completed**
- T4.8 — **completed**
- T4.9 — **completed**
- T4.10 — **completed**
- T4.11 — **completed**
