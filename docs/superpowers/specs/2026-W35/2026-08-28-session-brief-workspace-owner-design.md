---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-34
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Session brief Workspace owner design

## Objective

Retire the scheduled Documents-side `@公共/_runtime/session-brief.py` writer
from the execution path. Reuse the canonical Workspace `bin/mof/generate-brief.py`
owner, which already produces the system BRIEF from OMO/Workspace state, and
make its root/output locations explicit for accepted-release execution.

## Contract

`generate-brief.py` keeps its current default behavior for local invocation and
accepts an explicit Workspace root plus output path through environment-backed
runtime parameters. The cron command runs code from an accepted release but
reads the live Workspace state and writes only the live Workspace `BRIEF.md`.
It must not import or execute `session-brief.py`, `domain-sync.py`,
`bridge-refresh.py`, or `async-audit.py` from Documents.

Documents `@驾驶舱/_control/BRIEF.md` remains content/legacy material during the
observation and rollback window. Cockpit's existing `brief` command remains the
human entry point; no second brief generator or entry point is introduced.

## Acceptance

Tests prove explicit root/output resolution, default compatibility, output
publication outside Documents, and no mutation of Documents. Cutover evidence
records accepted-release identity, before/after crontab hashes, exact old/new
counts, unrelated-line byte identity, and a post-cutover smoke.
