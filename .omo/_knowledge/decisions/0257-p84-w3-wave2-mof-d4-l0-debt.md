---
id: ADR-0257
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-07-28
related:
  - 0240-mof-d1d4-decisions-aaaa-phase1.md
  - 0256-p84-w3-throughput-wave.md
---

# ADR-0257: W3 wave2 — MOF D4 模板投影 + L0 gac 债关闭

## Decision
1. **MOF D4**: `tool_generate` 明示 `codegen=false` / `projection_kind=template_yaml_json`.
2. **gac-consensus-inject**: 缺 `entity_type` 时 ADD COLUMN + 回填; 查询 schema-tolerant.
3. **gac-compute-onboard --check**: 轻量路径 (无 uv spawn), 目标 <2s, 不调大超时.

## Status
**ACCEPTED** 2026-07-28.
