---
title: Documents KEMS legacy parity
type: analysis
---

# Documents KEMS legacy parity

This decision table covers the 12 Python entry points under `@公共/_runtime/kems-v2/` and the 10 scripts under `@学习进化/_knowledge/10-systems/KEMS/.kems/_scripts/`.

The target architecture keeps Documents as the Method/Profile/content authority. KOS remains the only KEMS runtime; L4 owns domain contracts; OMO owns tasks and approvals; Runtime owns execution and schedules; Cockpit owns projections. Historical prose references are not treated as live runtime consumers.

## Decision table

| Legacy entry point | Decision | Workspace replacement | Reason |
|---|---|---|---|
| `@公共/_runtime/kems-v2/check-critical-path.py` | retire | OMO milestones + Runtime checks + Cockpit projection | Business deadline orchestration is not a KEMS content primitive. |
| `@公共/_runtime/kems-v2/check-model-conformance.py` | extend | `kos.kems.check_content_records` | Required metadata, allowed status, and configurable freshness are reusable; filename-based model inference is not. |
| `@公共/_runtime/kems-v2/check-ontology-consistency.py` | map-existing | KOS ontology schema/extraction + `GraphStore` provenance | The legacy YAML/Markdown dual-representation check preserves duplicated SSOTs that the graph contract removes. |
| `@公共/_runtime/kems-v2/check-ssot-sync.py` | extend | `check_source_consistency` + KEMS SQLite health | Source IDs and SHA-256 digests are checked against the redacted graph snapshot without subprocess fan-out. |
| `@公共/_runtime/kems-v2/gen-report-view.py` | retire | Cockpit governed projections | Report generation is a presentation concern and must not write from KEMS into Documents. |
| `@公共/_runtime/kems-v2/graph-query.py` | map-existing | `GraphStore.get_entity`, `search_entities`, and `neighbors` | Existing graph queries already return provenance-bound, redacted records. |
| `@公共/_runtime/kems-v2/kems-cross-check.py` | extend | `build_domain_profile` + L4/Cockpit domain enumeration | Preserve hash/version parity, but remove shared-script and symlink identity as the authority. |
| `@公共/_runtime/kems-v2/kems-init.py` | retire | L4 declarative domain bootstrap | Runtime/script copying was removed from domain initialization. |
| `@公共/_runtime/kems-v2/kems-snapshot.py` | map-existing | `GraphStore.export_snapshot`, KEMS health, and `DomainProfile` | The existing store already emits deterministic snapshots with raw text excluded by default. |
| `@公共/_runtime/kems-v2/kems-toolkit.py` | extend | `check_content_records`; mutation and scheduling move to Runtime | Only metadata/freshness/index checks belong in KOS; state-file writes and inbox orchestration do not. |
| `@公共/_runtime/kems-v2/model-ask.py` | map-existing | KOS graph search + Minerva research/query entry points | The filename/regex question router is domain-specific and duplicates graph retrieval. |
| `@公共/_runtime/kems-v2/refresh-indexes.py` | map-existing | KOS fingerprint indexer and status APIs | Indexes and counts are derived KOS state, not Documents-authored runtime. |
| `@学习进化/.../.kems/_scripts/bootstrap.py` | retire | L4 declarative domain bootstrap | It copies an executable framework into content roots. |
| `@学习进化/.../.kems/_scripts/check-freshness.py` | extend | `check_content_records` | Configurable and date-injected freshness replaces the fixed 7/14-day script and its stale-rate arithmetic bug. |
| `@学习进化/.../.kems/_scripts/check-frontmatter.py` | extend | `check_content_records` | Required metadata validation is retained without reading or retaining raw bodies. |
| `@学习进化/.../.kems/_scripts/check-index.py` | extend | `check_content_records` exact index coverage | Missing and dangling refs fail closed and expose only refs/hashes. |
| `@学习进化/.../.kems/_scripts/generate-dashboard.py` | retire | Cockpit governed projections | HTML output is a projection, not KEMS state. |
| `@学习进化/.../.kems/_scripts/install.sh` | retire | Workspace package/environment management | Self-installing scripts inside Documents are not a supported runtime surface. |
| `@学习进化/.../.kems/_scripts/kems-cli.py` | map-existing | KOS CLI + L4 domain commands | A second bootstrap/health CLI would split authority. |
| `@学习进化/.../.kems/_scripts/kems-mcp.py` | map-existing | KOS MCP + L4 domain MCP | A second hand-written stdio server would split tool identity and lifecycle. |
| `@学习进化/.../.kems/_scripts/run-sunsets.py` | retire | OMO lifecycle state + Runtime schedule | Sunset execution is task lifecycle orchestration; the legacy script only prints candidates. |
| `@学习进化/.../.kems/_scripts/validate-schema.py` | map-existing | KOS ontology schema/extraction plus metadata checks | Content-body regex validation is replaced by the existing ontology contracts; no second schema engine is added. |

## Implemented extension boundary

- `content_checks.py` accepts metadata-only records, rejects raw-content keys, and emits only refs, hashes, field names, and status codes.
- `check_source_consistency` compares `SourceManifest` admission decisions with `GraphStore.export_snapshot(include_text=False)`.
- `domain_profile.py` binds a Documents Method and Profile by ref, version, and SHA-256; it reuses the KEMS SQLite health contract and exposes only safe graph counts.
- No legacy CLI, MCP server, scheduler, dashboard, indexer, or Documents writer was copied into KOS.
