---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents consumer-audit command path tokenization hardening
bet_id: BET-Y1Q3-T10-102
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
type: ssot
last_updated: 2026-09-03
---

# Documents consumer-audit command path tokenization hardening

## Intent

Restore the consumer audit as a truthful cutover gate. A live Claude Scheduled
skill currently invokes `bash ~/Documents/@学习进化/_control/l4-kernel.sh all`,
but the audit absorbs ` all` into the path token and therefore omits the active
Documents executor. The parser must separate executable paths from argv while
preserving quoted paths that legitimately contain spaces.

## Contract

- Parse unquoted absolute and `~/Documents` paths only through the first shell
  whitespace or existing command delimiter.
- Preserve spaces inside a matching quoted path and stop at its closing quote.
- Treat extensionless paths under `_control/executors/` and `.githooks/` as
  execution candidates, using one shared candidate predicate for discovery and
  execution-mode classification.
- Scheduled skills, crontab, and LaunchAgents that invoke a Documents executor
  remain `documents-executor`, `writes_documents=true`, and
  `forbidden_executor=true`.
- Workspace owner commands that read Documents through the canonical owner
  entry remain `workspace-owner-read` and are never promoted to a forbidden
  executor.

## Non-goals

- No modification of Claude Scheduled skills, crontab, LaunchAgents, Documents
  content, migration-family status, or quarantine payloads in this BET.
- No second consumer registry, dispatcher, parser, or owner command.
- No claim that learning-runtime or Documents physical purity is complete.

## Acceptance

- Focused tests reproduce the current false negative before implementation.
- Unquoted HOME and absolute executable paths with trailing argv are detected.
- Quoted executable paths containing spaces remain intact.
- Extensionless `_control/executors` commands are detected.
- A fresh host audit reports the live `vault-daily-health` Scheduled reference
  as a forbidden Documents executor and leaves canonical Workspace owner reads
  non-forbidden.
- Tests, Ruff, ledger lint, doc SSOT, GaC, PR checks, and mainline replay pass.

## Rollback

Revert the parser/candidate-predicate change and its tests. No host or Documents
rollback is required because this BET is read-only outside Workspace code.
