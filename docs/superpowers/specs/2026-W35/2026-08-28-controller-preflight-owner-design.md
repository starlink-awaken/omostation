---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-35
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Weijian controller preflight owner design

## Objective

Move the scheduled execution boundary for the Documents Weijian controller to
Workspace. The old `@工作文档/卫健委/_control/controller.py` writes daily reports
under Documents and invokes several other Documents scripts. The replacement
must observe the same 11 CR rule families without executing those scripts or
mutating Documents.

## Contract

Reuse `bin/gac/documents-domain-owner-job.py controller-preflight` as the one
root entrypoint. The owner reads bounded content inputs and Workspace-bound
state, then emits `documents.controller-preflight.v1` with per-rule findings for
CR01, CR02, CR03, CR05, CR08, CR23, CR24, CR25, CR26, CR29, and CR30.

Existing Runtime control-health, model-freshness, sanyi, and controller-shadow
owners remain canonical evidence sources where they already cover a rule. The
new preflight may reproduce only the missing read-only checks (OCR inventory,
critical-path/material/stage presence and document-governance summaries); it
must not call a Documents executable. It must preserve truthful exit semantics:
0 for no findings, 1 for findings, and 2 for unavailable or invalid inputs.

All evidence is written below the Workspace runtime state root. Documents
signals, control files, reports, and business materials are never written.
The legacy controller remains available for rollback and parity comparison
until the scheduled cutover has been observed.

## Acceptance

Tests prove all 11 rule IDs are represented, missing input is fail-closed,
findings use stable severity/rule envelopes, evidence is outside Documents, and
the source tree is unchanged by the owner invocation.
