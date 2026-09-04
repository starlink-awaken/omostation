---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-40
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Predictor preflight owner design

Replace the monthly Documents `@工作文档/卫健委/_control/predictor.py` writer
with a Workspace-owned preflight. Preserve the existing date-driven forecast
categories (三医、考核、合同/项目质量), but emit a structured
`documents.predictor-preflight.v1` evidence envelope rather than writing
`_runtime/巡检报告/forecast-*.md`.

The owner is read-only against Documents. It must not execute the legacy
predictor or modify business materials. Exit `0` means a forecast was generated
without findings; exit `1` means a forecast was generated with attention items;
exit `2` means required inputs or the evidence boundary are unavailable.

The legacy predictor remains intact for rollback/parity. The schedule cutover is
separate and must prove accepted-release identity, exact cron replacement,
unrelated-line byte identity, Workspace evidence output, and unchanged
Documents report state.
