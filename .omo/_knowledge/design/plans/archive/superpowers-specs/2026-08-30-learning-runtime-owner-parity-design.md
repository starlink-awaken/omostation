---
schema_version: specification/v1
spec_version: 1.0.0
title: Workspace owner parity for learning decay inspection
bet_id: BET-Y1Q3-T10-99
status: accepted
lifecycle: contract
owner: runtime-team
created: 2026-08-30
last-reviewed: 2026-08-30
risk_level: L2
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Workspace owner parity for learning decay inspection

## Intent

Move the read-only meaning of the legacy learning `knowledge-decay` command
into the canonical Workspace Runtime owner plane. Documents remains the source
of concept content and declarations; Runtime owns execution, bounded evidence,
and the user-facing owner jobs.

## Existing boundary

The legacy implementation lives at
`Documents/@学习进化/_control/scripts/knowledge-decay.sh`. Its safe modes are
`scan` and `ls-orphan`; its `mark-stale` mode mutates Documents and is not part
of this parity slice. The existing canonical entry is
`runtime documents run <job-id>`, backed by the Workspace binding registry and
Runtime's fail-closed job sandbox.

## Contract

1. Register two explicit manual jobs:
   - `documents-learning-decay`, action `audit_concept_decay`, mode `scan`.
   - `documents-learning-orphans`, action `list_orphan_concepts`, mode
     `ls-orphan`.
2. Both jobs read only
   `@学习进化/_knowledge/50-concepts`, declare `writes: []`, use owner
   `runtime-learning`, fail closed, and publish evidence below the Runtime
   state root.
3. The owner reproduces the legacy read-only rules:
   - recurse through regular Markdown concept files;
   - exclude index/readme/ontology files;
   - count a reference when another concept file contains the target basename;
   - prefer the concept vault's last Git timestamp and fall back to file mtime;
   - classify age as fresh (<7d), normal (7–20d), aging (21–29d), stale
     (30–59d), or decayed (>=60d);
   - report stale/decayed files as decay candidates without emitting file names.
4. Owner stdout is aggregate-only JSON. Runtime validates the exact evidence
   schema before persisting a receipt. No source text, absolute path, title,
   filename, or personal identity may enter the receipt.
5. `runtime documents run ... --dry-run --json` must validate the registered
   owner without starting it or creating state. The normal run may write only
   Runtime's isolated owner output and evidence roots.

## Out of scope and safety

- `mark-stale`, archive moves, inbox routing, `l4-kernel all`, daemon wrappers,
  G18 executors, and `.githooks` remain untouched and retain their own future
  owner-parity work.
- No host launchd, cron, or client configuration changes occur here.
- A live canary is read-only and may return `attention` when the concept corpus
  has orphans or decay candidates; that is truthful health evidence, not a
  failed owner registration.

## Acceptance

- The binding and `JobSpec` are exact and duplicate-resistant.
- Unit and integration tests prove the semantics, path containment, evidence
  redaction, dry-run behavior, and CLI registration.
- A live canary runs from the Workspace Runtime entry point against the actual
  Documents concept root and produces a Runtime-only receipt.
- `learning-runtime` remains `in_progress` until the write-capable and
  control-plane residuals have separate parity evidence.
